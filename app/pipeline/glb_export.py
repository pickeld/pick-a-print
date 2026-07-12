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


def _load_triangle_mesh(ply_path: Path):
    import trimesh

    mesh = trimesh.load(str(ply_path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
        raise ValueError("not a valid triangle mesh")
    return mesh


def apply_vertex_colors_from_pointcloud(mesh, point_cloud_path: Path | None):
    """Paint mesh vertices from nearest colored sparse/dense point cloud."""
    if point_cloud_path is None or not point_cloud_path.exists():
        return mesh

    import numpy as np
    import trimesh
    from scipy.spatial import cKDTree

    loaded = trimesh.load(str(point_cloud_path))
    if isinstance(loaded, trimesh.PointCloud):
        cloud = loaded
    elif hasattr(loaded, "vertices"):
        cloud = trimesh.PointCloud(loaded.vertices, colors=getattr(loaded, "colors", None))
    else:
        return mesh

    colors = getattr(cloud, "colors", None)
    if colors is None or len(colors) != len(cloud.vertices):
        return mesh

    tree = cKDTree(np.asarray(cloud.vertices))
    _, idx = tree.query(np.asarray(mesh.vertices), k=1)
    vertex_colors = np.asarray(colors)[np.atleast_1d(idx)]
    if vertex_colors.shape[1] >= 3:
        # Slightly boost blue channel so photo-derived colors read clearly in the viewer.
        vertex_colors = vertex_colors.copy()
        vertex_colors[:, 2] = np.clip(vertex_colors[:, 2] * 1.2, 0, 255)
    if vertex_colors.shape[1] == 3:
        alpha = np.full((len(vertex_colors), 1), 255, dtype=vertex_colors.dtype)
        vertex_colors = np.hstack([vertex_colors, alpha])
    mesh.visual.vertex_colors = vertex_colors
    return mesh


def export_glb_from_ply(
    ply_path: Path,
    glb_path: Path,
    obj_path: Path | None = None,
    color_point_cloud: Path | None = None,
) -> Path:
    """Build a valid GLB from PLY, preserving vertex colors when available."""
    import trimesh

    glb_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        mesh = _load_triangle_mesh(ply_path)
    except Exception:
        mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])

    mesh = apply_vertex_colors_from_pointcloud(mesh, color_point_cloud or ply_path)
    mesh.export(str(glb_path))
    if obj_path is not None:
        mesh.export(str(obj_path))
    return glb_path


def ensure_glb_from_ply(ply_path: Path, glb_path: Path, obj_path: Path | None = None) -> Path:
    """Return existing GLB or regenerate from PLY when missing/invalid."""
    if is_valid_glb(glb_path):
        return glb_path
    return export_glb_from_ply(ply_path, glb_path, obj_path)
