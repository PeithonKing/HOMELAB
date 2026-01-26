# worker_node.py
# H.265 Encoding Worker Node

import os
import re
import subprocess
import threading
import signal
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ====================
# Configuration
# ====================

MOUNT_ROOT = os.environ.get("H265_MOUNT", "./test")
LOG_DIR = "/tmp/h265_worker_logs"

# ====================
# Global State
# ====================

current_job: Optional[dict] = None
job_lock = threading.Lock()

def get_current_job():
    with job_lock:
        return current_job.copy() if current_job else None

def clear_current_job():
    global current_job
    with job_lock:
        current_job = None

# ====================
# Models
# ====================

class JobRequest(BaseModel):
    job_id: int
    rel_path: str
    preset: str = "medium"
    crf: int = 28
    threads: int = 0

# ====================
# FFmpeg
# ====================

def build_ffmpeg_command(input_path, output_path, crf, preset, threads):
    return [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx265",
        "-crf", str(crf),
        "-preset", preset,
        "-threads", str(threads),
        "-tag:v", "hvc1",
        "-c:a", "copy",
        output_path
    ]

# ====================
# Log Parsing
# ====================

FRAME_REGEX = re.compile(r"frame=\s*(\d+)")
FPS_REGEX = re.compile(r"fps=\s*([\d.]+)")
ENCODED_REGEX = re.compile(r"encoded\s+(\d+)\s+frames")

def parse_log(log_file: str) -> dict:
    """Parse FFmpeg log for progress."""
    result = {"status": "processing", "frames_done": 0, "fps": 0.0}
    
    if not os.path.exists(log_file):
        return result
    
    try:
        with open(log_file, "r") as f:
            for line in f.readlines()[::-1]:
                if line.strip():
                    content = line
                    break

        
        if ENCODED_REGEX.search(content):
            result["status"] = "completed"
            match = ENCODED_REGEX.search(content)
            if match:
                result["frames_done"] = int(match.group(1))
        else:
            for line in reversed(content.split('\r')):
                fm = FRAME_REGEX.search(line)
                fp = FPS_REGEX.search(line)
                if fm:
                    result["frames_done"] = int(fm.group(1))
                if fp:
                    try:
                        result["fps"] = float(fp.group(1))
                    except ValueError:
                        pass
                if fm or fp:
                    break
    except Exception as e:
        print(f"Error parsing log: {e}")
    
    return result

# ====================
# FastAPI App
# ====================

app = FastAPI(title="H265 Worker")

@app.get("/status")
def get_status():
    """Check if worker is idle or busy."""
    job = get_current_job()
    if job is None:
        return {"state": "idle"}
    return {"state": "busy", "job_id": job["job_id"]}

def _start_encoding_job(job_id: int, rel_path: str, input_path: str, crf: int, preset: str, threads: int):
    """Start encoding job with proper locking. Must be called with job_lock held."""
    global current_job
    
    # Check if worker is busy
    if current_job is not None:
        raise HTTPException(409, "Worker is busy with another job")
    
    # Prepare paths
    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_h265.mp4"
    
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"job_{job_id}.log")
    
    # Quote paths for shell safety
    quoted_input = f'"{input_path}"'
    quoted_output = f'"{output_path}"'
    
    cmd = build_ffmpeg_command(quoted_input, quoted_output, crf, preset, threads)
    
    # Build shell command with redirection
    cmd_str = ' '.join(cmd) + f' > "{log_file}" 2>&1'
    print(f"Starting FFmpeg: {cmd_str}", flush=True)
    
    # Use shell=True to let shell handle redirection
    # start_new_session=True creates a new process group for signal control
    proc = subprocess.Popen(cmd_str, shell=True, start_new_session=True)
    print(f"FFmpeg started with PID: {proc.pid} (process group)", flush=True)
    
    # Set global state
    current_job = {
        "job_id": job_id,
        "rel_path": rel_path,
        "input_path": input_path,
        "output_path": output_path,
        "log_file": log_file,
        "process": proc,
        "pid": proc.pid
    }
    
    return JSONResponse(status_code=202, content={
        "message": "Job accepted",
        "job_id": job_id, 
        "pid": proc.pid
    })

