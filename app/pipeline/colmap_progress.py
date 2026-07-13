from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import JobStage

# Dense stage is split into three COLMAP CLI steps with these sub-ranges (0–1 within stage).
DENSE_SUBSTEP_RANGES: dict[str, tuple[float, float]] = {
    "undistort": (0.0, 0.12),
    "patch_match": (0.12, 0.88),
    "fusion": (0.88, 1.0),
}

_RE_PROCESSED_FILE = re.compile(r"Processed file \[(\d+)/(\d+)\]", re.IGNORECASE)
_RE_EXTRACT_FEATURES = re.compile(
    r"Extracting features from image (\d+)\s*/\s*(\d+)", re.IGNORECASE
)
_RE_MATCHING_BLOCK = re.compile(r"Matching block \[(\d+)/(\d+)", re.IGNORECASE)
_RE_REGISTERING_IMAGE = re.compile(r"Registering image #(\d+)", re.IGNORECASE)
_RE_PROBLEMS_TOTAL = re.compile(r"Configuration has (\d+) problems", re.IGNORECASE)
_RE_PROCESSING_PROBLEM = re.compile(
    r"Processing problem(?: \[)?(\d+)(?:/(\d+)| of (\d+))?", re.IGNORECASE
)
_RE_PROCESSING_IMAGE = re.compile(
    r"Processing image .+?\((\d+)/(\d+)\)", re.IGNORECASE
)
_RE_FUSING_IMAGE = re.compile(r"Fusing image \[(\d+)/(\d+)\]", re.IGNORECASE)


@dataclass
class ColmapProgressReporter:
    """Parse COLMAP stdout and map it to stage sub-progress (0–1 within the stage)."""

    stage: JobStage
    dense_substep: str | None = None
    _patch_total: int = 0
    _last_message: str | None = field(default=None, repr=False)

    def set_dense_substep(self, name: str) -> str:
        self.dense_substep = name
        self._patch_total = 0
        self._last_message = None
        labels = {
            "undistort": "Undistorting images for dense reconstruction",
            "patch_match": "Patch-match stereo (GPU dense depth maps)",
            "fusion": "Fusing depth maps into point cloud",
        }
        return labels.get(name, name.replace("_", " ").title())

    def feed_line(self, line: str) -> tuple[str | None, float | None]:
        """Return (user-facing status message, sub_progress 0–1) if parsed."""
        line = line.strip()
        if not line:
            return None, None

        message, fraction = self._parse_fraction(line)
        if fraction is None:
            return None, None

        if message and message != self._last_message:
            self._last_message = message
            return message, self._scale_sub_progress(fraction)

        if fraction is not None:
            return None, self._scale_sub_progress(fraction)

        return None, None

    def _scale_sub_progress(self, fraction: float) -> float:
        fraction = max(0.0, min(1.0, fraction))
        if self.stage == JobStage.DENSE_RECONSTRUCTION and self.dense_substep:
            start, end = DENSE_SUBSTEP_RANGES.get(self.dense_substep, (0.0, 1.0))
            return start + (end - start) * fraction
        return fraction

    def _parse_fraction(self, line: str) -> tuple[str | None, float | None]:
        if self.stage in (JobStage.COLMAP_FEATURES, JobStage.PREPROCESSING):
            m = _RE_PROCESSED_FILE.search(line) or _RE_EXTRACT_FEATURES.search(line)
            if m:
                current, total = int(m.group(1)), int(m.group(2))
                if total > 0:
                    return f"Extracting features: image {current}/{total}", current / total

        if self.stage == JobStage.COLMAP_MATCHING:
            m = _RE_MATCHING_BLOCK.search(line)
            if m:
                current, total = int(m.group(1)), int(m.group(2))
                if total > 0:
                    return f"Matching features: block {current}/{total}", current / total

        if self.stage == JobStage.COLMAP_MAPPING:
            m = _RE_REGISTERING_IMAGE.search(line)
            if m:
                current = int(m.group(1)) + 1
                return f"Sparse mapping: registering image {current}", None

        if self.stage == JobStage.DENSE_RECONSTRUCTION:
            m = _RE_PROBLEMS_TOTAL.search(line)
            if m:
                self._patch_total = int(m.group(1))
                return f"Dense stereo: {self._patch_total} depth maps to compute", 0.0

            m = _RE_PROCESSING_PROBLEM.search(line)
            if m:
                current = int(m.group(1))
                total = int(m.group(2) or m.group(3) or self._patch_total or 0)
                if total > 0:
                    return f"Dense stereo: depth map {current}/{total}", current / total

            m = _RE_PROCESSING_IMAGE.search(line)
            if m:
                current, total = int(m.group(1)), int(m.group(2))
                if total > 0:
                    return f"Dense stereo: image {current}/{total}", current / total

            m = _RE_FUSING_IMAGE.search(line)
            if m:
                current, total = int(m.group(1)), int(m.group(2))
                if total > 0:
                    return f"Fusing point cloud: image {current}/{total}", current / total

        return None, None
