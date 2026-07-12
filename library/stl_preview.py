from __future__ import annotations

import shutil
from pathlib import Path

from app.pipeline.glb_export import is_valid_glb


def preview_glb_path(stl_path: Path) -> Path:
    return stl_path.with_suffix(".glb")


def export_glb_from_stl(stl_path: Path, glb_path: Path) -> Path:
    import trimesh
    from trimesh.visual.material import PBRMaterial

    glb_path.parent.mkdir(parents=True, exist_ok=True)
    mesh = trimesh.load(str(stl_path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
        raise ValueError("not a valid triangle mesh")

    # Neutral blue-gray material — avoids face_colors (needs scipy) while still looking shaded.
    mesh.visual.material = PBRMaterial(
        baseColorFactor=[0.75, 0.78, 0.82, 1.0],
        metallicFactor=0.1,
        roughnessFactor=0.65,
    )
    mesh.export(str(glb_path), file_type="glb")
    return glb_path


def export_glb_from_mesh_file(mesh_path: Path, glb_path: Path) -> Path:
    """Build a preview GLB from any trimesh-supported mesh file (STL, 3MF, etc.)."""
    import trimesh
    from trimesh.visual.material import PBRMaterial

    glb_path.parent.mkdir(parents=True, exist_ok=True)
    loaded = trimesh.load(str(mesh_path), force="mesh")
    if isinstance(loaded, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(loaded.geometry.values()))
    else:
        mesh = loaded
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
        raise ValueError("not a valid triangle mesh")

    if not getattr(mesh.visual, "material", None):
        mesh.visual.material = PBRMaterial(
            baseColorFactor=[0.75, 0.78, 0.82, 1.0],
            metallicFactor=0.1,
            roughnessFactor=0.65,
        )
    mesh.export(str(glb_path), file_type="glb")
    return glb_path


def ensure_preview_glb(mesh_path: Path) -> Path | None:
    """Return a valid GLB beside the mesh file, generating it when missing."""
    mesh_path = Path(mesh_path)
    if not mesh_path.exists():
        return None

    glb_path = preview_glb_path(mesh_path)
    if is_valid_glb(glb_path):
        return glb_path

    if glb_path.exists():
        glb_path.unlink()

    try:
        return export_glb_from_mesh_file(mesh_path, glb_path)
    except Exception:
        if glb_path.exists():
            glb_path.unlink(missing_ok=True)
        return None


def copy_preview_glb(source_glb: Path, stl_path: Path) -> Path | None:
    """Copy an existing GLB (e.g. from a scan) next to a saved STL."""
    source_glb = Path(source_glb)
    if not source_glb.exists() or not is_valid_glb(source_glb):
        return None

    dest = preview_glb_path(stl_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_glb, dest)
    return dest
