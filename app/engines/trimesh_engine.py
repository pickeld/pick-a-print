from __future__ import annotations

from pathlib import Path

from app.engines.base import EngineResult
from app.pipeline.glb_export import export_glb_from_ply


class TrimeshEngine:
    def prepare_poisson_pointcloud(self, input_ply: Path, output_ply: Path) -> EngineResult:
        """Add estimated normals required by COLMAP poisson_mesher."""
        try:
            import numpy as np
            import trimesh
            from scipy.spatial import cKDTree
        except ImportError as exc:
            return EngineResult(False, f"Missing dependency for normal estimation: {exc}")

        loaded = trimesh.load(str(input_ply))
        if isinstance(loaded, trimesh.PointCloud):
            vertices = np.asarray(loaded.vertices)
            colors = getattr(loaded, "colors", None)
        elif hasattr(loaded, "vertices"):
            vertices = np.asarray(loaded.vertices)
            colors = None
        else:
            return EngineResult(False, f"Could not load point cloud from {input_ply}")

        if len(vertices) < 4:
            return EngineResult(False, "Point cloud has too few points for meshing")

        tree = cKDTree(vertices)
        k = min(16, len(vertices))
        normals = np.zeros((len(vertices), 3), dtype=np.float64)
        for i, vertex in enumerate(vertices):
            _, idx = tree.query(vertex, k=k)
            neighbors = vertices[np.atleast_1d(idx)]
            centered = neighbors - neighbors.mean(axis=0)
            if centered.shape[0] < 3:
                normals[i] = np.array([0.0, 0.0, 1.0])
                continue
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            normal = vh[-1]
            norm = np.linalg.norm(normal)
            normals[i] = normal / norm if norm > 0 else np.array([0.0, 0.0, 1.0])

        output_ply.parent.mkdir(parents=True, exist_ok=True)
        with output_ply.open("w", encoding="ascii") as handle:
            handle.write("ply\nformat ascii 1.0\n")
            handle.write(f"element vertex {len(vertices)}\n")
            handle.write("property float x\nproperty float y\nproperty float z\n")
            handle.write("property float nx\nproperty float ny\nproperty float nz\n")
            if colors is not None and len(colors) == len(vertices):
                handle.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
                for (x, y, z), (nx, ny, nz), color in zip(vertices, normals, colors):
                    r, g, b = (int(c) for c in color[:3])
                    handle.write(
                        f"{x:.6f} {y:.6f} {z:.6f} {nx:.6f} {ny:.6f} {nz:.6f} {r} {g} {b}\n"
                    )
            else:
                for (x, y, z), (nx, ny, nz) in zip(vertices, normals):
                    handle.write(f"{x:.6f} {y:.6f} {z:.6f} {nx:.6f} {ny:.6f} {nz:.6f}\n")
        return EngineResult(True, "point cloud normals prepared", [output_ply])

    def repair_mesh(
        self, input_mesh: Path, output_ply: Path, color_point_cloud: Path | None = None
    ) -> EngineResult:
        output_ply.parent.mkdir(parents=True, exist_ok=True)

        try:
            import trimesh
        except ImportError:
            return EngineResult(False, "trimesh package not installed")

        mesh = trimesh.load(str(input_mesh), force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            return EngineResult(False, f"Could not load mesh from {input_mesh}")

        mesh.remove_unreferenced_vertices()
        if hasattr(mesh, "merge_vertices"):
            mesh.merge_vertices()
        if hasattr(mesh, "nondegenerate_faces"):
            mesh.update_faces(mesh.nondegenerate_faces())
        if hasattr(mesh, "fill_holes"):
            mesh.fill_holes()

        from app.pipeline.glb_export import apply_vertex_colors_from_pointcloud

        apply_vertex_colors_from_pointcloud(mesh, color_point_cloud)
        mesh.export(str(output_ply))
        return EngineResult(True, "mesh repaired", [output_ply])

    def export_formats(
        self,
        ply: Path,
        obj: Path,
        glb: Path,
        color_point_cloud: Path | None = None,
    ) -> EngineResult:
        try:
            export_glb_from_ply(ply, glb, obj, color_point_cloud=color_point_cloud)
        except ImportError:
            return EngineResult(False, "trimesh package not installed")
        except Exception as exc:
            return EngineResult(False, f"GLB export failed: {exc}")
        return EngineResult(True, "exported obj/glb", [obj, glb])

    def mesh_from_pointcloud(self, point_cloud: Path, output_ply: Path) -> EngineResult:
        """Last-resort mesh when COLMAP Poisson is unavailable."""
        try:
            import trimesh
        except ImportError:
            return EngineResult(False, "trimesh package not installed")
        try:
            import scipy  # noqa: F401
        except ImportError:
            return EngineResult(False, "scipy package not installed (required for meshing)")

        loaded = trimesh.load(str(point_cloud))
        if isinstance(loaded, trimesh.PointCloud):
            cloud = loaded
        elif hasattr(loaded, "vertices"):
            cloud = trimesh.PointCloud(loaded.vertices)
        else:
            return EngineResult(False, f"Could not load point cloud from {point_cloud}")

        if len(cloud.vertices) < 4:
            return EngineResult(False, "Point cloud has too few points to mesh")

        try:
            mesh = cloud.convex_hull
        except Exception as exc:
            return EngineResult(False, f"Could not build mesh from point cloud: {exc}")

        from app.pipeline.glb_export import apply_vertex_colors_from_pointcloud

        apply_vertex_colors_from_pointcloud(mesh, point_cloud)
        output_ply.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(output_ply))
        return EngineResult(True, "mesh from point cloud convex hull", [output_ply])

    def mesh_from_pointcloud_voxel(self, point_cloud: Path, output_ply: Path) -> EngineResult:
        """Voxel + marching cubes — better envelope than convex hull for sparse CPU scans."""
        try:
            import numpy as np
            import trimesh
            from scipy.ndimage import binary_dilation
            from scipy.spatial import cKDTree
        except ImportError as exc:
            return EngineResult(False, f"Missing dependency for voxel meshing: {exc}")

        loaded = trimesh.load(str(point_cloud))
        if isinstance(loaded, trimesh.PointCloud):
            cloud = loaded
        elif hasattr(loaded, "vertices"):
            cloud = trimesh.PointCloud(loaded.vertices, colors=getattr(loaded, "colors", None))
        else:
            return EngineResult(False, f"Could not load point cloud from {point_cloud}")

        vertices = np.asarray(cloud.vertices)
        if len(vertices) < 4:
            return EngineResult(False, "Point cloud has too few points to mesh")

        extent = vertices.max(axis=0) - vertices.min(axis=0)
        pitch = float(extent.max()) / 40.0
        origin = vertices.min(axis=0)
        indices = np.floor((vertices - origin) / pitch).astype(int)
        shape = tuple(indices.max(axis=0) + 3)
        grid = np.zeros(shape, dtype=bool)
        grid[indices[:, 0], indices[:, 1], indices[:, 2]] = True
        grid = binary_dilation(grid, iterations=1)

        try:
            mesh = trimesh.voxel.VoxelGrid(grid).marching_cubes
        except Exception as exc:
            return EngineResult(False, f"Voxel meshing failed: {exc}")

        # Re-center to original coordinates.
        mesh.vertices = mesh.vertices * pitch + origin

        colors = getattr(cloud, "colors", None)
        if colors is not None and len(colors) == len(vertices):
            tree = cKDTree(vertices)
            _, idx = tree.query(mesh.vertices, k=1)
            vertex_colors = np.asarray(colors)[np.atleast_1d(idx)]
            if vertex_colors.shape[1] == 3:
                alpha = np.full((len(vertex_colors), 1), 255, dtype=vertex_colors.dtype)
                vertex_colors = np.hstack([vertex_colors, alpha])
            mesh.visual.vertex_colors = vertex_colors

        output_ply.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(output_ply))
        return EngineResult(True, "voxel mesh from point cloud", [output_ply])
