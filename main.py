import asyncio
import argparse
import sys
from app.pipeline import Pipeline

def main():
    parser = argparse.ArgumentParser(description="Extractive Video Summarization Pipeline")
    parser.add_argument("video_path", help="Path to the input video file")
    parser.add_argument("--l", type=str, default="medium", help="Summary length (default: medium)")
    parser.add_argument("--workspace", default="workspace", help="Workspace directory")
    
    args = parser.parse_args()
    
    pipeline = Pipeline(workspace_root=args.workspace)
    
    try:
        asyncio.run(pipeline.run(args.video_path, args.l))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
