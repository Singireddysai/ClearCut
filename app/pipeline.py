import asyncio
import os
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv

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
        self.summarizer = SummarizerService(self.groq_key)

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
        audio_path = video_utils.extract_audio(video_path)
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
        self.topic_processor.process_topics(
            transcript_json_path=str(transcript_path),
            vision_json_path=str(vision_context_path),
            output_path=str(enriched_blocks_path)
        )

        # 4. Summarization
        print(f"--- Step 4: Summarization (Length: {length_option}) ---")
        final_cuts_json_path = run_dir / "final_cuts.json"
        cuts_txt_path = run_dir / "cuts.txt"
        
        final_cuts = self.summarizer.run_pipeline(
            enriched_json_path=str(enriched_blocks_path),
            length=length_option,
            output_cuts_path=str(final_cuts_json_path)
        )

        # Map JSON blocks to the simple comma-separated text file expected by VideoUtils
        with open(cuts_txt_path, "w", encoding="utf-8") as f:
            for cut in final_cuts:
                f.write(f"{cut['start']},{cut['end']}\n")

        # 5. Assembly
        print("--- Step 5: Assembly ---")
        output_video_path = run_dir / "summary_output.mp4"

        video_utils.stitch_clips_from_file(
            video_path=video_path,
            cuts_txt_path=cuts_txt_path,
            output_path=str(output_video_path)
        )

        print(f"Pipeline Complete: {output_video_path}")
        return str(output_video_path)