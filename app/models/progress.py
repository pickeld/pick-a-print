from __future__ import annotations

from app.models.enums import JobStage

# (start%, end%) for each stage — dense reconstruction gets the largest slice.
STAGE_PROGRESS: dict[JobStage, tuple[float, float]] = {
    JobStage.UPLOADED: (0.0, 2.0),
    JobStage.PREPROCESSING: (2.0, 15.0),
    JobStage.COLMAP_FEATURES: (15.0, 28.0),
    JobStage.COLMAP_MATCHING: (28.0, 38.0),
    JobStage.COLMAP_MAPPING: (38.0, 48.0),
    JobStage.DENSE_RECONSTRUCTION: (48.0, 75.0),
    JobStage.MESHING: (75.0, 88.0),
    JobStage.REPAIRING: (88.0, 94.0),
    JobStage.EXPORTING: (94.0, 100.0),
    JobStage.COMPLETED: (100.0, 100.0),
    JobStage.FAILED: (0.0, 0.0),
}

# Warn if job.json has not changed for this long while still running.
STAGE_STALE_AFTER_SEC: dict[JobStage, int] = {
    JobStage.UPLOADED: 120,
    JobStage.PREPROCESSING: 600,
    JobStage.COLMAP_FEATURES: 900,
    JobStage.COLMAP_MATCHING: 900,
    JobStage.COLMAP_MAPPING: 900,
    JobStage.DENSE_RECONSTRUCTION: 3600,
    JobStage.MESHING: 1200,
    JobStage.REPAIRING: 300,
    JobStage.EXPORTING: 300,
}

STAGE_HINTS: dict[JobStage, str] = {
    JobStage.UPLOADED: "Waiting for the scan worker to pick up this job.",
    JobStage.PREPROCESSING: "Preparing photos for reconstruction.",
    JobStage.DENSE_RECONSTRUCTION: "Dense stereo reconstruction — progress updates per depth map (often 10–45 minutes on Jetson GPU).",
    JobStage.MESHING: "Building the surface mesh from the point cloud.",
}


def progress_for_stage(stage: JobStage, *, completed: bool = False, sub_progress: float = 0.0) -> float:
    start, end = STAGE_PROGRESS.get(stage, (0.0, 0.0))
    if completed:
        return end
    sub_progress = max(0.0, min(1.0, sub_progress))
    return round(start + (end - start) * sub_progress, 1)


def stale_after_seconds(stage: JobStage) -> int:
    return STAGE_STALE_AFTER_SEC.get(stage, 900)
