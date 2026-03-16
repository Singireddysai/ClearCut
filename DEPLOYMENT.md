# ClearCut — Deployment

## Quick start (local dev)

### 1. Environment

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY and GEMMA_API_KEY
```

### 2. Backend (FastAPI)

From the **project root** (ClearCut):

```bash
pip install -e .
pip install -r backend/requirements.txt

set PYTHONPATH=.
uvicorn backend.app.main:app --reload --port 8000
```

On Unix/macOS: `export PYTHONPATH=.` then run the uvicorn command.

### 3. Frontend (React)

**Node:** Use Node 20.19+ or 22.12+ if you hit Vite/Rolldown native binding issues.

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the backend.

---

## Docker

Backend image uses **uv** for fast installs and **CPU-only PyTorch** (no GPU/CUDA). No `torch` or `moviepy` in project deps; Docker installs CPU torch explicitly.

### Clean rebuild (remove all containers, volumes, images, networks, build cache)

From the project root:

```bash
docker compose down -v --rmi all --remove-orphans
docker network prune -f
docker builder prune -af
```

### Build and run

```bash
cp .env.example .env
# Set GROQ_API_KEY and GEMMA_API_KEY in .env

docker compose up --build
```

- Frontend: http://localhost:80
- Backend API: http://localhost:8000

---

## Project layout

```
ClearCut/
├── app/                    # Pipeline (transcription, vision, summarization, etc.)
├── backend/
│   ├── app/                # FastAPI app
│   │   ├── api/            # Routes: upload, jobs
│   │   ├── core/           # Config, job store
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # React + Vite + Tailwind + shadcn-style UI
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # UI and Aceternity-style components
│   │   ├── pages/
│   │   └── lib/
│   ├── nginx.conf          # Production: proxy /api to backend
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── DEPLOYMENT.md
```

---

## Production notes

- **CORS**: Backend allows `http://localhost:5173` and `http://127.0.0.1:5173`. For a custom frontend origin, set `CORS_ORIGINS` (or update `backend/app/main.py`).
- **Upload limit**: Default 500 MB; set `MAX_UPLOAD_MB` in `.env` or backend config.
- **Workspace**: Default `workspace/`; set `CLEARCUT_WORKSPACE` for Docker or production paths.
