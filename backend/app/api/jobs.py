"""Job status and outputs."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.core.config import WORKSPACE_ROOT
from backend.app.core.job_store import get_job, list_jobs

router = APIRouter()


@router.get("")
def list_jobs_handler():
    jobs = list_jobs()
    return {"jobs": [j.to_dict() for j in reversed(jobs)]}


@router.get("/{job_id}")
def get_job_handler(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    return job.to_dict()


@router.get("/{job_id}/outputs")
def get_outputs_handler(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    run_dir = WORKSPACE_ROOT / job_id
    if not run_dir.exists():
        return {"job_id": job_id, "outputs": [], "transcripts": []}
    outputs = []
    transcripts = []
    for name in ["short", "medium", "long"]:
        vid = run_dir / f"summary_{name}.mp4"
        txt = run_dir / f"{name}_transcript.txt"
        if vid.exists():
            outputs.append({"length": name, "video": f"/api/jobs/{job_id}/download/{name}", "filename": vid.name})
        if txt.exists():
            transcripts.append({"length": name, "transcript": f"/api/jobs/{job_id}/transcript/{name}", "filename": txt.name})
    return {"job_id": job_id, "outputs": outputs, "transcripts": transcripts}


@router.get("/{job_id}/download/{length}")
def download_video(job_id: str, length: str):
    if length not in ("short", "medium", "long"):
        raise HTTPException(400, detail="Invalid length")
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    path = WORKSPACE_ROOT / job_id / f"summary_{length}.mp4"
    if not path.exists():
        raise HTTPException(404, detail="Video not ready")
    return FileResponse(path, filename=f"summary_{length}.mp4", media_type="video/mp4")


@router.get("/{job_id}/transcript/{length}")
def get_transcript(job_id: str, length: str):
    if length not in ("short", "medium", "long"):
        raise HTTPException(400, detail="Invalid length")
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    path = WORKSPACE_ROOT / job_id / f"{length}_transcript.txt"
    if not path.exists():
        raise HTTPException(404, detail="Transcript not ready")
    return FileResponse(path, filename=f"{length}_transcript.txt", media_type="text/plain")
