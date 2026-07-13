from enum import Enum


class StrEnum(str, Enum):
    """Python 3.10-compatible StrEnum."""


class JobStage(StrEnum):
    UPLOADED = "UPLOADED"
    PREPROCESSING = "PREPROCESSING"
    COLMAP_FEATURES = "COLMAP_FEATURES"
    COLMAP_MATCHING = "COLMAP_MATCHING"
    COLMAP_MAPPING = "COLMAP_MAPPING"
    DENSE_RECONSTRUCTION = "DENSE_RECONSTRUCTION"
    MESHING = "MESHING"
    REPAIRING = "REPAIRING"
    EXPORTING = "EXPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Ordered pipeline stages (excludes terminal states).
PIPELINE_STAGES: tuple[JobStage, ...] = (
    JobStage.UPLOADED,
    JobStage.PREPROCESSING,
    JobStage.COLMAP_FEATURES,
    JobStage.COLMAP_MATCHING,
    JobStage.COLMAP_MAPPING,
    JobStage.DENSE_RECONSTRUCTION,
    JobStage.MESHING,
    JobStage.REPAIRING,
    JobStage.EXPORTING,
    JobStage.COMPLETED,
)


class ArtifactType(StrEnum):
    INPUT_IMAGE = "input_image"
    FRAME = "frame"
    COLMAP_SPARSE = "colmap_sparse"
    COLMAP_DENSE = "colmap_dense"
    OPENMVS_MESH = "openmvs_mesh"
    MESH_PLY = "mesh_ply"
    MESH_OBJ = "mesh_obj"
    MODEL_GLB = "model_glb"
    MODEL_STL = "model_stl"
    REPORT = "report"
