"""Stage definitions — logic lives in orchestrator.py; this module documents the flow."""

from app.models.enums import JobStage, PIPELINE_STAGES

STAGE_DESCRIPTIONS: dict[JobStage, str] = {
    JobStage.UPLOADED: "Input received",
    JobStage.PREPROCESSING: "Extract frames / copy images and validate",
    JobStage.COLMAP_FEATURES: "COLMAP feature extraction",
    JobStage.COLMAP_MATCHING: "COLMAP feature matching",
    JobStage.COLMAP_MAPPING: "COLMAP sparse reconstruction",
    JobStage.DENSE_RECONSTRUCTION: "Dense point cloud (COLMAP + OpenMVS prep)",
    JobStage.MESHING: "Surface mesh reconstruction (OpenMVS)",
    JobStage.REPAIRING: "Mesh repair and watertight check (Trimesh)",
    JobStage.EXPORTING: "Export STL, GLB, OBJ and quality report",
    JobStage.COMPLETED: "Pipeline finished",
    JobStage.FAILED: "Pipeline failed",
}

__all__ = ["JobStage", "PIPELINE_STAGES", "STAGE_DESCRIPTIONS"]
