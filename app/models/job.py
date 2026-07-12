from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.enums import JobStage, PIPELINE_STAGES


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    id: str
    stage: JobStage = JobStage.UPLOADED
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    error: str | None = None
    progress: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    stage_logs: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, job_id: str | None = None) -> Job:
        return cls(id=job_id or str(uuid4()))

    def touch(self, stage: JobStage | None = None) -> None:
        self.updated_at = _utcnow()
        if stage is not None:
            self.stage = stage
            total = len(PIPELINE_STAGES) - 1
            idx = PIPELINE_STAGES.index(stage)
            self.progress = round(idx / total * 100, 1)

    def mark_failed(self, message: str) -> None:
        self.stage = JobStage.FAILED
        self.error = message
        self.updated_at = _utcnow()

    def save(self, workspace_root: Path) -> None:
        path = workspace_root / self.id / "job.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, workspace_root: Path, job_id: str) -> Job:
        path = workspace_root / job_id / "job.json"
        if not path.exists():
            return cls.create(job_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["stage"] = JobStage(data["stage"])
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
