"""
Optional Streamlit UI for Video Condenser.
Run from project root: streamlit run video_condenser/app_streamlit.py
"""
import sys
from pathlib import Path

# Ensure project root is on path
_APP_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _APP_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st
from video_condenser.config.settings import Settings, condensed_filename_for_input
from video_condenser.utils.logging_config import setup_logging
from video_condenser.pipeline.audio_extractor import extract_audio
from video_condenser.pipeline.transcriber import transcribe
from video_condenser.pipeline.summarizer import summarize_transcript
from video_condenser.pipeline.embedding_engine import EmbeddingEngine
from video_condenser.pipeline.matcher import match_segments
from video_condenser.pipeline.clip_extractor import extract_clips
from video_condenser.pipeline.merger import merge_clips

import logging
setup_logging(level=logging.INFO)


def run_pipeline_ui(video_path: str, settings: Settings) -> str:
    """Run pipeline and return output video path."""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    audio_path = extract_audio(video_path, settings=settings)
    segments = transcribe(audio_path, settings=settings)
    if not segments:
        raise ValueError("No transcript segments")
    summary = summarize_transcript(segments, settings=settings)
    engine = EmbeddingEngine(settings=settings)
    segment_embeddings = engine.encode_segments(segments)
    summary_embedding = engine.encode_summary(summary)
    spans = match_segments(segments, segment_embeddings, summary_embedding, settings=settings)
    if not spans:
        raise ValueError("No segments matched; try lowering threshold")
    clip_paths = extract_clips(str(video_path), spans, output_dir=str(clips_dir), settings=settings)
    out_path = merge_clips(clip_paths, output_path=settings.condensed_output_path, settings=settings, cleanup_clips=True)
    return out_path


def main():
    st.set_page_config(page_title="Video Condenser", layout="centered")
    st.title("Video Condenser")
    st.caption("Remove ads, filler, and redundancy; keep semantic continuity.")

    video_file = st.file_uploader("Upload video", type=["mp4", "mkv", "avi", "mov"])
    video_path_input = st.text_input("Or enter path to video file", placeholder="C:/path/to/video.mp4")

    threshold = st.slider("Similarity threshold", 0.5, 0.95, 0.75, 0.01)
    min_clip_duration = st.slider("Min clip duration (sec)", 0.5, 10.0, 2.0, 0.5)
    use_whisper_api = st.checkbox("Use OpenAI Whisper API (requires OPENAI_API_KEY)", False)

    if st.button("Condense video"):
        video_path = None
        if video_file:
            # Save upload to temp and use that path
            save_path = Path(".") / "output" / video_file.name
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(video_file.getvalue())
            video_path = str(save_path)
        elif video_path_input and Path(video_path_input).exists():
            video_path = video_path_input
        if not video_path:
            st.error("Please upload a video or provide a valid file path.")
            return

        settings = Settings(
            input_video=video_path,
            output_dir="./output",
            condensed_filename=condensed_filename_for_input(video_path),
            similarity_threshold=threshold,
            min_clip_duration_sec=min_clip_duration,
            use_whisper_api=use_whisper_api,
        )

        with st.spinner("Running pipeline (extract audio → transcribe → summarize → match → extract → merge)…"):
            try:
                out_path = run_pipeline_ui(video_path, settings)
                st.success(f"Done. Output: {out_path}")
                out_file = Path(out_path)
                if out_file.exists():
                    data = out_file.read_bytes()
                    st.download_button("Download condensed video", data=data, file_name=out_file.name, mime="video/mp4")
                with st.expander("Transcript & summary"):
                    import json
                    transcript_path = Path(settings.transcript_path)
                    if transcript_path.exists():
                        st.json(json.loads(transcript_path.read_text(encoding="utf-8")))
                    st.text_area("Summary", value=Path(settings.summary_path).read_text(encoding="utf-8") if Path(settings.summary_path).exists() else "")
            except Exception as e:
                st.error(str(e))
                raise


if __name__ == "__main__":
    main()
