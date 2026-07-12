from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MIN_IMAGES = 3
MIN_RESOLUTION = 480


@dataclass
class QualityReport:
    ok: bool
    issues: list[str] = field(default_factory=list)
    metrics: dict[str, float | int] = field(default_factory=dict)


def validate_images(frames_dir: Path) -> QualityReport:
    issues: list[str] = []
    images = [p for p in frames_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS]

    if len(images) < MIN_IMAGES:
        issues.append(f"Need at least {MIN_IMAGES} images, found {len(images)}")

    widths: list[int] = []
    heights: list[int] = []
    for img in images[:50]:
        try:
            from PIL import Image

            with Image.open(img) as im:
                w, h = im.size
                widths.append(w)
                heights.append(h)
                if min(w, h) < MIN_RESOLUTION:
                    issues.append(f"{img.name}: resolution below {MIN_RESOLUTION}px")
        except ImportError:
            break
        except OSError as exc:
            issues.append(f"{img.name}: unreadable ({exc})")

    metrics: dict[str, float | int] = {"image_count": len(images)}
    if widths:
        metrics["avg_width"] = sum(widths) / len(widths)
        metrics["avg_height"] = sum(heights) / len(heights)

    return QualityReport(ok=len(issues) == 0, issues=issues, metrics=metrics)
