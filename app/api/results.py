from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.storage import get_storage

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/{job_id}/{filename}")
async def download_result(job_id: str, filename: str) -> FileResponse:
    storage = get_storage()
    ws = storage.workspace(job_id)
    path = ws.output_dir / filename

    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")

    # Prevent path traversal
    try:
        path.resolve().relative_to(ws.output_dir.resolve())
    except ValueError as exc:
        raise HTTPException(400, "Invalid filename") from exc

    media_types = {
        ".stl": "model/stl",
        ".glb": "model/gltf-binary",
        ".ply": "application/octet-stream",
        ".obj": "text/plain",
        ".json": "application/json",
    }
    return FileResponse(path, media_type=media_types.get(path.suffix.lower(), "application/octet-stream"))
