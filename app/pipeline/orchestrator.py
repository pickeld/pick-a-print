from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Callable
from pathlib import Path

from app.engines.blender import BlenderEngine
from app.engines.colmap import ColmapEngine
from app.engines.openmvs import OpenMvsEngine
from app.engines.trimesh_engine import TrimeshEngine
from app.models.enums import JobStage, PIPELINE_STAGES
from app.models.job import Job
from app.pipeline.colmap_progress import ColmapProgressReporter, DENSE_SUBSTEP_RANGES
from app.pipeline.config import PipelineConfig
from app.pipeline.hardware import colmap_cuda_available, openmvs_available
from app.pipeline.preview import build_preview_warnings, count_frames, is_placeholder_mesh
from app.pipeline.workspace import JobWorkspace
from app.quality.image_checks import validate_images
from app.quality.mesh_checks import validate_mesh
from app.quality.reconstruction_checks import validate_sparse_model

logger = logging.getLogger(__name__)


class StageError(Exception):
    pass


class ReconstructionPipeline:
    """Runs photogrammetry stages in order with resume support."""

    def __init__(
        self,
        job_id: str,
        config: PipelineConfig | None = None,
        on_checkpoint: Callable[[Job], None] | None = None,
    ) -> None:
        self.config = config or PipelineConfig.from_env()
        self.job = Job.load(self.config.workspace_root, job_id)
        self.ws = JobWorkspace(self.config.workspace_root, job_id)
        self.colmap = ColmapEngine()
        self.openmvs = OpenMvsEngine()
        self.trimesh = TrimeshEngine()
        self.blender = BlenderEngine()
        self._used_cpu_sparse_fallback = False
        self._on_checkpoint = on_checkpoint

    def _persist(self) -> None:
        self.job.save(self.config.workspace_root)
        if self._on_checkpoint is not None:
            self._on_checkpoint(self.job)

    def _colmap_on_line(self, stage: JobStage, reporter: ColmapProgressReporter) -> Callable[[str], None]:
        last_persist = 0.0
        last_sub_progress = -1.0

        def on_line(line: str) -> None:
            nonlocal last_persist, last_sub_progress
            message, sub_progress = reporter.feed_line(line)
            should_persist = False
            if message:
                self.job.append_log(message, stage)
                should_persist = True
            if sub_progress is not None:
                self.job.touch(stage, completed=False, sub_progress=sub_progress)
                now = time.monotonic()
                if (
                    sub_progress - last_sub_progress >= 0.02
                    or now - last_persist >= 5.0
                    or message is not None
                ):
                    should_persist = True
                    last_sub_progress = sub_progress
                    last_persist = now
            if should_persist:
                self._persist()

        return on_line

    def _colmap_dense_substep(self, reporter: ColmapProgressReporter) -> Callable[[str], None]:
        def on_dense_substep(name: str) -> None:
            label = reporter.set_dense_substep(name)
            start, _ = DENSE_SUBSTEP_RANGES.get(name, (0.0, 1.0))
            self.job.append_log(label, JobStage.DENSE_RECONSTRUCTION)
            self.job.touch(JobStage.DENSE_RECONSTRUCTION, completed=False, sub_progress=start)
            self._persist()

        return on_dense_substep

    def run(self, from_stage: JobStage | None = None) -> Job:
        self.ws.ensure_dirs()
        self.job.metadata["gpu_available"] = colmap_cuda_available()
        self.job.metadata["openmvs_available"] = openmvs_available()
        self._persist()

        start_idx = 0
        if from_stage is not None:
            start_idx = PIPELINE_STAGES.index(from_stage)

        stages_to_run = PIPELINE_STAGES[start_idx:]
        for stage in stages_to_run:
            if stage == JobStage.COMPLETED:
                self.job.error = None
                self.job.touch(JobStage.COMPLETED, completed=True)
                self._persist()
                break
            if self.ws.is_stage_done(stage) and stage != JobStage.UPLOADED:
                logger.info("Skipping completed stage %s for job %s", stage, self.job.id)
                self.job.append_log("Skipped (already completed)", stage)
                self.job.touch(stage, completed=True)
                self._persist()
                continue
            try:
                logger.info("Running stage %s for job %s", stage, self.job.id)
                self.job.touch(stage, completed=False)
                self.job.append_log("Stage started", stage)
                self._persist()
                self._run_stage(stage)
                self.ws.mark_stage_done(stage)
                self.job.append_log("Stage completed", stage)
                self.job.touch(stage, completed=True)
                self._persist()
            except Exception as exc:
                logger.exception("Stage %s failed for job %s", stage, self.job.id)
                self.job.append_log(f"Failed: {exc}", stage)
                self.job.mark_failed(f"{stage}: {exc}")
                self._persist()
                raise

        return self.job

    def _run_stage(self, stage: JobStage) -> None:
        handlers = {
            JobStage.UPLOADED: self._stage_uploaded,
            JobStage.PREPROCESSING: self._stage_preprocessing,
            JobStage.COLMAP_FEATURES: self._stage_colmap_features,
            JobStage.COLMAP_MATCHING: self._stage_colmap_matching,
            JobStage.COLMAP_MAPPING: self._stage_colmap_mapping,
            JobStage.DENSE_RECONSTRUCTION: self._stage_dense,
            JobStage.MESHING: self._stage_meshing,
            JobStage.REPAIRING: self._stage_repairing,
            JobStage.EXPORTING: self._stage_exporting,
        }
        handler = handlers.get(stage)
        if handler is None:
            raise StageError(f"No handler for stage {stage}")
        handler()

    def _stage_uploaded(self) -> None:
        if not any(self.ws.input_dir.iterdir()) if self.ws.input_dir.exists() else True:
            raise StageError("No input files in input/ directory")

    def _stage_preprocessing(self) -> None:
        self._extract_or_copy_images()
        report = validate_images(self.ws.frames_dir)
        if not report.ok:
            raise StageError(f"Image validation failed: {report.issues}")

    def _stage_colmap_features(self) -> None:
        if not colmap_cuda_available():
            self.job.append_log("CUDA unavailable — using CPU SIFT extraction", JobStage.COLMAP_FEATURES)
            self._persist()
        reporter = ColmapProgressReporter(JobStage.COLMAP_FEATURES)
        result = self.colmap.extract_features(
            self.ws.frames_dir,
            self.ws.colmap_database(),
            self.config.colmap,
            on_line=self._colmap_on_line(JobStage.COLMAP_FEATURES, reporter),
        )
        if not result.ok:
            raise StageError(result.message)

    def _stage_colmap_matching(self) -> None:
        reporter = ColmapProgressReporter(JobStage.COLMAP_MATCHING)
        result = self.colmap.match_features(
            self.ws.colmap_database(),
            self.config.colmap,
            on_line=self._colmap_on_line(JobStage.COLMAP_MATCHING, reporter),
        )
        if not result.ok:
            raise StageError(result.message)

    def _stage_colmap_mapping(self) -> None:
        reporter = ColmapProgressReporter(JobStage.COLMAP_MAPPING)
        result = self.colmap.map_sparse(
            self.ws.colmap_database(),
            self.ws.frames_dir,
            self.ws.colmap_sparse_dir(),
            self.config.colmap,
            on_line=self._colmap_on_line(JobStage.COLMAP_MAPPING, reporter),
        )
        if not result.ok:
            raise StageError(result.message)
        frame_count = int(self.job.metadata.get("frame_count") or count_frames(self.ws.frames_dir))
        report = validate_sparse_model(self.ws.colmap_sparse_dir(), frame_count=frame_count)
        self.job.metadata["sparse_validation"] = report.metrics
        self._persist()
        if not report.ok:
            raise StageError(f"Sparse model validation failed: {report.issues}")

    def _stage_dense(self) -> None:
        if self.config.colmap.max_image_size and colmap_cuda_available():
            self.job.append_log(
                f"Dense stereo max image size: {self.config.colmap.max_image_size}px",
                JobStage.DENSE_RECONSTRUCTION,
            )
            self._persist()
        reporter = ColmapProgressReporter(JobStage.DENSE_RECONSTRUCTION)
        result = self.colmap.dense_reconstruction(
            self.ws.colmap_sparse_dir(),
            self.ws.frames_dir,
            self.ws.colmap_dense_dir(),
            self.config.colmap,
            on_line=self._colmap_on_line(JobStage.DENSE_RECONSTRUCTION, reporter),
            on_dense_substep=self._colmap_dense_substep(reporter),
        )
        if not result.ok:
            raise StageError(result.message)

        self._used_cpu_sparse_fallback = "CPU mode" in result.message
        if self._used_cpu_sparse_fallback:
            self.job.append_log(result.message, JobStage.DENSE_RECONSTRUCTION)
            self._persist()
            return

        if openmvs_available():
            result = self.openmvs.prepare_scene(
                self.ws.colmap_dense_dir(),
                self.ws.openmvs_dir,
            )
            if not result.ok:
                raise StageError(result.message)
        else:
            self.job.append_log(
                "OpenMVS not installed — meshing will use COLMAP Poisson on dense/sparse cloud",
                JobStage.DENSE_RECONSTRUCTION,
            )
            self._persist()

    def _stage_meshing(self) -> None:
        mesh_out = self.ws.mesh_dir / "mesh.ply"

        if openmvs_available() and (self.ws.openmvs_dir / "scene.mvs").exists():
            result = self.openmvs.create_mesh(
                self.ws.openmvs_dir,
                self.ws.mesh_dir,
                self.config.openmvs,
            )
            if result.ok:
                return
            self.job.append_log(f"OpenMVS meshing failed ({result.message}), trying COLMAP Poisson", JobStage.MESHING)
            self._persist()

        point_cloud = self._find_point_cloud()
        point_count = self._count_point_cloud_points(point_cloud)
        self.job.metadata["point_cloud_count"] = point_count
        self._persist()
        if point_count < 500:
            raise StageError(
                f"Point cloud too sparse ({point_count} points) for reliable meshing. "
                "Re-shoot with a slow orbit around the object."
            )

        result = self.colmap.poisson_mesh(point_cloud, mesh_out)
        if not result.ok:
            self.job.append_log(
                f"COLMAP Poisson failed ({result.message}), trying voxel mesh",
                JobStage.MESHING,
            )
            self._persist()
            result = self.trimesh.mesh_from_pointcloud_voxel(point_cloud, mesh_out)
        if not result.ok:
            self.job.append_log(
                f"Voxel mesh failed ({result.message}), trying convex hull",
                JobStage.MESHING,
            )
            self._persist()
            result = self.trimesh.mesh_from_pointcloud(point_cloud, mesh_out)
        if not result.ok:
            raise StageError(result.message)

        self._color_point_cloud = point_cloud

    def _stage_repairing(self) -> None:
        mesh_in = self._find_mesh_input()
        color_cloud = getattr(self, "_color_point_cloud", None) or self._find_point_cloud_optional()
        result = self.trimesh.repair_mesh(mesh_in, self.ws.output_ply(), color_cloud)
        if not result.ok:
            raise StageError(result.message)
        report = validate_mesh(self.ws.output_ply())
        if not report.ok:
            raise StageError(f"Mesh validation failed: {report.issues}")

    def _stage_exporting(self) -> None:
        ply = self.ws.output_ply()
        color_cloud = getattr(self, "_color_point_cloud", None) or self._find_point_cloud_optional()
        result = self.trimesh.export_formats(
            ply, self.ws.output_obj(), self.ws.output_glb(), color_point_cloud=color_cloud
        )
        if not result.ok:
            raise StageError(result.message)
        result = self.blender.export_stl(
            ply,
            self.ws.output_stl(),
            self.config.export,
        )
        if not result.ok:
            raise StageError(result.message)
        self._write_report()

    def _extract_or_copy_images(self) -> None:
        from app.pipeline.input_extract import prepare_scan_input

        self.ws.frames_dir.mkdir(parents=True, exist_ok=True)
        prepared = prepare_scan_input(self.ws.input_dir)

        if prepared.archives:
            names = ", ".join(a.name for a in prepared.archives)
            self.job.append_log(
                f"Extracted {prepared.extracted_files} file(s) from {len(prepared.archives)} archive(s): {names}",
                JobStage.PREPROCESSING,
            )
            self._persist()

        images = prepared.images

        if images:
            self.job.append_log(f"Copying {len(images)} image(s) to frames/", JobStage.PREPROCESSING)
            self._persist()
            for index, img in enumerate(images):
                suffix = img.suffix.lower() if img.suffix else ".jpg"
                dest = self.ws.frames_dir / f"frame_{index:05d}{suffix}"
                shutil.copy2(img, dest)
        else:
            raise StageError(
                "Input must contain photos or a .zip archive with photos inside"
            )

        frame_count = count_frames(self.ws.frames_dir)
        self.job.metadata["frame_count"] = frame_count
        self.job.metadata["gpu_available"] = colmap_cuda_available()
        self._persist()

    def _find_point_cloud(self) -> Path:
        fused = self.ws.colmap_dense_dir() / "fused.ply"
        if fused.exists():
            return fused
        sparse_ply = self.ws.colmap_dense_dir() / "sparse_points.ply"
        if sparse_ply.exists():
            return sparse_ply
        result = self.colmap.export_sparse_pointcloud(
            self.ws.colmap_sparse_dir(),
            sparse_ply,
        )
        if result.ok and sparse_ply.exists():
            return sparse_ply
        raise StageError("No point cloud available for meshing")

    def _find_point_cloud_optional(self) -> Path | None:
        fused = self.ws.colmap_dense_dir() / "fused.ply"
        if fused.exists():
            return fused
        sparse_ply = self.ws.colmap_dense_dir() / "sparse_points.ply"
        if sparse_ply.exists():
            return sparse_ply
        return None

    def _find_mesh_input(self) -> Path:
        for pattern in ("*.ply", "*.obj"):
            matches = sorted(self.ws.mesh_dir.glob(pattern))
            if matches:
                return matches[0]
        raise StageError("No mesh found in mesh/ directory")

    def _count_point_cloud_points(self, point_cloud: Path) -> int:
        try:
            import trimesh

            loaded = trimesh.load(str(point_cloud))
            if isinstance(loaded, trimesh.PointCloud):
                return len(loaded.vertices)
            if hasattr(loaded, "vertices"):
                return len(loaded.vertices)
        except Exception:
            pass

        try:
            with point_cloud.open("rb") as handle:
                header = handle.read(4096).decode("latin-1", errors="ignore")
            for line in header.splitlines():
                if line.startswith("element vertex"):
                    return int(line.split()[-1])
        except OSError:
            pass
        return 0

    def _write_report(self) -> None:
        import json

        ply = self.ws.output_ply()
        frame_count = int(self.job.metadata.get("frame_count") or count_frames(self.ws.frames_dir))
        placeholder = is_placeholder_mesh(ply)
        report = {
            "job_id": self.job.id,
            "stage": self.job.stage.value,
            "gpu_available": bool(self.job.metadata.get("gpu_available", colmap_cuda_available())),
            "openmvs_available": bool(self.job.metadata.get("openmvs_available", openmvs_available())),
            "cpu_sparse_fallback": self._used_cpu_sparse_fallback,
            "frame_count": frame_count,
            "placeholder_mesh": placeholder,
            "warnings": build_preview_warnings(
                frame_count=frame_count,
                placeholder_mesh=placeholder,
                gpu_available=bool(self.job.metadata.get("gpu_available", colmap_cuda_available())),
                registration_ratio=self.job.metadata.get("sparse_validation", {}).get("registration_ratio"),
                point_cloud_count=self.job.metadata.get("point_cloud_count"),
            ),
            "outputs": {
                "ply": str(ply),
                "obj": str(self.ws.output_obj()),
                "glb": str(self.ws.output_glb()),
                "stl": str(self.ws.output_stl()),
            },
            "metadata": self.job.metadata,
        }
        self.ws.output_report().write_text(json.dumps(report, indent=2), encoding="utf-8")


def process_scan(
    job_id: str,
    config: PipelineConfig | None = None,
    on_checkpoint: Callable[[Job], None] | None = None,
) -> Job:
    """High-level entry used by workers and CLI."""
    pipeline = ReconstructionPipeline(job_id, config, on_checkpoint=on_checkpoint)
    return pipeline.run()
