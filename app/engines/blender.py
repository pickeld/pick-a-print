from __future__ import annotations

import textwrap
from pathlib import Path

from app.engines.base import EngineResult, require_binary, run_command
from app.pipeline.config import ExportConfig


class BlenderEngine:
    def export_stl(self, input_mesh: Path, output_stl: Path, config: ExportConfig) -> EngineResult:
        output_stl.parent.mkdir(parents=True, exist_ok=True)

        blender = require_binary("blender")
        if not blender:
            try:
                import trimesh

                mesh = trimesh.load(str(input_mesh), force="mesh")
                mesh.export(str(output_stl))
                return EngineResult(True, "stl via trimesh fallback", [output_stl])
            except Exception as exc:
                return EngineResult(False, f"blender not found and trimesh fallback failed: {exc}")

        scale = 1.0
        if config.target_max_dimension_mm:
            scale = config.target_max_dimension_mm / 100.0

        script = textwrap.dedent(
            f"""
            import bpy
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_mesh.ply(filepath={input_mesh.as_posix()!r})
            obj = bpy.context.selected_objects[0]
            obj.scale = ({scale}, {scale}, {scale})
            bpy.ops.object.transform_apply(scale=True)
            bpy.ops.export_mesh.stl(
                filepath={output_stl.as_posix()!r},
                use_selection=False,
            )
            """
        )
        script_path = output_stl.parent / "_blender_export.py"
        script_path.write_text(script, encoding="utf-8")

        return run_command(
            [blender, "--background", "--python", str(script_path)],
            timeout=600,
        )
