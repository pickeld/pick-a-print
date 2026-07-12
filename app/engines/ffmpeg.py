from __future__ import annotations

from pathlib import Path

from app.engines.base import EngineResult, require_binary, run_command
from app.pipeline.config import FfmpegConfig


class FfmpegEngine:
    def extract_frames(self, video: Path, output_dir: Path, config: FfmpegConfig) -> EngineResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        pattern = output_dir / "frame_%05d.jpg"

        ffmpeg = require_binary("ffmpeg")
        if not ffmpeg:
            return EngineResult(False, "ffmpeg not found in PATH")

        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video),
            "-vf",
            f"fps={config.fps},scale='min({config.max_width},iw)':-2",
            "-q:v",
            str(config.quality),
            "-frames:v",
            str(config.max_frames),
            str(pattern),
        ]
        return run_command(cmd, timeout=3600)
