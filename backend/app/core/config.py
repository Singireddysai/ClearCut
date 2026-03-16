"""App config from environment."""
import os
from pathlib import Path

WORKSPACE_ROOT = Path(os.getenv("CLEARCUT_WORKSPACE", "workspace"))
UPLOAD_DIR = WORKSPACE_ROOT / "uploads"
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
