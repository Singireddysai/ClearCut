"""FastAPI application for ClearCut."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.app.core.config import UPLOAD_DIR, WORKSPACE_ROOT, ALLOWED_EXTENSIONS
from backend.app.core.job_store import get_job, create_job, update_job, list_jobs, JobStatus
from backend.app.runner import run_pipeline_for_job
from backend.app.api import jobs, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    yield
    # cleanup if needed


app = FastAPI(
    title="ClearCut API",
    description="Video summarization pipeline API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])


@app.get("/health")
def health():
    return {"status": "ok"}
