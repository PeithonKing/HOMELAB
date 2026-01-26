# scanner.py
# Master Node - Video File Scanner

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from sqlmodel import Session, select
from database import engine, VideoFile, create_db_and_tables
from dotenv import load_dotenv

load_dotenv()

# ====================
# Configuration
# ====================

# Default root, can be overridden by function argument
VIDEO_ROOT = os.environ.get("VIDEO_ROOT", "./test")
MIN_SIZE_MB = 10
MIN_SIZE_BYTES = MIN_SIZE_MB * 1024 * 1024
MAX_SCAN_WORKERS = 4

# ====================
# FFprobe Functions
# ====================

def get_codec(filepath: str) -> str | None:
    """Returns codec name or None if not a video."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=nw=1:nk=1",
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception as e:
        pass
    return None


def get_duration(filepath: str) -> float:
    """Returns duration in seconds."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except:
        return 0.0


def get_frame_count(filepath: str, duration: float) -> int:
    """Calculates total frames from duration * avg_frame_rate."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate",
            "-of", "default=nw=1:nk=1",
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        fps_str = result.stdout.strip()
        
        if '/' in fps_str:
            num, den = map(int, fps_str.split('/'))
            if den > 0:
                fps = num / den
                return int(duration * fps)
    except:
        pass
    return 0


# ====================
# Scanning Functions
# ====================

def collect_candidates(root_dir: str) -> list:
    """Walk directory and collect candidate files."""
    candidates = []
    abs_root = os.path.abspath(root_dir)
    
    for dirpath, dirnames, filenames in os.walk(abs_root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        
        for filename in filenames:
            if filename.startswith('.'):
                continue
            
            ext = os.path.splitext(filename)[1].lower()
            if ext in ['.srt', '.txt', '.nfo', '.jpg', '.png', '.jpeg']:
                continue
            
            # if '_h265.' in filename:
            #     continue
            
            full_path = os.path.join(dirpath, filename)
            
            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue
            
            if size < MIN_SIZE_BYTES:
                continue
            
            # Calculate relative path
            rel_path = os.path.relpath(full_path, abs_root)
            candidates.append((full_path, filename, size, rel_path))
    
    return candidates


def probe_file(file_info: tuple) -> dict | None:
    """Probe a single file for metadata."""
    full_path, filename, size_bytes, rel_path = file_info
    
    codec = get_codec(full_path)
    if not codec:
        return None
    
    duration = get_duration(full_path)
    frames = get_frame_count(full_path, duration)
    
    return {
        "path": rel_path,
        "filename": filename,
        "size": size_bytes,
        "codec": codec,
        "duration": round(duration, 2),
        "frames": frames
    }


def scan_directory_custom(directory_path: str) -> int:
    """Main scanning function."""
    create_db_and_tables()
    
    with Session(engine) as session:
        existing_paths = set(
            session.exec(select(VideoFile.path)).all()
        )
    
    print(f"Scanning directory: {directory_path}")
    all_candidates = collect_candidates(directory_path)
    
    new_candidates = [
        c for c in all_candidates 
        if c[3] not in existing_paths
    ]
    
    print(f"Found {len(new_candidates)} new candidates")
    
    if not new_candidates:
        return 0
    
    print(f"Probing with {MAX_SCAN_WORKERS} workers...")
    new_files = []
    
    with ThreadPoolExecutor(max_workers=MAX_SCAN_WORKERS) as executor:
        for result in executor.map(probe_file, new_candidates):
            if result:
                new_files.append(result)
                print(f"  Found: {result['filename']} ({result['codec']})")
    
    with Session(engine) as session:
        for data in new_files:
            status = "pending"
            
            if data["codec"] in ("hevc", "h265"):
                status = "completed"
            
            # Dropped progress_pct as per schema change
            video = VideoFile(
                path=data["path"],
                filename=data["filename"],
                size=data["size"],
                codec=data["codec"],
                duration=data["duration"],
                frames=data["frames"],
                status=status
            )
            session.add(video)
        
        session.commit()
    
    print(f"Added {len(new_files)} new files to database")
    return len(new_files)


if __name__ == "__main__":
    import sys
    
    scan_root = VIDEO_ROOT
    if len(sys.argv) > 1:
        scan_root = sys.argv[1]
    
    print(f"Scanning: {scan_root}")
    count = scan_directory_custom(scan_root)
    print(f"Done. Added {count} files.")
