# manager.py
# H.265 Encoding Manager (Master Node)

import os
import time
import threading
import requests
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from datetime import datetime
from dotenv import load_dotenv

# Import from local modules
from database import engine, VideoFile, WorkerNode, Job, create_db_and_tables, add_worker
import scanner

load_dotenv()

# ====================
# Configuration
# ====================

DISPATCH_INTERVAL = int(os.environ.get("POLL_INTERVAL", 1))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 1))
MAX_RETRIES = 3
VIDEO_ROOT = os.environ.get("VIDEO_ROOT", "./test")

# Defaults
DEFAULT_PRESET = os.environ.get("DEFAULT_PRESET", "medium")
DEFAULT_CRF = int(os.environ.get("DEFAULT_CRF", 28))
DEFAULT_THREADS = int(os.environ.get("DEFAULT_THREADS", 0))

# ====================
# FastAPI Setup
# ====================

app = FastAPI(title="H265 Manager")
templates = Jinja2Templates(directory="templates")
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ====================
# Helper Functions
# ====================

def is_worker_active(worker: WorkerNode) -> bool:
    """Check if a worker is reachable and idle."""
    try:
        r = requests.get(f"{worker.url}/status", timeout=2)
        if r.status_code == 200:
            data = r.json()
            # If state is idle, it's definitely free.
            # If busy, we need to check if it's busy with OUR job or ghost job.
            # But the scheduling rule is: 1 job per worker.
            # So if it says busy, we treat it as unavailable.
            if data.get("state") != "idle":
                 pass
            return data.get("state") == "idle"
    except Exception:
        pass
    return False

def dispatch_job(job: Job, worker: WorkerNode) -> bool:
    """Send a job to a worker."""
    try:
        payload = {
            "job_id": job.id,
            "rel_path": job.video.path, # Join should be loaded
            "preset": job.preset,
            "crf": job.crf,
            "threads": worker.threads_capacity if worker.threads_capacity > 0 else 0
        }
        r = requests.post(f"{worker.url}/jobs", json=payload, timeout=10)
        return r.status_code == 202
    except Exception as e:
        print(f"Failed to dispatch Job {job.id} to {worker.name} ({worker.ip}): {e}")
        return False

# ====================
# Background Threads
# ====================

retry_counts = {}

def dispatch_loop():
    """Background thread to dispatch queued jobs to idle workers."""
    print(f"Dispatcher started (Interval: {DISPATCH_INTERVAL}s)")
    while True:
        try:
            with Session(engine) as session:
                # 1. Get Queued Jobs (FIFO by Created At)
                # Eager load video for path
                queued_jobs = session.exec(
                    select(Job)
                    .where(Job.status == "queued")
                    .order_by(Job.created_at)
                    .options(selectinload(Job.video))
                ).all()
                
                if queued_jobs:
                    # 2. Get All Enabled Workers
                    workers = session.exec(select(WorkerNode).where(WorkerNode.enabled == True)).all()
                    
                    # 3. Filter for IDLE workers (check DB state first to avoid network spam + strict 1 job rule)
                    # We check if worker has ANY job in 'processing' state in DB.
                    # Because poll_loop updates DB, DB acts as state of truth for assignment.
                    
                    active_worker_ids = set()
                    # Check for processing OR paused jobs (worker is still holding the job)
                    busy_jobs = session.exec(select(Job).where(Job.status.in_(["processing", "paused"]))).all()
                    for job in busy_jobs:
                        if job.worker_id:
                            active_worker_ids.add(job.worker_id)
                    
                    # Available = Enabled + Online + Not Busy
                    available_workers = [
                        w for w in workers 
                        if w.is_online and w.id not in active_worker_ids
                    ]
                    
                    # 4. Assignment Loop
                    # Simple FIFO: Assign first job to first available worker
                    
                    w_idx = 0
                    for job in queued_jobs:
                        if w_idx >= len(available_workers):
                            break # No more workers
                        
                        worker = available_workers[w_idx]
                        
                        # Trust DB state (is_online) and poller updates.
                        # Direct dispatch without pre-check reduces latency.
                        print(f"Assigning Job {job.id} ({job.video.filename}) to {worker.name}...")
                        
                        if dispatch_job(job, worker):
                            job.status = "processing"
                            job.worker_id = worker.id
                            job.started_at = int(time.time())
                            
                            session.add(job)
                            session.commit()
                            print(f"Dispatched Job {job.id}")
                            w_idx += 1
                        else:
                            print(f"Worker {worker.name} rejected job (Dispatch failed).")
                            # If dispatch fails, worker might be offline or ghost busy.
                            # Poller will eventually update its status.
                            # Try next worker for THIS job? No, loop structure assigns 1 job to 1 worker. 
                            # If this worker failed, we just skip it for this cycle.
                            w_idx += 1 

        except Exception as e:
            print(f"Error in dispatch loop: {e}")
            
        time.sleep(DISPATCH_INTERVAL)

