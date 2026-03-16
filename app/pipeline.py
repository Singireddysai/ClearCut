import asyncio
import os
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv

from app.services.eval import get_metrics
from app.core.video_utils import VideoUtils
from app.services.transcription import TranscriptionService
from app.services.vision_analysis import VisionService
from app.services.segmentation import TopicProcessor
from app.services.summarizer import SummarizerService

load_dotenv()

# Global variable for the session/video hash
VIDEO_HASH = ""

def init_video_session(video_path: str):
    """Generates a unique MD5 hash for the video to be used as a global session ID."""
    global VIDEO_HASH
    abs_path = os.path.abspath(video_path)
    VIDEO_HASH = hashlib.md5(abs_path.encode()).hexdigest()
    return VIDEO_HASH

class Pipeline:
    def __init__(self, workspace_root: str = "workspace"):
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(exist_ok=True)

        self.groq_key = os.getenv("GROQ_API_KEY")
        self.gemma_key = os.getenv("GEMMA_API_KEY")

        if not self.groq_key:
            raise ValueError("API_KEY not found in environment.")

        self.transcriber = TranscriptionService(self.groq_key)
        self.vision = VisionService(self.gemma_key)
        self.topic_processor = TopicProcessor()
        self.summarizer = SummarizerService(self.gemma_key)

    async def run(self, video_path: str, length_option: str = "medium", run_id: str = None) -> str:
        # Use the global MD5 hash if no run_id is provided
        if not run_id:
            run_id = f"v_{init_video_session(video_path)}"
            
        run_dir = self.workspace_root / run_id
        run_dir.mkdir(exist_ok=True)

        print(f"Starting Pipeline Run (Session Hash): {run_id}")
        video_utils = VideoUtils(run_dir)

        # 1. Ingestion
        print("--- Step 1: Ingestion ---")
        expected_audio_path = run_dir / "audio.mp3"
        frames_dir = run_dir / "frames"

        if expected_audio_path.exists():
            print("  -> Cached audio found. Skipping extraction.")
            audio_path = str(expected_audio_path)
        else:
            print("  -> Extracting audio...")
            audio_path = video_utils.extract_audio(video_path)

        if frames_dir.exists() and any(frames_dir.iterdir()):
            print("  -> Cached frames found. Skipping extraction.")
            frame_paths = sorted([str(p) for p in frames_dir.glob("*.jpg")]) 
        else:
            print("  -> Extracting frames...")
            frame_paths = video_utils.extract_frames(video_path, interval=10)

        # 2. Parallel Analysis
        print("--- Step 2: Analysis ---")
        vision_context_path = run_dir / "vision_context.json"
        transcript_path = run_dir / "transcript.json"
        
        transcription, vision_results = await asyncio.gather(
            self.transcriber.transcribe(audio_path, context_file=str(transcript_path)),
            self.vision.process_frames(frame_paths, 10, context_file=str(vision_context_path))
        )
        if not transcript_path.exists():
            self.transcriber.save_transcription(transcription, str(transcript_path))
        
        # Only dump to JSON if it's a fresh run (VisionService handles loading internally)
        vision_data = [v.model_dump() for v in vision_results]
        if not vision_context_path.exists():
            with open(vision_context_path, "w", encoding="utf-8") as f:
                json.dump(vision_data, f, indent=2)

        # 3. Topic Segmentation
        print("--- Step 3: Semantic Topic Segmentation ---")
        enriched_blocks_path = run_dir / "enriched_blocks.json"
        if not enriched_blocks_path.exists():
            self.topic_processor.process_topics(
                transcript_json_path=str(transcript_path),
                vision_json_path=str(vision_context_path),
                output_path=str(enriched_blocks_path)
            )

        # 4. Summarization
        print(f"--- Step 4: Summarization (Length: {length_option}) ---")
        final_cuts_path = run_dir / f"{length_option}.txt"
        with open(enriched_blocks_path, "r", encoding="utf-8") as f:
            loaded_enriched_blocks = json.load(f)
        self.summarizer.run_pipeline(
            loaded_enriched_blocks,
            length=length_option,
            output_cuts_path=str(final_cuts_path)
        )

        # 5. Assembly
        print("--- Step 5: Assembly ---")
        output_video_path = run_dir / f"summary_{length_option}.mp4"

        video_utils.stitch_clips_from_file(
            video_path=video_path,
            cuts_txt_path=final_cuts_path,
            output_path=str(output_video_path)
        )

        print("--- Step 6: Evaluation ---")
        google_key = os.getenv("GEMMA_API_KEY") or os.getenv("GOOGLE_API_KEY") or self.gemma_key
        get_metrics(
            original_transcript_path=str(transcript_path),
            dir_path=str(run_dir),
            google_api_key=google_key or "",
        )

        print(f"Pipeline Complete: {output_video_path}")
        return str(output_video_path)