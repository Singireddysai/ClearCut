"""
Central configuration for the Video Condenser pipeline.
Paths, model names, and thresholds; load from env or override via CLI.
"""
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


def condensed_filename_for_input(input_video_path: str) -> str:
    """Build output name: condensed_<input_stem>_<YYYYmmdd_HHMM>.mp4"""
    stem = Path(input_video_path).stem
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    return f"condensed_{stem}_{ts}.mp4"

# Load .env from video_condenser dir so it works when run from project root
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
    load_dotenv()  # also allow cwd .env override
except ImportError:
    pass


@dataclass
class Settings:
    """Pipeline settings. Override attributes after loading for CLI overrides."""

    # --- Paths ---
    input_video: Optional[str] = None
    output_dir: str = "./output"
    audio_filename: str = "audio.wav"
    transcript_filename: str = "transcript.json"
    summary_filename: str = "summary.txt"
    condensed_filename: str = "condensed_video.mp4"

    # --- Whisper ---
    use_whisper_api: bool = False
    whisper_model: str = "base"  # local: tiny, base, small, medium, large
    whisper_api_model: str = "whisper-1"
    # OpenRouter/proxies often < 25 MB; chunk when larger. Env WHISPER_API_MAX_FILE_MB overrides.
    whisper_api_max_file_mb: float = 4.0

    # --- Summarizer ---
    summarization_model: str = "facebook/bart-large-cnn"  # used when not using LLM
    summarization_llm_model: str = "openai/gpt-oss-20b"   # OpenRouter model for summarization
    use_llm_summarization: bool = True                   # use LLM (OpenRouter) when API key set
    summarization_max_length: int = 150
    summarization_min_length: int = 30
    transcript_chunk_size: int = 4000  # chars per chunk for long transcripts

    # --- Embeddings ---
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_batch_size: int = 32
    normalize_embeddings: bool = True

    # --- Matcher ---
    similarity_threshold: float = 0.75
    min_clip_duration_sec: float = 2.0
    merge_gap_sec: float = 1.0
    redundancy_similarity_threshold: Optional[float] = 0.92  # segment-to-segment dedup

    # --- FFmpeg ---
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    def __post_init__(self) -> None:
        self.output_dir = os.path.abspath(self.output_dir)

    @property
    def audio_path(self) -> str:
        return str(Path(self.output_dir) / self.audio_filename)

    @property
    def transcript_path(self) -> str:
        return str(Path(self.output_dir) / self.transcript_filename)

    @property
    def summary_path(self) -> str:
        return str(Path(self.output_dir) / self.summary_filename)

    @property
    def condensed_output_path(self) -> str:
        return str(Path(self.output_dir) / self.condensed_filename)

    def get_openai_api_key(self) -> Optional[str]:
        return os.environ.get("OPENAI_API_KEY") or os.environ.get("OPEN_API_KEY")

    def get_openai_base_url(self) -> Optional[str]:
        return os.environ.get("BASE_URL") or os.environ.get("OPENAI_BASE_URL")


# Default singleton; main.py / app can replace or override attributes
default_settings = Settings()
