from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.quality.image_checks import QualityReport

MIN_REGISTERED_IMAGES = 5
MIN_POINTS3D = 100


def validate_sparse_model(sparse_dir: Path) -> QualityReport:
    issues: list[str] = []
    models = [p for p in sparse_dir.iterdir() if p.is_dir()]

    if not models:
        issues.append("No sparse reconstruction model found")
        return QualityReport(ok=False, issues=issues)

    model = models[0]
    required = ["cameras.bin", "images.bin", "points3D.bin"]
    for name in required:
        if not (model / name).exists():
            # text format also valid
            if not (model / name.replace(".bin", ".txt")).exists():
                issues.append(f"Missing {name} in sparse model")

    metrics: dict[str, float | int] = {"model_count": len(models)}

    images_txt = model / "images.txt"
    points_txt = model / "points3D.txt"
    if images_txt.exists():
        image_lines = sum(1 for line in images_txt.read_text().splitlines() if line and not line.startswith("#"))
        metrics["registered_images"] = image_lines // 2
        if metrics["registered_images"] < MIN_REGISTERED_IMAGES:
            issues.append(f"Only {metrics['registered_images']} images registered (min {MIN_REGISTERED_IMAGES})")

    if points_txt.exists():
        point_lines = sum(1 for line in points_txt.read_text().splitlines() if line and not line.startswith("#"))
        metrics["points3d"] = point_lines
        if point_lines < MIN_POINTS3D:
            issues.append(f"Only {point_lines} 3D points (min {MIN_POINTS3D})")

    return QualityReport(ok=len(issues) == 0, issues=issues, metrics=metrics)
