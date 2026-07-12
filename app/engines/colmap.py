from __future__ import annotations

from pathlib import Path

from app.engines.base import EngineResult, require_binary, run_command
from app.pipeline.config import ColmapConfig


class ColmapEngine:
    def __init__(self, mock: bool = False) -> None:
        self.mock = mock

    def _colmap(self) -> str | None:
        return require_binary("colmap")

    def extract_features(
        self, images_dir: Path, database: Path, config: ColmapConfig
    ) -> EngineResult:
        database.parent.mkdir(parents=True, exist_ok=True)
        if self.mock:
            database.write_bytes(b"mock-colmap-db")
            return EngineResult(True, "mock features")

        colmap = self._colmap()
        if not colmap:
            return EngineResult(False, "colmap not found in PATH")

        cmd = [
            colmap,
            "feature_extractor",
            "--database_path",
            str(database),
            "--image_path",
            str(images_dir),
            "--ImageReader.single_camera",
            "1",
        ]
        if config.use_gpu:
            cmd += ["--SiftExtraction.use_gpu", "1"]
        if config.max_image_size:
            cmd += ["--SiftExtraction.max_image_size", str(config.max_image_size)]
        return run_command(cmd)

    def match_features(self, database: Path, config: ColmapConfig) -> EngineResult:
        if self.mock:
            return EngineResult(True, "mock matching")

        colmap = self._colmap()
        if not colmap:
            return EngineResult(False, "colmap not found in PATH")

        matcher = "exhaustive_matcher" if config.matcher == "exhaustive" else "sequential_matcher"
        cmd = [colmap, matcher, "--database_path", str(database)]
        if config.use_gpu:
            cmd += ["--SiftMatching.use_gpu", "1"]
        return run_command(cmd)

    def map_sparse(
        self,
        database: Path,
        images_dir: Path,
        sparse_dir: Path,
        config: ColmapConfig,
    ) -> EngineResult:
        sparse_dir.mkdir(parents=True, exist_ok=True)
        if self.mock:
            model = sparse_dir / "0"
            model.mkdir(parents=True, exist_ok=True)
            (model / "cameras.bin").write_bytes(b"mock")
            (model / "images.bin").write_bytes(b"mock")
            (model / "points3D.bin").write_bytes(b"mock")
            return EngineResult(True, "mock sparse", [model])

        colmap = self._colmap()
        if not colmap:
            return EngineResult(False, "colmap not found in PATH")

        cmd = [
            colmap,
            "mapper",
            "--database_path",
            str(database),
            "--image_path",
            str(images_dir),
            "--output_path",
            str(sparse_dir),
        ]
        return run_command(cmd, timeout=3600 * 4)

    def dense_reconstruction(
        self,
        sparse_dir: Path,
        images_dir: Path,
        dense_dir: Path,
        config: ColmapConfig,
    ) -> EngineResult:
        dense_dir.mkdir(parents=True, exist_ok=True)
        if self.mock:
            (dense_dir / "mock_dense.ply").write_text("ply\nformat ascii 1.0\n", encoding="utf-8")
            return EngineResult(True, "mock dense")

        colmap = self._colmap()
        if not colmap:
            return EngineResult(False, "colmap not found in PATH")

        model = sparse_dir / "0"
        if not model.exists():
            models = sorted(sparse_dir.iterdir())
            if not models:
                return EngineResult(False, "No sparse model found")
            model = models[0]

        undistorted = dense_dir / "images"
        cmd_undistort = [
            colmap,
            "image_undistorter",
            "--image_path",
            str(images_dir),
            "--input_path",
            str(model),
            "--output_path",
            str(dense_dir),
            "--output_type",
            "COLMAP",
        ]
        result = run_command(cmd_undistort, timeout=3600 * 2)
        if not result.ok:
            return result

        cmd_stereo = [
            colmap,
            "patch_match_stereo",
            "--workspace_path",
            str(dense_dir),
            "--workspace_format",
            "COLMAP",
        ]
        if config.use_gpu:
            cmd_stereo += ["--PatchMatchStereo.gpu_index", "0"]
        result = run_command(cmd_stereo, timeout=3600 * 4)
        if not result.ok:
            return result

        cmd_fuse = [
            colmap,
            "stereo_fusion",
            "--workspace_path",
            str(dense_dir),
            "--workspace_format",
            "COLMAP",
            "--input_type",
            "geometric",
            "--output_path",
            str(dense_dir / "fused.ply"),
        ]
        return run_command(cmd_fuse, timeout=3600 * 2)
