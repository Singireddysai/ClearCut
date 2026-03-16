"""Background runner for the ClearCut pipeline with job status updates."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.app.core.job_store import (
    JobStatus,
    update_job,
)
from backend.app.core.config import WORKSPACE_ROOT

# Run pipeline in a thread so the FastAPI event loop stays free for GET /api/jobs, etc.
_POOL = ThreadPoolExecutor(max_workers=2)


def _run_pipeline_sync(job_id: str, video_path: str) -> None:
    """Run the async pipeline in a dedicated event loop inside a thread."""
    asyncio.run(run_pipeline_for_job(job_id, video_path))


async def start_pipeline_background(job_id: str, video_path: str) -> None:
    """Schedule pipeline in thread pool; returns immediately so API stays responsive."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_POOL, _run_pipeline_sync, job_id, video_path)


async def run_pipeline_for_job(job_id: str, video_path: str) -> None:
    """Run full pipeline (short, medium, long) for a job and update status."""
    from app.pipeline import Pipeline

    update_job(job_id, status=JobStatus.INGESTING, current_step="Ingestion", progress_pct=5)
    pipeline = Pipeline(workspace_root=str(WORKSPACE_ROOT))

    lengths = ["short", "medium", "long"]
    steps = 6  # ingestion, analysis, segmentation, then 3x (summarize+assemble+eval per length)
    total_steps = 6 + len(lengths) * 2  # rough: 6 shared + 2 per length
    step = 0

    def progress_for_step(s: int) -> int:
        return min(95, int(100 * s / total_steps))

    try:
        for i, length in enumerate(lengths):
            update_job(
                job_id,
                status=JobStatus.SUMMARIZING,
                current_step=f"Summarizing ({length})",
                current_length=length,
                progress_pct=progress_for_step(6 + i * 2),
            )
            await pipeline.run(video_path, length_option=length, run_id=job_id)
            step += 2

        update_job(job_id, status=JobStatus.COMPLETED, current_step="Done", progress_pct=100)
    except Exception as e:
        update_job(
            job_id,
            status=JobStatus.FAILED,
            error=str(e),
            current_step="Failed",
        )
        raise
