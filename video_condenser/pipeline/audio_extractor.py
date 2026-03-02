"""
Extract audio from video using ffmpeg.
Output: 16 kHz mono WAV suitable for Whisper.
"""
import logging
import subprocess
from pathlib import Path
from typing import Union

from ..config.settings import Settings, default_settings

logger = logging.getLogger(__name__)


def extract_audio(
    video_path: Union[str, Path],
    output_path: Union[str, Path, None] = None,
    settings: Union[Settings, None] = None,
) -> str:
    """
    Extract audio from video to WAV (16 kHz mono).
    Returns path to the created audio file.
    """
    settings = settings or default_settings
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if output_path is None:
        output_path = settings.audio_path
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        settings.ffmpeg_path,
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        str(output_path),
    ]
    logger.info("Extracting audio from %s -> %s", video_path, output_path)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg stderr: %s", result.stderr)
        raise RuntimeError(f"ffmpeg failed with code {result.returncode}: {result.stderr}")
    logger.info("Audio extracted successfully: %s", output_path)
    return str(output_path)