def poll_loop():
    """Background thread to poll status of all workers and update jobs."""
    print(f"Poller started (Interval: {POLL_INTERVAL}s)")
    while True:
        start_time = time.time()
        updated_jobs = set()

        try:
            with Session(engine) as session:
                # 1. Check all workers
                workers = session.exec(select(WorkerNode)).all()
                
                for worker in workers:

                    try:  # Try to get worker status
                        r = requests.get(f"{worker.url}/status", timeout=0.1)
                        data = r.json()
                    except Exception:
                        worker.is_online = False
                        session.add(worker)
                        continue
                    if r.status_code != 200:
                        worker.is_online = False
                        session.add(worker)
                        continue

                    # Worker is online
                    worker.is_online = True
                    session.add(worker)

                    if data["state"] == "idle": continue
                    
                    # Worker is busy, check if it has a job_id
                    job_id = data.get("job_id")
                    if not job_id: continue  # Should never happen actually
                    
                    # Poll job details
                    try:
                        jr = requests.get(f"{worker.url}/jobs/info/{job_id}", timeout=0.1)
                        jdata = jr.json()
                    except Exception as e:
                        print(f"Failed to poll job {job_id} details: {e}")
                        continue
                    if jr.status_code != 200: continue
                    
                    # Process job data
                    job = session.get(Job, job_id)
                    # If job is paused, we shouldn't kill it.
                    if not job or job.status not in ["processing", "paused"]:
                        # Ghost job: worker is processing a job we don't know about
                        # Tell worker to stop it
                        print(f"Ghost job {job_id} on {worker.name}. Stopping it.")
                        try:
                            requests.post(f"{worker.url}/jobs/stop/{job_id}", timeout=1)
                        except Exception as e:
                            print(f"Failed to stop ghost job {job_id}: {e}")
                        continue
                    
                    # Mark job as updated
                    updated_jobs.add(job_id)
                    
                    # Update job based on status
                    status = jdata.get("status")
                    frames_done = jdata.get("frames_done", 0)
                    fps = jdata.get("fps", 0.0)
                    
                    if status == "completed":
                        job.status = "completed"
                        job.progress_pct = 100.0
                        job.completed_at = int(time.time())
                        job.video.status = "completed"
                        session.add(job.video)
                        print(f"Job {job.id} Completed.")

                        # Auto-add the new file to DB
                        try:
                            # Construct expected output path
                            # Worker hardcodes output to: {base}_h265.mp4
                            src_rel_path = job.video.path
                            base, _ = os.path.splitext(src_rel_path)
                            out_rel_path = f"{base}_h265.mp4"
                            
                            # Check if it already exists in DB to avoid duplicates
                            existing = session.exec(select(VideoFile).where(VideoFile.path == out_rel_path)).first()
                            
                            if not existing:
                                abs_out_path = os.path.join(VIDEO_ROOT, out_rel_path)
                                if os.path.exists(abs_out_path):
                                    size = os.path.getsize(abs_out_path)
                                    filename = os.path.basename(out_rel_path)
                                    
                                    new_video = VideoFile(
                                        path=out_rel_path,
                                        filename=filename,
                                        size=size,
                                        codec="hevc", # Safe assumption
                                        duration=job.video.duration, # Should be same
                                        frames=job.video.frames,
                                        status="completed",
                                        orig=job.video.id
                                    )
                                    session.add(new_video)
                                    print(f"Auto-added new file: {filename} (derived from Job {job.id})")
                        except Exception as e:
                            print(f"Failed to auto-add new file for Job {job.id}: {e}")
                    
                    elif status == "error":
                        job.status = "error"
                        job.video.status = "pending"
                        session.add(job.video)
                        print(f"Job {job.id} Error from worker.")
                    
                    elif status == "processing":
                        job.frames_processed = frames_done
                        job.fps = fps
                        # Only update status/progress if we are not paused, or if we want to update progress while paused?
                        # If we are paused, we stay paused.
                        if job.status == "processing":
                            if job.video.frames > 0:
                                job.progress_pct = min((frames_done / job.video.frames) * 100, 99.9)
                    
                    session.add(job)
                    session.add(worker)
                
                # 2. Check for stale processing jobs
                processing_jobs = session.exec(
                    select(Job).where(Job.status == "processing")
                ).all()
                
                for job in processing_jobs:
                    if job.id not in updated_jobs:
                        print(f"Job {job.id} stagnant (not updated). Marking error.")
                        job.status = "error"
                        job.video.status = "pending"
                        session.add(job)
                        session.add(job.video)

                session.commit()

        except Exception as e:
            print(f"Error in poll loop: {e}")
            
        elapsed = time.time() - start_time
        # print(f"Poll loop took {elapsed:.3f}s")
        
        # Determine sleep time to maintain constant processing rate
        sleep_time = max(0, POLL_INTERVAL - elapsed)
        time.sleep(sleep_time)

