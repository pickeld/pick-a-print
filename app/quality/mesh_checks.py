from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.quality.image_checks import QualityReport

MIN_VERTICES = 20
MIN_FACES = 20


def validate_mesh(mesh_path: Path) -> QualityReport:
    issues: list[str] = []
    metrics: dict[str, float | int] = {}

    if not mesh_path.exists():
        return QualityReport(ok=False, issues=["Mesh file does not exist"])

    try:
        import trimesh

        mesh = trimesh.load(str(mesh_path), force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            return QualityReport(ok=False, issues=["Could not load as triangle mesh"])

        metrics["vertices"] = len(mesh.vertices)
        metrics["faces"] = len(mesh.faces)
        metrics["watertight"] = int(mesh.is_watertight)
        metrics["volume"] = float(mesh.volume) if mesh.is_watertight else 0.0

        if len(mesh.vertices) < MIN_VERTICES:
            issues.append(f"Too few vertices: {len(mesh.vertices)}")
        if len(mesh.faces) < MIN_FACES:
            issues.append(f"Too few faces: {len(mesh.faces)}")
        if not mesh.is_watertight:
            metrics["watertight_warning"] = 1

    except ImportError:
        if mesh_path.stat().st_size < 100:
            issues.append("Mesh file suspiciously small")
    except Exception as exc:
        issues.append(f"Mesh load error: {exc}")

    return QualityReport(ok=len(issues) == 0, issues=issues, metrics=metrics)
