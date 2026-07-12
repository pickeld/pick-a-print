from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.engines.blender import BlenderEngine
from app.engines.colmap import ColmapEngine
from app.engines.ffmpeg import FfmpegEngine
from app.engines.openmvs import OpenMvsEngine
from app.engines.trimesh_engine import TrimeshEngine
from app.models.enums import JobStage, PIPELINE_STAGES
from app.models.job import Job
from app.pipeline.config import PipelineConfig
from app.pipeline.workspace import JobWorkspace
from app.quality.image_checks import validate_images
from app.quality.mesh_checks import validate_mesh
from app.quality.reconstruction_checks import validate_sparse_model

logger = logging.getLogger(__name__)


class StageError(Exception):
    pass


class ReconstructionPipeline:
    """Runs photogrammetry stages in order with resume support."""

    def __init__(self, job_id: str, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig.from_env()
        self.job = Job.load(self.config.workspace_root, job_id)
        self.ws = JobWorkspace(self.config.workspace_root, job_id)
        self.ffmpeg = FfmpegEngine(mock=self.config.mock)
        self.colmap = ColmapEngine(mock=self.config.mock)
        self.openmvs = OpenMvsEngine(mock=self.config.mock)
        self.trimesh = TrimeshEngine(mock=self.config.mock)
        self.blender = BlenderEngine(mock=self.config.mock)

    def run(self, from_stage: JobStage | None = None) -> Job:
        self.ws.ensure_dirs()
        start_idx = 0
        if from_stage is not None:
            start_idx = PIPELINE_STAGES.index(from_stage)

        stages_to_run = PIPELINE_STAGES[start_idx:]
        for stage in stages_to_run:
            if stage == JobStage.COMPLETED:
                self.job.touch(JobStage.COMPLETED)
                self.job.save(self.config.workspace_root)
                break
            if self.ws.is_stage_done(stage) and stage != JobStage.UPLOADED:
                logger.info("Skipping completed stage %s for job %s", stage, self.job.id)
                self.job.touch(stage)
                self.job.save(self.config.workspace_root)
                continue
            try:
                logger.info("Running stage %s for job %s", stage, self.job.id)
                self._run_stage(stage)
                self.ws.mark_stage_done(stage)
                self.job.touch(stage)
                self.job.save(self.config.workspace_root)
            except Exception as exc:
                logger.exception("Stage %s failed for job %s", stage, self.job.id)
                self.job.mark_failed(f"{stage}: {exc}")
                self.job.save(self.config.workspace_root)
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
        if not self.config.mock:
            report = validate_images(self.ws.frames_dir)
            if not report.ok:
                raise StageError(f"Image validation failed: {report.issues}")

    def _stage_colmap_features(self) -> None:
        result = self.colmap.extract_features(
            self.ws.frames_dir,
            self.ws.colmap_database(),
            self.config.colmap,
        )
        if not result.ok:
            raise StageError(result.message)

    def _stage_colmap_matching(self) -> None:
        result = self.colmap.match_features(
            self.ws.colmap_database(),
            self.config.colmap,
        )
        if not result.ok:
            raise StageError(result.message)

    def _stage_colmap_mapping(self) -> None:
        result = self.colmap.map_sparse(
            self.ws.colmap_database(),
            self.ws.frames_dir,
            self.ws.colmap_sparse_dir(),
            self.config.colmap,
        )
        if not result.ok:
            raise StageError(result.message)
        report = validate_sparse_model(self.ws.colmap_sparse_dir())
        if not report.ok:
            raise StageError(f"Sparse model validation failed: {report.issues}")

    def _stage_dense(self) -> None:
        result = self.colmap.dense_reconstruction(
            self.ws.colmap_sparse_dir(),
            self.ws.frames_dir,
            self.ws.colmap_dense_dir(),
            self.config.colmap,
        )
        if not result.ok:
            raise StageError(result.message)
        result = self.openmvs.prepare_scene(
            self.ws.colmap_dense_dir(),
            self.ws.openmvs_dir,
        )
        if not result.ok:
            raise StageError(result.message)

    def _stage_meshing(self) -> None:
        result = self.openmvs.create_mesh(
            self.ws.openmvs_dir,
            self.ws.mesh_dir,
            self.config.openmvs,
        )
        if not result.ok:
            raise StageError(result.message)

    def _stage_repairing(self) -> None:
        mesh_in = self._find_mesh_input()
        result = self.trimesh.repair_mesh(mesh_in, self.ws.output_ply())
        if not result.ok:
            raise StageError(result.message)
        if not self.config.mock:
            report = validate_mesh(self.ws.output_ply())
            if not report.ok:
                raise StageError(f"Mesh validation failed: {report.issues}")

    def _stage_exporting(self) -> None:
        ply = self.ws.output_ply()
        self.trimesh.export_formats(ply, self.ws.output_obj(), self.ws.output_glb())
        result = self.blender.export_stl(
            ply,
            self.ws.output_stl(),
            self.config.export,
        )
        if not result.ok:
            raise StageError(result.message)
        self._write_report()

    def _extract_or_copy_images(self) -> None:
        self.ws.frames_dir.mkdir(parents=True, exist_ok=True)
        videos = list(self.ws.input_dir.glob("*.mp4")) + list(self.ws.input_dir.glob("*.mov"))
        images = [
            p
            for p in self.ws.input_dir.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ]

        if videos:
            result = self.ffmpeg.extract_frames(
                videos[0],
                self.ws.frames_dir,
                self.config.ffmpeg,
            )
            if not result.ok:
                raise StageError(result.message)
        elif images:
            for img in images:
                shutil.copy2(img, self.ws.frames_dir / img.name)
        else:
            raise StageError("Input must contain images or a video file")

    def _find_mesh_input(self) -> Path:
        for pattern in ("*.ply", "*.obj"):
            matches = sorted(self.ws.mesh_dir.glob(pattern))
            if matches:
                return matches[0]
        raise StageError("No mesh found in mesh/ directory")

    def _write_report(self) -> None:
        import json

        report = {
            "job_id": self.job.id,
            "stage": self.job.stage.value,
            "outputs": {
                "ply": str(self.ws.output_ply()),
                "obj": str(self.ws.output_obj()),
                "glb": str(self.ws.output_glb()),
                "stl": str(self.ws.output_stl()),
            },
            "metadata": self.job.metadata,
        }
        self.ws.output_report().write_text(json.dumps(report, indent=2), encoding="utf-8")


def process_scan(job_id: str, config: PipelineConfig | None = None) -> Job:
    """High-level entry used by workers and CLI."""
    pipeline = ReconstructionPipeline(job_id, config)
    return pipeline.run()