# ====================
# API Endpoints
# ====================

@app.get("/")
def dashboard(request: Request):
    """Render the dashboard."""
    with Session(engine) as session:
        # Fetch data for UI
        # We need to construct a robust view
        videos = session.exec(select(VideoFile).order_by(VideoFile.id)).all()
        workers = session.exec(select(WorkerNode)).all()
        
        # Prepare video list with active job info
        # This is inefficient N+1 but fine for ~1000 items on local DB
        video_list = []
        for v in videos:
            # Find latest pertinent job
            # We want current active one, or last completed/error
            # Simple heuristic: look for any queued/processing job
            active_job = session.exec(
                select(Job)
                .where(Job.video_id == v.id)
                .where(Job.status.in_(["queued", "processing"]))
            ).first()
            
            v_data = {
                "id": v.id,
                "filename": v.filename,
                "path": v.path,
                "size": v.size,
                "codec": v.codec,
                "duration": v.duration,
                "status": v.status, # Default from VideoFile
                "progress_pct": 0.0,
                "worker_str": "-"
            }
            
            if active_job:
                v_data["status"] = active_job.status
                v_data["progress_pct"] = active_job.progress_pct
                if active_job.worker_id:
                    # quick fetch
                    w = session.get(WorkerNode, active_job.worker_id)
                    if w: v_data["worker_str"] = w.name
            
            video_list.append(v_data)

        workers_data = [
            {"id": w.id, "name": w.name, "ip": w.ip, "port": w.port, "threads_capacity": w.threads_capacity, "enabled": w.enabled, "is_online": w.is_online}
            for w in workers
        ]

        return templates.TemplateResponse("index.html", {
            "request": request,
            "videos": video_list,
            "workers": workers_data
        })

@app.get("/api/state")
def get_state_api():
    """Return all database tables for dashboard synchronization."""
    with Session(engine) as session:
        # Videos
        videos = session.exec(select(VideoFile).order_by(VideoFile.id)).all()
        videos_data = [
            {
                "id": v.id,
                "path": v.path,
                "filename": v.filename,
                "size": v.size,
                "duration": v.duration,
                "frames": v.frames,
                "codec": v.codec,
                "status": v.status,
                "orig": v.orig
            }
            for v in videos
        ]
        
        # Jobs
        jobs = session.exec(select(Job).order_by(Job.id)).all()
        jobs_data = [
            {
                "id": j.id,
                "video_id": j.video_id,
                "worker_id": j.worker_id,
                "status": j.status,
                "progress_pct": j.progress_pct,
                "frames_processed": j.frames_processed,
                "fps": j.fps,
                "preset": j.preset,
                "crf": j.crf,
                "threads": j.threads,
                "created_at": j.created_at,
                "started_at": j.started_at,
                "completed_at": j.completed_at
            }
            for j in jobs
        ]
        
        # Workers
        workers = session.exec(select(WorkerNode)).all()
        workers_data = [
            {
                "id": w.id,
                "name": w.name,
                "ip": w.ip,
                "port": w.port,
                "enabled": w.enabled,
                "is_online": w.is_online,
                "threads_capacity": w.threads_capacity
            }
            for w in workers
        ]
        
    return {
        "videos": videos_data,
        "jobs": jobs_data,
        "workers": workers_data
    }

@app.post("/scan")
def trigger_scan(directory: str = None):
    path = directory or VIDEO_ROOT
    if not os.path.exists(path):
         raise HTTPException(400, "Directory does not exist")
    count = scanner.scan_directory_custom(path)
    return {"message": "Scan complete", "new_files": count}

