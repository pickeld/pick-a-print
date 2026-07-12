from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.models.enums import ArtifactType


@dataclass(frozen=True)
class Artifact:
    job_id: str
    artifact_type: ArtifactType
    path: Path
    size_bytes: int = 0

    @classmethod
    def from_path(cls, job_id: str, artifact_type: ArtifactType, path: Path) -> Artifact:
        size = path.stat().st_size if path.exists() else 0
        return cls(job_id=job_id, artifact_type=artifact_type, path=path, size_bytes=size)
