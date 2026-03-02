# Video Condenser

Shorten videos by removing ads, filler speech, and redundant sections while keeping semantic continuity. Pipeline: extract audio → transcribe (Whisper) → summarize (HuggingFace) → match segments to summary (BGE embeddings + cosine similarity) → extract and merge clips (ffmpeg).

## Prerequisites

- **Python 3.10+**
- **ffmpeg** on PATH ([ffmpeg.org](https://ffmpeg.org/download.html))

## Installation

From the project root (parent of `video_condenser`):

```powershell
# Windows PowerShell
venv\Scripts\Activate.ps1
pip install -r video_condenser/requirements.txt
```

Or from inside `video_condenser`:

```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Example usage

Run from the **project root** (so `video_condenser` is a package):

```powershell
python video_condenser/main.py --input path/to/video.mp4 --output ./output
```

With options:

```powershell
python video_condenser/main.py --input video.mp4 --output ./out --threshold 0.78 --min-clip-duration 2.5 --merge-gap 1.0
```

Use OpenAI Whisper API (requires `OPENAI_API_KEY`):

```powershell
$env:OPENAI_API_KEY = "sk-..."
python video_condenser/main.py --input video.mp4 --output ./out --use-whisper-api
```

## Output

- `output_dir/audio.wav` – extracted audio
- `output_dir/transcript.json` – timestamped segments
- `output_dir/summary.txt` – condensed summary
- `output_dir/condensed_video.mp4` – final shortened video
- `output_dir/clips/` – temporary clips (removed after merge)

## Config

Key settings (override via CLI or edit `config/settings.py`):

| Setting | Default | Description |
|--------|---------|-------------|
| `--threshold` | 0.75 | Cosine similarity threshold (segment vs summary) |
| `--min-clip-duration` | 2.0 | Minimum clip length (seconds) |
| `--merge-gap` | 1.0 | Merge segments closer than this (seconds) |
| `--whisper-model` | base | Local Whisper size (tiny, base, small, medium, large) |

## Optional Streamlit UI

```powershell
streamlit run video_condenser/app_streamlit.py
```

Upload a video, set threshold and min clip duration, then run the pipeline and download the condensed video.
