# Pick-a-Print

Django + DRF app for saving, organizing, and searching 3D models from across the web.

## Quick start

### Docker (recommended — live reload)

```bash
docker compose up --build
```

Open http://127.0.0.1:8000/ — login **`dev`** / **`devdevdev`**

Services: `web`, `library-worker` (Django Celery), `api`, `worker` (scan pipeline + GPU), `db`, `redis`, `minio`, `frontend`

If port 8000 is in use: `WEB_PORT=8001 docker compose up --build`

Source is mounted (`./:/app`) — code changes reload automatically.

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate && python manage.py create_dev_token
# Terminal 1:
python manage.py runserver
# Terminal 2 (optional, for background metadata):
celery -A config worker -l info
```

## Features

| Feature | Description |
|---------|-------------|
| **Save from URL** | Web UI, API, browser extension |
| **STL upload** | Auto analysis: triangles, dimensions, volume |
| **Collections** | Organize like playlists |
| **Async metadata** | Celery fetches thumbnails/details in background |
| **Adapters** | Printables, MakerWorld, Thangs, generic Open Graph |
| **Mobile UI** | Hamburger nav, responsive grid |
| **Browser extension** | Floating Save button on supported sites |

## Web UI

- **Home** — Recently saved, stats
- **Save Model** — URL tab or STL upload tab
- **3D Scan** — Upload photos/video, track pipeline steps, logs, download STL
- **Settings** — API token for extension
- **Collections** — Create and browse

## API

Auth: `Authorization: Token <key>` (from Settings page or `create_dev_token`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/models/save/` | Save from URL |
| POST | `/api/models/upload/` | Upload STL (`multipart/form-data`, field `file`) |
| GET | `/api/models/recent/` | Last 12 saved |
| GET | `/api/models/search/?q=` | Search |
| CRUD | `/api/models/`, `/api/collections/` | Standard REST |

## Browser extension

See [extension/README.md](extension/README.md)

1. Settings page → copy API URL + token
2. `chrome://extensions` → Load unpacked → `extension/` folder
3. Visit Printables / MakerWorld / Thangs → click **Save to Library**

## Architecture

```
library/
├── adapters/       # Printables, MakerWorld, Thangs, OG fallback
├── tasks.py        # Celery: enrich metadata, analyze STL
├── stl_analysis.py # Triangle count, bbox, volume
├── services.py     # save_model_from_url / save_model_from_upload
└── web_views.py    # Session-based UI
```

## Model status

`saved` → `downloaded` → `printed` → `painted` → `gifted`

---

## Photogrammetry Pipeline (scan → STL)

Pipeline code lives in `app/` — Docker Compose is only the infrastructure.

### Architecture

```
Phone / Browser → FastAPI → Redis/Celery → GPU Worker
  → FFmpeg → COLMAP → OpenMVS → Trimesh → Blender → STL + GLB + report
```

### Phase 1 — Local CLI (start here)

```bash
pip install -r requirements-photogrammetry.txt

# Local CLI (requires colmap, ffmpeg, blender; OpenMVS optional):
python scan.py --input ./samples/cup --output ./results/cup
```

Outputs: `model.ply`, `model.obj`, `model.glb`, `model.stl`, `report.json`

Resume from a stage after failure:

```bash
python scan.py --input ./samples/cup --output ./results/cup --from-stage COLMAP_MAPPING
```

### Phase 2 — Single GPU container

```bash
docker build -f services/worker/Dockerfile -t photogrammetry-worker .
docker run --gpus all \
  -v ./samples/cup:/input \
  -v ./results/cup:/output \
  photogrammetry-worker
```

### Phase 3 — Full stack (same `docker compose up`)

Photogrammetry services run alongside the Django library app in the same Compose file:

```bash
docker compose up --build
```

| Service         | Port  | Role                              |
|-----------------|-------|-----------------------------------|
| web             | 8000  | Django library UI + API           |
| library-worker  | —     | Django Celery (metadata, STL)     |
| api             | 8001  | Scan upload, job status, downloads |
| worker          | —     | Scan pipeline Celery + GPU        |
| db              | —     | PostgreSQL (shared)               |
| redis           | —     | Task queue (db 0 = Django, 1 = scan) |
| minio           | 9000  | Object storage for scan artifacts |
| frontend        | 3000  | Scan upload UI + progress         |

API examples:

```bash
# Create job
curl -F "files=@photo1.jpg" -F "files=@photo2.jpg" http://localhost:8001/jobs/

# Poll status
curl http://localhost:8001/jobs/{job_id}

# Download STL
curl -O http://localhost:8001/results/{job_id}/model.stl
```

### Code layout

```
app/
├── api/           # FastAPI: uploads, jobs, results
├── pipeline/      # orchestrator.py, stages, workspace
├── engines/       # Adapters: colmap, openmvs, ffmpeg, trimesh, blender
├── quality/       # Image / reconstruction / mesh checks
├── workers/       # Celery tasks
├── storage/       # Local + MinIO
└── models/        # Job state, artifacts, stage enums
scan.py            # CLI entry point
```

### Pipeline stages

`UPLOADED` → `PREPROCESSING` → `COLMAP_FEATURES` → `COLMAP_MATCHING` →
`COLMAP_MAPPING` → `DENSE_RECONSTRUCTION` → `MESHING` → `REPAIRING` →
`EXPORTING` → `COMPLETED`

Each stage writes a marker file — failed jobs can resume without restarting from scratch.
