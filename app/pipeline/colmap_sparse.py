from __future__ import annotations

import struct
from pathlib import Path


def best_sparse_model_dir(sparse_dir: Path) -> Path | None:
    """Pick the sparse model with the most registered images (COLMAP may emit fragments)."""
    models = [p for p in sparse_dir.iterdir() if p.is_dir() and (p / "images.bin").exists()]
    if not models:
        return None
    return max(models, key=lambda model_dir: read_sparse_stats(model_dir)[0])


def read_sparse_stats(model_dir: Path) -> tuple[int, int]:
    """Return (registered_images, points3d) from COLMAP binary model files."""
    registered = 0
    points = 0

    images_bin = model_dir / "images.bin"
    if images_bin.exists():
        try:
            with images_bin.open("rb") as handle:
                registered = struct.unpack("<Q", handle.read(8))[0]
        except OSError:
            registered = 0

    points_bin = model_dir / "points3D.bin"
    if points_bin.exists():
        try:
            with points_bin.open("rb") as handle:
                points = struct.unpack("<Q", handle.read(8))[0]
        except OSError:
            points = 0

    return registered, points
