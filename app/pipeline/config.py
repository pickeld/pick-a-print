from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ColmapConfig:
    use_gpu: bool = True
    max_image_size: int = 3200
    matcher: str = "exhaustive"  # exhaustive | sequential


@dataclass
class OpenMvsConfig:
    resolution_level: int = 1
    min_resolution: int = 640
    texture_size: int = 4096


@dataclass
class FfmpegConfig:
    fps: float = 2.0
    max_frames: int = 200
    quality: int = 2  # 1=best, 31=worst


@dataclass
class ExportConfig:
    target_max_dimension_mm: float | None = None
    decimate_ratio: float | None = None


@dataclass
class PipelineConfig:
    workspace_root: Path = field(
        default_factory=lambda: Path(os.getenv("PIPELINE_DATA_DIR", "./data/jobs"))
    )
    mock: bool = field(default_factory=lambda: os.getenv("PIPELINE_MOCK", "").lower() in ("1", "true", "yes"))
    colmap: ColmapConfig = field(default_factory=ColmapConfig)
    openmvs: OpenMvsConfig = field(default_factory=OpenMvsConfig)
    ffmpeg: FfmpegConfig = field(default_factory=FfmpegConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    @classmethod
    def from_env(cls) -> PipelineConfig:
        return cls(
            workspace_root=Path(os.getenv("PIPELINE_DATA_DIR", "./data/jobs")),
            mock=os.getenv("PIPELINE_MOCK", "").lower() in ("1", "true", "yes"),
        )
