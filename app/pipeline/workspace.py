from __future__ import annotations

from pathlib import Path

from app.models.enums import JobStage


class JobWorkspace:
    """Canonical on-disk layout for a single reconstruction job."""

    def __init__(self, root: Path, job_id: str) -> None:
        self.root = root / job_id
        self.job_id = job_id

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def colmap_dir(self) -> Path:
        return self.root / "colmap"

    @property
    def openmvs_dir(self) -> Path:
        return self.root / "openmvs"

    @property
    def mesh_dir(self) -> Path:
        return self.root / "mesh"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def markers_dir(self) -> Path:
        return self.root / ".markers"

    def marker(self, stage: JobStage) -> Path:
        return self.markers_dir / f"{stage.value}.done"

    def is_stage_done(self, stage: JobStage) -> bool:
        return self.marker(stage).exists()

    def mark_stage_done(self, stage: JobStage) -> None:
        self.markers_dir.mkdir(parents=True, exist_ok=True)
        self.marker(stage).write_text("ok", encoding="utf-8")

    def ensure_dirs(self) -> None:
        for d in (
            self.input_dir,
            self.frames_dir,
            self.colmap_dir,
            self.openmvs_dir,
            self.mesh_dir,
            self.output_dir,
            self.markers_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def colmap_database(self) -> Path:
        return self.colmap_dir / "database.db"

    def colmap_sparse_dir(self) -> Path:
        return self.colmap_dir / "sparse"

    def colmap_dense_dir(self) -> Path:
        return self.colmap_dir / "dense"

    def openmvs_scene(self) -> Path:
        return self.openmvs_dir / "scene.mvs"

    def output_ply(self) -> Path:
        return self.output_dir / "model.ply"

    def output_obj(self) -> Path:
        return self.output_dir / "model.obj"

    def output_glb(self) -> Path:
        return self.output_dir / "model.glb"

    def output_stl(self) -> Path:
        return self.output_dir / "model.stl"

    def output_report(self) -> Path:
        return self.output_dir / "report.json"
