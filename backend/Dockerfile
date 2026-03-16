# Build from project root: docker build -f backend/Dockerfile .
# CPU-only, no GPU/CUDA. Uses uv for fast installs.
FROM python:3.11-slim

WORKDIR /app

# FFmpeg for audio/video
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl && rm -rf /var/lib/apt/lists/*

# Install uv (fast pip replacement)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install CPU-only PyTorch first (no CUDA) so sentence-transformers & bert-score use it
RUN uv pip install --system --no-cache torch --index-url https://download.pytorch.org/whl/cpu

# Copy project and install with uv (reuses existing torch)
COPY . .
RUN uv pip install --system --no-cache -e . && uv pip install --system --no-cache -r backend/requirements.txt

# Pre-download NLTK data so container has it at runtime (no network needed)
RUN python -c "import nltk; nltk.download('punkt_tab'); nltk.download('punkt')"

ENV PYTHONPATH=/app
ENV CLEARCUT_WORKSPACE=/app/workspace

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
