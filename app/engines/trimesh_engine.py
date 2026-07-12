from __future__ import annotations

from pathlib import Path

from app.engines.base import EngineResult
from app.pipeline.glb_export import export_glb_from_ply


class TrimeshEngine:
    def __init__(self, mock: bool = False) -> None:
        self.mock = mock

    def repair_mesh(self, input_mesh: Path, output_ply: Path) -> EngineResult:
        output_ply.parent.mkdir(parents=True, exist_ok=True)

        if self.mock:
            try:
                import trimesh

                mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
                mesh.visual.face_colors = [255, 140, 40, 255]
                mesh.export(str(output_ply))
            except ImportError:
                output_ply.write_text(
                    "ply\nformat ascii 1.0\nelement vertex 8\nproperty float x\n"
                    "property float y\nproperty float z\nelement face 12\n"
                    "property list uchar int vertex_indices\nend_header\n"
                    "0 0 0\n1 0 0\n1 1 0\n0 1 0\n"
                    "0 0 1\n1 0 1\n1 1 1\n0 1 1\n"
                    "3 0 1 2\n3 0 2 3\n",
                    encoding="utf-8",
                )
            return EngineResult(True, "mock repair", [output_ply])

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
