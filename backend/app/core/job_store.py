"""In-memory job store for pipeline run status."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class JobStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    INGESTING = "ingesting"
    ANALYZING = "analyzing"
    SEGMENTING = "segmenting"
    SUMMARIZING = "summarizing"
    ASSEMBLING = "assembling"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


class LengthOption(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


@dataclass
class Job:
    id: str
    filename: str
    status: JobStatus = JobStatus.PENDING
    current_step: str = ""
    current_length: Optional[str] = None
    error: Optional[str] = None
    video_path: Optional[str] = None
    run_id: Optional[str] = None
    progress_pct: int = 0

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "status": self.status.value,
            "current_step": self.current_step,
            "current_length": self.current_length,
            "error": self.error,
            "video_path": self.video_path,
            "run_id": self.run_id,
            "progress_pct": self.progress_pct,
        }


_jobs: dict[str, Job] = {}


def create_job(filename: str) -> Job:
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, filename=filename)
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def update_job(
    job_id: str,
    status: Optional[JobStatus] = None,
    current_step: Optional[str] = None,
    current_length: Optional[str] = None,
    error: Optional[str] = None,
    video_path: Optional[str] = None,
    run_id: Optional[str] = None,
    progress_pct: Optional[int] = None,
) -> Optional[Job]:
    job = _jobs.get(job_id)
    if not job:
        return None
    if status is not None:
        job.status = status
    if current_step is not None:
        job.current_step = current_step
    if current_length is not None:
        job.current_length = current_length
    if error is not None:
        job.error = error
    if video_path is not None:
        job.video_path = video_path
    if run_id is not None:
        job.run_id = run_id
    if progress_pct is not None:
        job.progress_pct = min(100, max(0, progress_pct))
    return job


def list_jobs() -> list[Job]:
    return list(_jobs.values())
