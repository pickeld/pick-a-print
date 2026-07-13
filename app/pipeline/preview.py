from __future__ import annotations

from pathlib import Path

MIN_IMAGES = 3
MIN_RESOLUTION = 480


def is_placeholder_mesh(ply_path: Path) -> bool:
    """Detect degenerate placeholder meshes (e.g. unit cube from old mock runs)."""
    if not ply_path.exists():
        return False
    try:
        import trimesh

        mesh = trimesh.load(str(ply_path), force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            return False
        return len(mesh.vertices) <= 8 and len(mesh.faces) <= 12
    except Exception:
        return ply_path.stat().st_size < 600


def count_frames(frames_dir: Path) -> int:
    if not frames_dir.exists():
        return 0
    exts = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
    return sum(1 for p in frames_dir.iterdir() if p.is_file() and p.suffix.lower() in exts)


def build_preview_warnings(
    *,
    frame_count: int,
    placeholder_mesh: bool,
    gpu_available: bool,
    registration_ratio: float | None = None,
    point_cloud_count: int | None = None,
) -> list[str]:
    warnings: list[str] = []
    if placeholder_mesh:
        warnings.append(
            "The generated mesh looks like a placeholder or failed reconstruction. "
            "Try more overlapping photos from different angles."
        )
    if frame_count and frame_count < 8:
        warnings.append(
            f"Only {frame_count} photo(s) found. Photogrammetry works best with at least 8 "
            "overlapping images from different angles."
        )
    if registration_ratio is not None and registration_ratio < 0.7:
        warnings.append(
            f"Only {registration_ratio:.0%} of frames aligned in 3D. "
            "Use a slower, steadier camera orbit with even lighting."
        )
    if point_cloud_count is not None and point_cloud_count < 2000:
        warnings.append(
            f"Sparse point cloud ({point_cloud_count} points) — mesh detail may be limited. "
            "GPU dense reconstruction improves results when available."
        )
    if not gpu_available:
        warnings.append(
            "No GPU/CUDA detected — using CPU photogrammetry. Dense reconstruction is skipped; "
            "mesh quality may be lower than on a GPU host."
        )
    return warnings
