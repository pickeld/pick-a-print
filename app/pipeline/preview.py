from __future__ import annotations

import os
from pathlib import Path

MIN_IMAGES = 8
MOCK_BOX_VERTICES = 8
MOCK_BOX_FACES = 12


def is_mock_placeholder_mesh(ply_path: Path) -> bool:
    """Detect the default 1x1x1 mock cube (8 verts, 12 faces)."""
    if not ply_path.exists():
        return False
    try:
        import trimesh

        mesh = trimesh.load(str(ply_path), force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            return False
        return len(mesh.vertices) == MOCK_BOX_VERTICES and len(mesh.faces) == MOCK_BOX_FACES
    except Exception:
        return ply_path.stat().st_size < 600


def count_frames(frames_dir: Path) -> int:
    if not frames_dir.exists():
        return 0
    exts = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
    return sum(1 for p in frames_dir.iterdir() if p.is_file() and p.suffix.lower() in exts)


def pipeline_mock_enabled() -> bool:
    return os.getenv("PIPELINE_MOCK", "").lower() in ("1", "true", "yes")


def build_preview_warnings(
    *,
    mock_mode: bool,
    frame_count: int,
    placeholder_mesh: bool,
) -> list[str]:
    warnings: list[str] = []
    if mock_mode or placeholder_mesh:
        warnings.append(
            "Preview is a placeholder cube — photogrammetry did not run. "
            "Set PIPELINE_MOCK=false and use a Linux machine with GPU/COLMAP for a real model."
        )
    if frame_count and frame_count < MIN_IMAGES:
        warnings.append(
            f"Only {frame_count} photo(s) found. Photogrammetry works best with at least {MIN_IMAGES} "
            "overlapping images from different angles."
        )
    return warnings
