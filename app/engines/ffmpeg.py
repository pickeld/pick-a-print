from __future__ import annotations

from pathlib import Path

from app.engines.base import EngineResult, require_binary, run_command
from app.pipeline.config import FfmpegConfig


class FfmpegEngine:
    def __init__(self, mock: bool = False) -> None:
        self.mock = mock

    def extract_frames(self, video: Path, output_dir: Path, config: FfmpegConfig) -> EngineResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        pattern = output_dir / "frame_%05d.jpg"

        if self.mock:
            # Copy a placeholder by duplicating first frame request — create dummy frames
            for i in range(min(10, config.max_frames)):
                (output_dir / f"frame_{i:05d}.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
            return EngineResult(True, "mock frames created", list(output_dir.glob("*.jpg")))

        ffmpeg = require_binary("ffmpeg")
        if not ffmpeg:
            return EngineResult(False, "ffmpeg not found in PATH")

        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video),
            "-vf",
            f"fps={config.fps}",
            "-q:v",
            str(config.quality),
            "-frames:v",
            str(config.max_frames),
            str(pattern),
        ]
        return run_command(cmd)
