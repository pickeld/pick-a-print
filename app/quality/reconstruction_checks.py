from __future__ import annotations

from pathlib import Path

from app.pipeline.colmap_sparse import best_sparse_model_dir, read_sparse_stats
from app.quality.image_checks import QualityReport

MIN_REGISTERED_IMAGES = 3
MIN_POINTS3D = 100
MIN_REGISTRATION_RATIO = 0.5


def validate_sparse_model(sparse_dir: Path, frame_count: int | None = None) -> QualityReport:
    issues: list[str] = []
    model = best_sparse_model_dir(sparse_dir)

    if model is None:
        issues.append("No sparse reconstruction model found")
        return QualityReport(ok=False, issues=issues)

    required = ["cameras.bin", "images.bin", "points3D.bin"]
    for name in required:
        if not (model / name).exists():
            if not (model / name.replace(".bin", ".txt")).exists():
                issues.append(f"Missing {name} in sparse model")

    registered, points = read_sparse_stats(model)
    model_count = sum(
        1 for p in sparse_dir.iterdir() if p.is_dir() and (p / "images.bin").exists()
    )
    metrics: dict[str, float | int] = {
        "model_count": model_count,
        "selected_model": model.name,
        "registered_images": registered,
        "points3d": points,
    }

    if registered < MIN_REGISTERED_IMAGES:
        issues.append(f"Only {registered} images registered (min {MIN_REGISTERED_IMAGES})")

    if points < MIN_POINTS3D:
        issues.append(f"Only {points} 3D points (min {MIN_POINTS3D})")

    if frame_count and frame_count > 0:
        ratio = registered / frame_count
        metrics["registration_ratio"] = round(ratio, 3)
        if ratio < MIN_REGISTRATION_RATIO:
            issues.append(
                f"Only {registered}/{frame_count} frames registered ({ratio:.0%}). "
                "Re-shoot with a slow orbit, steady movement, and good lighting."
            )

    return QualityReport(ok=len(issues) == 0, issues=issues, metrics=metrics)
