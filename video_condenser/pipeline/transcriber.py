"""
Transcribe audio using OpenAI Whisper (local or API).
Output: list of {start, end, text} in JSON-friendly format.
API has a 25 MB limit; we chunk large audio and merge segments with time offsets.
"""
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, List, Dict

from ..config.settings import Settings, default_settings

logger = logging.getLogger(__name__)

# 16 kHz mono 16-bit WAV ≈ 32 KB/s; 20 MB ≈ 600 s
def _duration_sec_for_mb(mb: float) -> float:
    return (mb * 1024 * 1024) / (16000 * 2)


def _get_audio_duration_sec(audio_path: str, ffprobe: str = "ffprobe") -> float:
    """Get duration in seconds via ffprobe."""
    cmd = [
        ffprobe,
        "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip())


def _segments_to_list(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize Whisper segments to [{start, end, text}, ...]."""
    out = []
    for s in segments:
        start = float(s.get("start", 0))
        end = float(s.get("end", start))
        if "duration" in s and "end" not in s:
            end = start + float(s["duration"])
        text = (s.get("text") or "").strip()
        out.append({"start": start, "end": end, "text": text})
    return out


def transcribe(
    audio_path: str,
    output_json_path: str | None = None,
    settings: Settings | None = None,
) -> List[Dict[str, Any]]:
    """
    Transcribe audio to timestamped segments.
    Uses local Whisper or OpenAI API based on settings.use_whisper_api.
    Returns list of {"start": float, "end": float, "text": str}.
    """
    settings = settings or default_settings
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if output_json_path is None:
        output_json_path = settings.transcript_path
    Path(output_json_path).parent.mkdir(parents=True, exist_ok=True)

    if settings.use_whisper_api:
        segments = _transcribe_api(str(audio_path), settings)
    else:
        segments = _transcribe_local(str(audio_path), settings)

    segments = _segments_to_list(segments)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)
    logger.info("Transcript saved to %s (%d segments)", output_json_path, len(segments))
    return segments


def _transcribe_local(audio_path: str, settings: Settings) -> List[Dict[str, Any]]:
    """Use openai-whisper local model."""
    import whisper
    logger.info("Loading Whisper model: %s", settings.whisper_model)
    model = whisper.load_model(settings.whisper_model)
    logger.info("Transcribing %s", audio_path)
    result = model.transcribe(audio_path, language=None, fp16=False)
    segments = result.get("segments") or []
    return segments


def _transcribe_api(audio_path: str, settings: Settings) -> List[Dict[str, Any]]:
    """Use OpenAI Whisper API; chunk audio if over size limit (25 MB), then merge segments."""
    from openai import OpenAI

    api_key = settings.get_openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY or OPEN_API_KEY not set; required for Whisper API")
    kwargs = {"api_key": api_key}
    base_url = settings.get_openai_base_url()
    if base_url:
        kwargs["base_url"] = base_url.rstrip("/")
    client = OpenAI(**kwargs)

    try:
        env_mb = os.environ.get("WHISPER_API_MAX_FILE_MB")
        max_bytes = int(float(env_mb or settings.whisper_api_max_file_mb) * 1024 * 1024)
    except (ValueError, TypeError):
        max_bytes = int(settings.whisper_api_max_file_mb * 1024 * 1024)
    file_size = Path(audio_path).stat().st_size

    # Use single request only when file is safely under limit (avoid 413 from OpenRouter/proxies)
    if file_size <= max_bytes:
        return _transcribe_api_single(client, audio_path, settings, offset_sec=0.0)

    # Chunk audio: get duration, split by time, transcribe each chunk, merge with offsets
    duration_sec = _get_audio_duration_sec(audio_path, settings.ffprobe_path)
    chunk_duration = _duration_sec_for_mb(settings.whisper_api_max_file_mb)
    all_segments: List[Dict[str, Any]] = []
    tmp_dir = tempfile.mkdtemp(prefix="whisper_chunks_")

    try:
        start = 0.0
        chunk_idx = 0
        while start < duration_sec:
            take = min(chunk_duration, duration_sec - start)
            chunk_path = Path(tmp_dir) / f"chunk_{chunk_idx:04d}.wav"
            cmd = [
                settings.ffmpeg_path, "-y",
                "-ss", str(start),
                "-i", audio_path,
                "-t", str(take),
                "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(chunk_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("ffmpeg chunk failed: %s", result.stderr)
                start += take
                chunk_idx += 1
                continue
            logger.info("Transcribing API chunk %d (%.1f–%.1f s)", chunk_idx, start, start + take)
            segs = _transcribe_api_single(client, str(chunk_path), settings, offset_sec=start)
            all_segments.extend(segs)
            chunk_path.unlink(missing_ok=True)
            start += take
            chunk_idx += 1
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return all_segments


def _transcribe_api_single(
    client, audio_path: str, settings: Settings, offset_sec: float = 0.0
) -> List[Dict[str, Any]]:
    """Call Whisper API for one file; add offset_sec to segment start/end."""
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=f,
            model=settings.whisper_api_model,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    segments = getattr(response, "segments", None) or []
    if offset_sec != 0:
        for s in segments:
            s["start"] = float(s.get("start", 0) or 0) + offset_sec
            s["end"] = float(s.get("end") or s.get("start", 0) or 0) + offset_sec
            if "duration" in s:
                s["duration"] = float(s["duration"])
    return segments
