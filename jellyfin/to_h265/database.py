# database.py
# Master Node - Database Models and Setup

from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, create_engine, Session, select, Relationship
from sqlalchemy import event

# ====================
# Models
# ====================

class VideoFile(SQLModel, table=True):
    """Represents a source video file."""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    path: str = Field(index=True, unique=True)  # Relative to VIDEO_ROOT
    filename: str
    size: int
    
    # Metadata
    duration: float = Field(default=0.0)
    frames: int = Field(default=0)
    codec: str = Field(default="unknown")
    
    # High-level status for UI filtering (computed/synced from latest job)
    status: str = Field(default="pending", index=True)  # queued, processing, completed
    
    # Relationships
    jobs: List["Job"] = Relationship(back_populates="video")
    orig: Optional[int] = Field(default=None, foreign_key="videofile.id")

    def __repr__(self):
        return f"VideoFile(id={self.id}, filename={self.filename})"


class WorkerNode(SQLModel, table=True):
    """Represents a registered worker."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    ip: str  # Not unique - same IP can have multiple ports
    port: int = Field(default=8000)
    enabled: bool = Field(default=True)
    is_online: bool = Field(default=False)
    
    # Capacity settings
    threads_capacity: int = Field(default=0) # 0 = Auto/Max
    
    # Relationships
    jobs: List["Job"] = Relationship(back_populates="worker")

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}"


class Job(SQLModel, table=True):
    """Represents a specific encoding task."""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Foreign Keys
    video_id: int = Field(foreign_key="videofile.id")
    worker_id: Optional[int] = Field(default=None, foreign_key="workernode.id")
    
    # Job Status
    status: str = Field(default="queued", index=True)
    # queued, processing, completed, error
    
    # Progress
    progress_pct: float = Field(default=0.0)
    frames_processed: int = Field(default=0)
    fps: float = Field(default=0.0)
    
    # Job Settings (Snapshot at creation)
    preset: str = Field(default="medium") 
    crf: int = Field(default=28)
    threads: int = Field(default=0) # 0 = Use worker default/max
    
    # Timestamps
    created_at: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    started_at: Optional[int] = Field(default=None)
    completed_at: Optional[int] = Field(default=None)
    
    # Relationships
    video: VideoFile = Relationship(back_populates="jobs")
    worker: Optional[WorkerNode] = Relationship(back_populates="jobs")

    @property
    def duration_formatted(self):
        if self.video and self.video.duration:
             # Convert seconds to HH:MM:SS
             m, s = divmod(self.video.duration, 60)
             h, m = divmod(m, 60)
             return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
        return "00:00:00"


# ====================
# Database Setup
# ====================

DATABASE_FILE = "videos.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"
engine = create_engine(
    DATABASE_URL, 
    echo=False, 
    connect_args={"timeout": 10}
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)

# ====================
# Helpers
# ====================

def get_all_videos():
    with Session(engine) as session:
        return session.exec(select(VideoFile)).all()

def get_active_workers():
    with Session(engine) as session:
        return session.exec(select(WorkerNode).where(WorkerNode.enabled == True)).all()

def add_worker(name: str, ip: str, port: int = 8000, threads: int = 0):
    with Session(engine) as session:
        # Check if exists (IP:PORT combination must be unique)
        worker = session.exec(
            select(WorkerNode).where(
                WorkerNode.ip == ip,
                WorkerNode.port == port
            )
        ).first()
        
        if worker:
            # Update existing
            worker.name = name
            worker.threads_capacity = threads
            worker.enabled = True
        else:
            # Create new
            worker = WorkerNode(name=name, ip=ip, port=port, threads_capacity=threads)
            session.add(worker)
            
        session.commit()
        session.refresh(worker)
        return worker
