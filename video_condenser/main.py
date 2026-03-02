"""
Video Condenser: full pipeline script.
Extract audio -> Transcribe -> Summarize -> Embed -> Match -> Extract clips -> Merge.
"""
import argparse
import sys
import time
from pathlib import Path

# Add project root (parent of video_condenser) so "video_condenser" package is found
_VIDEO_CONDENSER_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _VIDEO_CONDENSER_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from video_condenser.config.settings import Settings, condensed_filename_for_input
from video_condenser.utils.logging_config import setup_logging, get_logger
from video_condenser.pipeline.audio_extractor import extract_audio
from video_condenser.pipeline.transcriber import transcribe
from video_condenser.pipeline.summarizer import summarize_transcript
from video_condenser.pipeline.embedding_engine import EmbeddingEngine
from video_condenser.pipeline.matcher import match_segments
from video_condenser.pipeline.clip_extractor import extract_clips
from video_condenser.pipeline.merger import merge_clips

logger = get_logger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description="Video Condenser: shorten video by removing ads/filler.")
    p.add_argument("--input", "-i", required=True, help="Input video path")
    p.add_argument("--output", "-o", default="./output", help="Output directory (default: ./output)")
    p.add_argument("--threshold", "-t", type=float, default=None, help="Similarity threshold (default: 0.75)")
    p.add_argument("--min-clip-duration", type=float, default=None, help="Min clip duration in seconds (default: 2.0)")
    p.add_argument("--merge-gap", type=float, default=None, help="Merge segments within this gap in seconds (default: 1.0)")
    p.add_argument("--use-whisper-api", action="store_true", help="Use OpenAI Whisper API instead of local model")
    p.add_argument("--whisper-model", default=None, help="Local Whisper model (e.g. base, small)")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def run_pipeline(settings: Settings) -> str:
    """Run the full pipeline; returns path to condensed video."""
    video_path = Path(settings.input_video or "")
    if not video_path.exists():
        raise FileNotFoundError(f"Input video not found: {video_path}")

    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # 1) Extract audio
    logger.info("Step 1/7: Extracting audio")
    audio_path = extract_audio(video_path, settings=settings)

    # 2) Transcribe
    logger.info("Step 2/7: Transcribing")
    segments = transcribe(audio_path, settings=settings)
    if not segments:
        raise ValueError("Transcription produced no segments")

    # 3) Summarize
    logger.info("Step 3/7: Summarizing")
    summary = summarize_transcript(segments, settings=settings)

    # 4) Embeddings
    logger.info("Step 4/7: Generating embeddings")
    engine = EmbeddingEngine(settings=settings)
    segment_embeddings = engine.encode_segments(segments)
    summary_embedding = engine.encode_summary(summary)

    # 5) Match
    logger.info("Step 5/7: Matching segments to summary")
    spans = match_segments(segments, segment_embeddings, summary_embedding, settings=settings)
    if not spans:
        raise ValueError("No segments matched; try lowering --threshold")

    # 6) Extract clips
    logger.info("Step 6/7: Extracting clips")
    clip_paths = extract_clips(str(video_path), spans, output_dir=str(clips_dir), settings=settings)

    # 7) Merge
    logger.info("Step 7/7: Merging clips")
    out_path = merge_clips(clip_paths, output_path=settings.condensed_output_path, settings=settings, cleanup_clips=True)

    return out_path


def main():
    args = parse_args()
    import logging
    setup_logging(level=getattr(logging, args.log_level))

    settings = Settings(
        input_video=args.input,
        output_dir=args.output,
        condensed_filename=condensed_filename_for_input(args.input),
        use_whisper_api=args.use_whisper_api,
    )
    if args.threshold is not None:
        settings.similarity_threshold = args.threshold
    if args.min_clip_duration is not None:
        settings.min_clip_duration_sec = args.min_clip_duration
    if args.merge_gap is not None:
        settings.merge_gap_sec = args.merge_gap
    if args.whisper_model is not None:
        settings.whisper_model = args.whisper_model

    start = time.perf_counter()
    try:
        out_path = run_pipeline(settings)
        elapsed = time.perf_counter() - start
        logger.info("Done in %.1f s. Output: %s", elapsed, out_path)
        print(out_path)
        return 0
    except Exception as e:
        logger.exception("Pipeline failed")
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