@app.post("/queue/{video_id}")
def queue_video(
    video_id: int,
    crf: int = Form(DEFAULT_CRF),
    preset: str = Form(DEFAULT_PRESET)
):
    with Session(engine) as session:
        video = session.get(VideoFile, video_id)
        if not video:
            raise HTTPException(404, "Video not found")
        
        # Check if already has active job?
        active_job = session.exec(
            select(Job).where(Job.video_id == video.id).where(Job.status.in_(["queued", "processing"]))
        ).first()
        
        if active_job:
             # If user forces queue, maybe we should error or cancel old?
             # For simplicity now, error.
             raise HTTPException(400, "Video is already queued or processing")

        # Create Job
        job = Job(
            video_id=video.id,
            preset=preset,
            crf=crf,
            threads=0, # Deprecated/Worker managed
            status="queued",
            started_at=None,
            completed_at=None,
            frames_processed=0,
            fps=0.0
        )
        session.add(job)
        
        # Update Video status for quick UI feedback
        video.status = "queued"
        session.add(video)
        
        session.commit()
    return {"message": "Queued"}

@app.post("/jobs/stop/{video_id}")
def stop_job_api(video_id: int):
    """Stop the current job for a video."""
    with Session(engine) as session:
        active_job = session.exec(
            select(Job)
            .where(Job.video_id == video_id)
            .where(Job.status.in_(["queued", "processing", "paused"]))
        ).first()
        
        if not active_job:
            # Maybe just update video status just in case?
            v = session.get(VideoFile, video_id)
            if v and v.status != "completed":
                v.status = "pending"
                session.add(v)
                session.commit()
            return {"message": "No active job found"}

        # If queued, just delete job and reset video
        if active_job.status == "queued":
            session.delete(active_job)
            active_job.video.status = "pending"
            session.add(active_job.video)
            session.commit()
            return {"message": "Job cancelled"}

        # If processing/paused, tell worker
        worker = active_job.worker
        if worker and worker.is_online:
            try:
                requests.post(f"{worker.url}/jobs/stop/{active_job.id}", timeout=2)
            except Exception as e:
                print(f"Failed to stop job on worker: {e}")
        
        # Update DB
        active_job.status = "error" # User cancelled = error/stopped
        active_job.video.status = "pending"
        session.add(active_job)
        session.add(active_job.video)
        session.commit()
            
    return {"message": "Stopped"}

@app.post("/jobs/pause/{video_id}")
def pause_job_api(video_id: int):
    """Pause the current job."""
    with Session(engine) as session:
        active_job = session.exec(
            select(Job)
            .where(Job.video_id == video_id)
            .where(Job.status == "processing")
        ).first()
        
        if not active_job:
            raise HTTPException(400, "No processing job found")
            
        worker = active_job.worker
        if worker and worker.is_online:
            try:
                r = requests.post(f"{worker.url}/jobs/pause/{active_job.id}", timeout=2)
                if r.status_code == 200:
                    active_job.status = "paused"
                    active_job.video.status = "paused"
                    session.add(active_job)
                    session.add(active_job.video)
                    session.commit()
                    return {"message": "Paused"}
            except Exception as e:
                print(f"Failed to pause: {e}")
                raise HTTPException(500, "Failed to contact worker")
        
    raise HTTPException(500, "Worker offline or job lost")

@app.post("/jobs/resume/{video_id}")
def resume_job_api(video_id: int):
    """Resume the current job."""
    with Session(engine) as session:
        active_job = session.exec(
            select(Job)
            .where(Job.video_id == video_id)
            .where(Job.status == "paused")
        ).first()
        
        if not active_job:
            raise HTTPException(400, "No paused job found")
            
        worker = active_job.worker
        if worker and worker.is_online:
            try:
                r = requests.post(f"{worker.url}/jobs/resume/{active_job.id}", timeout=2)
                if r.status_code == 200:
                    active_job.status = "processing"
                    active_job.video.status = "processing"
                    session.add(active_job)
                    session.add(active_job.video)
                    session.commit()
                    return {"message": "Resumed"}
            except Exception as e:
                print(f"Failed to resume: {e}")
                raise HTTPException(500, "Failed to contact worker")

    raise HTTPException(500, "Worker offline or job lost")

@app.post("/workers")
def register_worker_api(
    name: str = Form(...),
    ip: str = Form(...),
    port: int = Form(8000),
    threads: int = Form(0)
):
    """Register a new worker."""
    w = add_worker(name, ip, port, threads)
    return {"message": "Worker added", "id": w.id}

@app.post("/workers/{worker_id}/toggle")
def toggle_worker(worker_id: int):
    with Session(engine) as session:
        w = session.get(WorkerNode, worker_id)
        if not w:
            raise HTTPException(404, "Worker not found")
        w.enabled = not w.enabled
        session.add(w)
        session.commit()
        return {"message": "Toggled", "enabled": w.enabled}

