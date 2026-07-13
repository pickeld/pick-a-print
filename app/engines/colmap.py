from __future__ import annotations

from pathlib import Path

from app.engines.base import EngineResult, require_binary, run_command
from app.pipeline.colmap_sparse import best_sparse_model_dir
from app.pipeline.config import ColmapConfig
from app.pipeline.hardware import colmap_cuda_available


class ColmapEngine:
    def _colmap(self) -> str | None:
        return require_binary("colmap")

    def _sparse_model_dir(self, sparse_dir: Path) -> Path | None:
        return best_sparse_model_dir(sparse_dir)

    def extract_features(
        self, images_dir: Path, database: Path, config: ColmapConfig
    ) -> EngineResult:
        database.parent.mkdir(parents=True, exist_ok=True)
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
            "--SiftExtraction.use_gpu",
            "1" if config.use_gpu else "0",
        ]
        if config.max_image_size:
            cmd += ["--SiftExtraction.max_image_size", str(config.max_image_size)]
        if not config.use_gpu and config.sift_threads > 0:
            cmd += ["--SiftExtraction.num_threads", str(config.sift_threads)]
        return run_command(cmd, timeout=3600 * 2)

    def match_features(self, database: Path, config: ColmapConfig) -> EngineResult:
        colmap = self._colmap()
        if not colmap:
            return EngineResult(False, "colmap not found in PATH")

        matcher = "exhaustive_matcher" if config.matcher == "exhaustive" else "sequential_matcher"
        cmd = [
            colmap,
            matcher,
            "--database_path",
            str(database),
            "--SiftMatching.use_gpu",
            "1" if config.use_gpu else "0",
        ]
        return run_command(cmd, timeout=3600 * 2)

    def map_sparse(
        self,
        database: Path,
        images_dir: Path,
        sparse_dir: Path,
        config: ColmapConfig,
    ) -> EngineResult:
        sparse_dir.mkdir(parents=True, exist_ok=True)
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

    def export_sparse_pointcloud(self, sparse_dir: Path, output_ply: Path) -> EngineResult:
        """Export sparse reconstruction as PLY (CPU fallback when dense/CUDA unavailable)."""
        colmap = self._colmap()
        if not colmap:
            return EngineResult(False, "colmap not found in PATH")

        model = self._sparse_model_dir(sparse_dir)
        if model is None:
            return EngineResult(False, "No sparse model found for point cloud export")

        output_ply.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            colmap,
            "model_converter",
            "--input_path",
            str(model),
            "--output_path",
            str(output_ply),
            "--output_type",
            "PLY",
        ]
        result = run_command(cmd, timeout=600)
        if not result.ok:
            return result
        if not output_ply.exists():
            return EngineResult(False, "Sparse point cloud export produced no file")
        return EngineResult(True, "sparse point cloud exported", [output_ply])

    def poisson_mesh(self, input_ply: Path, output_ply: Path) -> EngineResult:
        colmap = self._colmap()
        if not colmap:
            return EngineResult(False, "colmap not found in PATH")
        if not input_ply.exists():
            return EngineResult(False, f"Point cloud not found: {input_ply}")

        from app.engines.trimesh_engine import TrimeshEngine

        prepared = output_ply.parent / "poisson_input.ply"
        prep = TrimeshEngine().prepare_poisson_pointcloud(input_ply, prepared)
        if not prep.ok:
            return prep

        output_ply.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            colmap,
            "poisson_mesher",
            "--input_path",
            str(prepared),
            "--output_path",
            str(output_ply),
        ]
        result = run_command(cmd, timeout=3600 * 2)
        if not result.ok:
            return result
        if not output_ply.exists():
            return EngineResult(False, "Poisson mesher produced no output")
        return EngineResult(True, "poisson mesh created", [output_ply])

    def dense_reconstruction(
        self,
        sparse_dir: Path,
        images_dir: Path,
        dense_dir: Path,
        config: ColmapConfig,
    ) -> EngineResult:
        dense_dir.mkdir(parents=True, exist_ok=True)

        if not colmap_cuda_available():
            fused = dense_dir / "fused.ply"
            result = self.export_sparse_pointcloud(sparse_dir, fused)
            if result.ok:
                return EngineResult(
                    True,
                    "CPU mode: exported sparse point cloud (CUDA dense stereo unavailable)",
                    [fused],
                )
            return result

        colmap = self._colmap()
        if not colmap:
            return EngineResult(False, "colmap not found in PATH")

        model = self._sparse_model_dir(sparse_dir)
        if model is None:
            return EngineResult(False, "No sparse model found")

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
        if config.max_image_size:
            cmd_undistort += ["--max_image_size", str(config.max_image_size)]
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
            "--PatchMatchStereo.gpu_index",
            "0",
        ]
        if config.max_image_size:
            cmd_stereo += ["--PatchMatchStereo.max_image_size", str(config.max_image_size)]
        result = run_command(cmd_stereo, timeout=3600 * 4)
        if not result.ok:
            return result

        fused = dense_dir / "fused.ply"
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
            str(fused),
        ]
        if config.max_image_size:
            cmd_fuse += ["--StereoFusion.max_image_size", str(config.max_image_size)]
        result = run_command(cmd_fuse, timeout=3600 * 2)
        if not result.ok:
            return result
        return EngineResult(True, "dense reconstruction complete", [fused])
