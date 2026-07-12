from __future__ import annotations

from pathlib import Path

from app.engines.base import EngineResult
from app.pipeline.glb_export import export_glb_from_ply


class TrimeshEngine:
    def repair_mesh(self, input_mesh: Path, output_ply: Path) -> EngineResult:
        output_ply.parent.mkdir(parents=True, exist_ok=True)

        try:
            import trimesh
        except ImportError:
            return EngineResult(False, "trimesh package not installed")

        mesh = trimesh.load(str(input_mesh), force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            return EngineResult(False, f"Could not load mesh from {input_mesh}")

        mesh.remove_duplicate_faces()
        mesh.remove_degenerate_faces()
        mesh.remove_unreferenced_vertices()
        mesh.fill_holes()
        mesh.export(str(output_ply))
        return EngineResult(True, "mesh repaired", [output_ply])

    def export_formats(self, ply: Path, obj: Path, glb: Path) -> EngineResult:
        try:
            export_glb_from_ply(ply, glb, obj)
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

        output_ply.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(output_ply))
        return EngineResult(True, "mesh from point cloud convex hull", [output_ply])