@app.delete("/workers/{worker_id}")
def delete_worker(worker_id: int):
    with Session(engine) as session:
        w = session.get(WorkerNode, worker_id)
        if not w:
            raise HTTPException(404, "Worker not found")
        
        # Optional: Check if busy?
        # For now, just delete. Jobs will be orphaned or handled by poller error.
        session.delete(w)
        session.commit()
        return {"message": "Deleted"}

@app.put("/workers/{worker_id}")
def update_worker(
    worker_id: int,
    name: str = Form(...),
    ip: str = Form(...),
    port: int = Form(...),
    threads: int = Form(...)
):
    with Session(engine) as session:
        w = session.get(WorkerNode, worker_id)
        if not w:
            raise HTTPException(404, "Worker not found")
        
        # Check IP collision if IP changed
        if w.ip != ip:
            existing = session.exec(select(WorkerNode).where(WorkerNode.ip == ip)).first()
            if existing:
                raise HTTPException(409, "IP already in use")
        
        w.name = name
        w.ip = ip
        w.port = port
        w.threads_capacity = threads
        session.add(w)
        session.commit()
        return {"message": "Updated"}

@app.delete("/videos/{video_id}")
def delete_video(video_id: int):
    """Delete a video from the database (does NOT delete file)."""
    with Session(engine) as session:
        # Check active jobs first
        active_job = session.exec(
            select(Job)
            .where(Job.video_id == video_id)
            .where(Job.status.in_(["queued", "processing", "paused"]))
        ).first()

        if active_job:
             # Stop it first
             if active_job.status == "queued":
                 session.delete(active_job)
             else:
                 # If running, stop worker
                 worker = active_job.worker
                 if worker and worker.is_online:
                     try:
                         requests.post(f"{worker.url}/jobs/stop/{active_job.id}", timeout=2)
                     except Exception as e:
                         print(f"Failed to stop job during video delete: {e}")
                 
                 session.delete(active_job)
        
        # Now delete video
        video = session.get(VideoFile, video_id)
        if not video:
            raise HTTPException(404, "Video not found")
            
        session.delete(video)
        session.commit()
        
    return {"message": "Video removed from database"}

@app.post("/videos/{video_id}/merge")
def merge_video(video_id: int):
    """Merge completed H.265 file with its original.
    
    This will:
    1. Delete the original source file from disk
    2. Rename the H.265 file to the original's name
    3. Remove both entries from the database
    """
    with Session(engine) as session:
        # Get the H.265 video
        h265_video = session.get(VideoFile, video_id)
        if not h265_video:
            raise HTTPException(404, "Video not found")
        
        # Must have an original reference
        if not h265_video.orig:
            raise HTTPException(400, "This video has no linked original")
        
        # Get the original video
        orig_video = session.get(VideoFile, h265_video.orig)
        if not orig_video:
            raise HTTPException(400, "Original video not found in database")
        
        # Construct full paths
        h265_path = os.path.join(VIDEO_ROOT, h265_video.path)
        orig_path = os.path.join(VIDEO_ROOT, orig_video.path)
        
        # Safety checks
        if not os.path.exists(h265_path):
            raise HTTPException(400, f"H.265 file not found on disk: {h265_video.path}")
        
        # Step 1: Delete original file (if exists)
        if os.path.exists(orig_path):
            try:
                os.remove(orig_path)
                print(f"Deleted original: {orig_path}")
            except Exception as e:
                raise HTTPException(500, f"Failed to delete original: {e}")
        
        # Step 2: Rename H.265 file to original's name
        try:
            os.rename(h265_path, orig_path)
            print(f"Renamed {h265_path} -> {orig_path}")
        except Exception as e:
            raise HTTPException(500, f"Failed to rename file: {e}")
        
        # Step 3: Delete both database entries
        # First delete any jobs associated with these videos
        session.exec(select(Job).where(Job.video_id == h265_video.id)).all()
        for job in session.exec(select(Job).where(Job.video_id == h265_video.id)).all():
            session.delete(job)
        for job in session.exec(select(Job).where(Job.video_id == orig_video.id)).all():
            session.delete(job)
        
        session.delete(h265_video)
        session.delete(orig_video)
        session.commit()
        
        print(f"Merged: {h265_video.filename} -> {orig_video.filename}")
    
    return {"message": "Merge complete"}

# ====================
# Startup
# ====================

@app.on_event("startup")
def startup():
    create_db_and_tables()
    
    t_dispatch = threading.Thread(target=dispatch_loop, daemon=True)
    t_dispatch.start()
    
    t_poll = threading.Thread(target=poll_loop, daemon=True)
    t_poll.start()


