"""Upload video and start processing."""
import asyncio
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks

from backend.app.core.config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_MB
from backend.app.core.job_store import create_job, update_job, JobStatus
from backend.app.runner import start_pipeline_background

router = APIRouter()


@router.post("/upload")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    job = create_job(filename=file.filename or "video")
    update_job(job.id, status=JobStatus.UPLOADING, current_step="Uploading")
    dest = UPLOAD_DIR / f"{job.id}{suffix}"
    try:
        content = await file.read()
        if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(400, detail=f"File too large (max {MAX_UPLOAD_MB} MB)")
        dest.write_bytes(content)
    except Exception as e:
        update_job(job.id, status=JobStatus.FAILED, error=str(e))
        raise HTTPException(500, detail=str(e))
    update_job(job.id, video_path=str(dest), run_id=job.id)
    background_tasks.add_task(start_pipeline_background, job.id, str(dest))
    return {"job_id": job.id, "filename": job.filename, "status": "pending"}
