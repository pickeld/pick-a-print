from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from app.pipeline.hardware import colmap_cuda_available


@dataclass
class ColmapConfig:
    use_gpu: bool = True
    max_image_size: int = 3200
    sift_threads: int = 0  # 0 = COLMAP default (all cores)
    matcher: str = "exhaustive"  # exhaustive | sequential

    @classmethod
    def from_env(cls) -> ColmapConfig:
        use_gpu = colmap_cuda_available()
        default_max = 3200 if use_gpu else 1600
        max_size = int(os.getenv("COLMAP_MAX_IMAGE_SIZE", str(default_max)))
        matcher = os.getenv("COLMAP_MATCHER", "exhaustive")
        threads = int(os.getenv("COLMAP_SIFT_THREADS", "0" if use_gpu else "2"))
        return cls(use_gpu=use_gpu, max_image_size=max_size, sift_threads=threads, matcher=matcher)


@dataclass
class OpenMvsConfig:
    resolution_level: int = 1
    min_resolution: int = 640
    texture_size: int = 4096


@dataclass
class FfmpegConfig:
    fps: float = 4.0
    max_frames: int = 200
    quality: int = 2  # 1=best, 31=worst
    max_width: int = 1600  # downscale 4K phone video for CPU extraction/COLMAP

    @classmethod
    def from_env(cls) -> FfmpegConfig:
        colmap_max = os.getenv("COLMAP_MAX_IMAGE_SIZE")
        default_width = int(colmap_max) if colmap_max else 1600
        return cls(
            fps=float(os.getenv("FFMPEG_FPS", "4.0")),
            max_frames=int(os.getenv("FFMPEG_MAX_FRAMES", "200")),
            quality=int(os.getenv("FFMPEG_QUALITY", "2")),
            max_width=int(os.getenv("FFMPEG_MAX_WIDTH", str(default_width))),
        )


@dataclass
class ExportConfig:
    target_max_dimension_mm: float | None = None
    decimate_ratio: float | None = None


@dataclass
class PipelineConfig:
    workspace_root: Path = field(
        default_factory=lambda: Path(os.getenv("PIPELINE_DATA_DIR", "./data/jobs"))
    )
    colmap: ColmapConfig = field(default_factory=ColmapConfig.from_env)
    openmvs: OpenMvsConfig = field(default_factory=OpenMvsConfig)
    ffmpeg: FfmpegConfig = field(default_factory=FfmpegConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    @classmethod
    def from_env(cls) -> PipelineConfig:
        return cls(
            workspace_root=Path(os.getenv("PIPELINE_DATA_DIR", "./data/jobs")),
            colmap=ColmapConfig.from_env(),
            ffmpeg=FfmpegConfig.from_env(),
        )
