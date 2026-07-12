from __future__ import annotations

from pathlib import Path

from app.engines.base import EngineResult, require_binary, run_command
from app.pipeline.config import OpenMvsConfig


class OpenMvsEngine:
    def _binary(self, name: str) -> str | None:
        return require_binary(name)

    def prepare_scene(self, colmap_dense_dir: Path, openmvs_dir: Path) -> EngineResult:
        """Convert COLMAP dense workspace to OpenMVS scene."""
        openmvs_dir.mkdir(parents=True, exist_ok=True)
        scene = openmvs_dir / "scene.mvs"

        interface = self._binary("InterfaceCOLMAP")
        if not interface:
            return EngineResult(False, "InterfaceCOLMAP not found in PATH")

        cmd = [
            interface,
            "-i",
            str(colmap_dense_dir),
            "-o",
            str(scene),
            "--image-folder",
            str(colmap_dense_dir / "images"),
        ]
        return run_command(cmd, timeout=3600)

    def create_mesh(
        self, openmvs_dir: Path, mesh_dir: Path, config: OpenMvsConfig
    ) -> EngineResult:
        mesh_dir.mkdir(parents=True, exist_ok=True)
        scene = openmvs_dir / "scene.mvs"
        dense = openmvs_dir / "scene_dense.mvs"
        mesh_mvs = openmvs_dir / "scene_mesh.mvs"
        out_ply = mesh_dir / "mesh.ply"

        densify = self._binary("DensifyPointCloud")
        reconstruct = self._binary("ReconstructMesh")
        if not densify or not reconstruct:
            return EngineResult(False, "OpenMVS binaries (DensifyPointCloud, ReconstructMesh) not found")

        result = run_command(
            [
                densify,
                str(scene),
                "-o",
                str(dense),
                "--resolution-level",
                str(config.resolution_level),
                "--min-resolution",
                str(config.min_resolution),
            ],
            timeout=3600 * 4,
        )
        if not result.ok:
            return result

        result = run_command(
            [reconstruct, str(dense), "-o", str(mesh_mvs), "-p", str(out_ply)],
            timeout=3600 * 2,
        )
        if not result.ok:
            return result

        refine = self._binary("RefineMesh")
        if refine and mesh_mvs.exists():
            refined = openmvs_dir / "scene_mesh_refined.mvs"
            run_command([refine, str(mesh_mvs), "-o", str(refined)], timeout=3600 * 2)

        texture = self._binary("TextureMesh")
        if texture and mesh_mvs.exists():
            textured = mesh_dir / "mesh_textured.obj"
            run_command(
                [texture, str(mesh_mvs), "-o", str(textured), "--texture-size", str(config.texture_size)],
                timeout=3600 * 2,
            )

        return EngineResult(True, "mesh created", [out_ply])
