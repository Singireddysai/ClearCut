import asyncio
import sys
from pathlib import Path
from app.pipeline import Pipeline

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

async def process_video(pipeline: Pipeline, video_path: Path):
    for length in ("short", "medium", "long"):
        print(f"\n>>> [{video_path.name}] Running: {length.upper()}")
        try:
            await pipeline.run(str(video_path), length_option=length)
        except Exception as e:
            print(f"Error processing {video_path.name} ({length}): {e}", file=sys.stderr)

async def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <video_file_or_directory>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    
    if not input_path.exists():
        print(f"Path does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    video_files = []

    if input_path.is_file():
        if input_path.suffix.lower() in VIDEO_EXTENSIONS:
            video_files = [input_path]
        else:
            print(f"File is not a supported video extension {VIDEO_EXTENSIONS}: {input_path}", file=sys.stderr)
            sys.exit(1)
            
    elif input_path.is_dir():
        video_files = [f for f in sorted(input_path.iterdir()) if f.suffix.lower() in VIDEO_EXTENSIONS]
        if not video_files:
            print(f"No video files found in directory: {input_path}")
            sys.exit(0)

    print(f"Found {len(video_files)} video(s). Running all 3 length options each.\n")

    pipeline = Pipeline()

    for video_path in video_files:
        await process_video(pipeline, video_path)

if __name__ == "__main__":
    asyncio.run(main())