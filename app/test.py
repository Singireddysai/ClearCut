from pathlib import Path
from services.eval import get_metrics
from dotenv import load_dotenv
import os
load_dotenv("D:\\ClearestCUt\\.env")
def main():
    workspace_path = Path("workspace").resolve()
    
    if not workspace_path.exists():
        print(f"Error: Workspace directory {workspace_path} not found.")
        return
    run_dirs = [d for d in workspace_path.iterdir() if d.is_dir() and d.name.startswith("v_")]
    
    if not run_dirs:
        print("No run directories (v_*) found in workspace.")
        return

    print(f"Found {len(run_dirs)} session folders. Starting metrics extraction...")

    for run_dir in run_dirs:
        print(f"\n>>> Processing Session: {run_dir.name}")
        
        # 3. Path to the original transcript required by eval.py
        original_transcript = run_dir / "transcript.json"
        
        if not original_transcript.exists():
            print(f"Skipping {run_dir.name}: transcript.json not found.")
            continue

        try:
            # 4. Trigger the metrics calculation
            # We pass the full run_dir so eval.py knows where to look for .txt and .mp4
            get_metrics(
                original_transcript_path=str(original_transcript),
                dir_path=str(run_dir),
                google_api_key=os.getenv("GEMMA_API_KEY")
            )
        except Exception as e:
            print(f"Failed to process {run_dir.name}: {e}")

    print("\nBatch evaluation complete. Check evaluation_results.csv for results.")

if __name__ == "__main__":
    main()