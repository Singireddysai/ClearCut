"""
Extract video clips for selected segments using ffmpeg.
Preserves original audio; outputs to temp dir for merger.
"""
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from ..config.settings import Settings, default_settings

logger = logging.getLogger(__name__)


def extract_clips(
    video_path: str,
    spans: List[Dict[str, float]],
    output_dir: str | None = None,
    settings: Settings | None = None,
) -> List[str]:
    """
    Extract one clip per span. Returns list of clip file paths in order.
    Uses -ss before -i for fast seek; -c copy to preserve audio/video.
    """
    settings = settings or default_settings
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="video_condenser_clips_")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    for i, span in enumerate(spans):
        start = float(span["start"])
        end = float(span["end"])
        duration = end - start
        if duration <= 0:
            continue
        clip_path = output_dir / f"clip_{i:04d}.mp4"
        cmd = [
            settings.ffmpeg_path,
            "-y",
            "-ss", str(start),
            "-i", str(video_path),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(clip_path),
        ]
        logger.debug("Extracting clip %s: %.1f-%.1f", clip_path.name, start, end)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("ffmpeg stderr: %s", result.stderr)
            raise RuntimeError(f"ffmpeg failed for clip {i}: {result.stderr}")
        clip_paths.append(str(clip_path))

    logger.info("Extracted %d clips to %s", len(clip_paths), output_dir)
    return clip_paths