@app.post("/jobs")
def create_job(job: JobRequest):
    """Accept a new encoding job."""

    # 1. Validate File
    if ".." in job.rel_path:
         raise HTTPException(400, "Invalid path")
         
    input_path = os.path.join(MOUNT_ROOT, job.rel_path)
    if not os.path.exists(input_path):
         print(f"Worker Validation Error: File not found {input_path}", flush=True)
         raise HTTPException(400, f"File not found: {input_path}")
    
    # 2. Lock and Start
    with job_lock:
        return _start_encoding_job(
            job.job_id, 
            job.rel_path, 
            input_path, 
            job.crf, 
            job.preset, 
            job.threads
        )

@app.get("/jobs/info/{job_id}")
def get_job(job_id: int):
    """Get the status of a specific job."""
    job = get_current_job()
    
    if job is None or job["job_id"] != job_id:
        return {"status": "not_found", "frames_done": 0, "fps": 0.0}
    
    result = parse_log(job["log_file"])
    
    # Check if job completed
    if result["status"] == "completed":
        clear_current_job()
    elif job["process"].poll() is not None:
        # Process exited but no completion marker
        if job["process"].returncode != 0:
            result["status"] = "error"
        else:
            result["status"] = "completed"
        clear_current_job()
    
    return result

@app.post("/jobs/stop/{job_id}")
def stop_job(job_id: int):
    """Terminate a job and clean up partial files."""
    job = get_current_job()
    
    if not job or job["job_id"] != job_id:
        raise HTTPException(404, "Job not found or not active")
    
    process = job["process"]
    output_path = job.get("output_path")
    pgid = os.getpgid(process.pid)
    
    # Send SIGTERM to entire process group (shell + ffmpeg)
    try:
        if process.poll() is None:  # Still running
            os.killpg(pgid, signal.SIGTERM)
            process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # Force kill if doesn't respond
        os.killpg(pgid, signal.SIGKILL)
        process.wait()
    except Exception as e:
        print(f"Error terminating process group: {e}")
    
    # Delete partial output file
    if output_path and os.path.exists(output_path):
        try:
            os.remove(output_path)
            print(f"Deleted partial file: {output_path}")
        except Exception as e:
            print(f"Error deleting partial file: {e}")
    
    # Clear job state
    clear_current_job()
    
    return {"message": "Job stopped and cleaned up", "job_id": job_id}


@app.post("/jobs/pause/{job_id}")
def pause_job(job_id: int):
    """Pause a running job using SIGSTOP."""
    job = get_current_job()
    
    if not job or job["job_id"] != job_id:
        raise HTTPException(404, "Job not found or not active")
    
    process = job["process"]
    
    if process.poll() is not None:
        raise HTTPException(400, "Job is not running")
    
    try:
        pgid = os.getpgid(process.pid)
        os.killpg(pgid, signal.SIGSTOP)
        print(f"Job {job_id} paused (PGID: {pgid})")
        return {"message": "Job paused", "job_id": job_id, "pgid": pgid}
    except Exception as e:
        raise HTTPException(500, f"Failed to pause job: {e}")


@app.post("/jobs/resume/{job_id}")
def resume_job(job_id: int):
    """Resume a paused job using SIGCONT."""
    job = get_current_job()
    
    if not job or job["job_id"] != job_id:
        raise HTTPException(404, "Job not found or not active")
    
    process = job["process"]
    
    if process.poll() is not None:
        raise HTTPException(400, "Job is not running")
    
    try:
        pgid = os.getpgid(process.pid)
        os.killpg(pgid, signal.SIGCONT)
        print(f"Job {job_id} resumed (PGID: {pgid})")
        return {"message": "Job resumed", "job_id": job_id, "pgid": pgid}
    except Exception as e:
        raise HTTPException(500, f"Failed to resume job: {e}")
