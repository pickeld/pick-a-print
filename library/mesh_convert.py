from __future__ import annotations

from pathlib import Path


class MeshConvertError(Exception):
    pass


def convert_mesh_to_stl(source: Path, dest: Path | None = None) -> Path:
    """Convert a mesh file (OBJ, etc.) to binary STL using trimesh."""
    source = Path(source)
    if not source.exists():
        raise MeshConvertError(f"Mesh file not found: {source}")

    dest = Path(dest) if dest else source.with_suffix(".stl")
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        import trimesh
    except ImportError as exc:
        raise MeshConvertError("Mesh conversion requires trimesh") from exc

    try:
        loaded = trimesh.load(str(source), force="mesh")
    except Exception as exc:
        raise MeshConvertError(f"Could not read mesh file: {exc}") from exc

    if isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise MeshConvertError("OBJ file contains no geometry")
        mesh = trimesh.util.concatenate(tuple(loaded.geometry.values()))
    else:
        mesh = loaded

    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
        raise MeshConvertError("Mesh has no triangle data to export as STL")

    try:
        mesh.export(str(dest), file_type="stl")
    except Exception as exc:
        raise MeshConvertError(f"STL export failed: {exc}") from exc

    if not dest.exists() or dest.stat().st_size == 0:
        raise MeshConvertError("STL export produced an empty file")

    return dest
