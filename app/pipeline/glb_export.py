from __future__ import annotations

from pathlib import Path


MIN_VALID_GLB_BYTES = 100


def is_valid_glb(path: Path) -> bool:
    if not path.exists():
        return False
    if path.stat().st_size < MIN_VALID_GLB_BYTES:
        return False
    header = path.read_bytes()[:4]
    return header == b"glTF"


def export_glb_from_ply(ply_path: Path, glb_path: Path, obj_path: Path | None = None) -> Path:
    """Build a valid GLB from PLY. Falls back to a unit box if PLY cannot be loaded."""
    import trimesh

    glb_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        mesh = trimesh.load(str(ply_path), force="mesh")
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
            raise ValueError("not a valid triangle mesh")
    except Exception:
        mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])

    mesh.export(str(glb_path))
    if obj_path is not None:
        mesh.export(str(obj_path))
    return glb_path


def ensure_glb_from_ply(ply_path: Path, glb_path: Path, obj_path: Path | None = None) -> Path:
    """Return existing GLB or regenerate from PLY when missing/invalid."""
    if is_valid_glb(glb_path):
        return glb_path
    return export_glb_from_ply(ply_path, glb_path, obj_path)
