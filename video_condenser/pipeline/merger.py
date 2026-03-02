"""
Merge clip files into a single video using ffmpeg concat demuxer.
Cleans up temp clip files after merge (optional).
"""
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from ..config.settings import Settings, default_settings

logger = logging.getLogger(__name__)


def merge_clips(
    clip_paths: List[str],
    output_path: str | None = None,
    settings: Settings | None = None,
    cleanup_clips: bool = True,
) -> str:
    """
    Concatenate clips via ffmpeg concat demuxer (-f concat -safe 0).
    Returns path to the merged video. All clips must share same codecs for -c copy.
    """
    settings = settings or default_settings
    if not clip_paths:
        raise ValueError("No clip paths provided")
    if output_path is None:
        output_path = settings.condensed_output_path
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Concat list file: "file 'path'"
    list_dir = output_path.parent
    list_path = list_dir / "concat_list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for p in clip_paths:
            # Escape single quotes in path for ffmpeg
            escaped = str(Path(p).resolve()).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    cmd = [
        settings.ffmpeg_path,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        str(output_path),
    ]
    logger.info("Merging %d clips -> %s", len(clip_paths), output_path)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg stderr: %s", result.stderr)
        raise RuntimeError(f"ffmpeg merge failed: {result.stderr}")

    if cleanup_clips:
        for p in clip_paths:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError as e:
                logger.warning("Could not remove clip %s: %s", p, e)
        try:
            list_path.unlink(missing_ok=True)
        except OSError:
            pass

    logger.info("Merged video saved: %s", output_path)
    return str(output_path)
