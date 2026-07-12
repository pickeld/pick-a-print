from __future__ import annotations

import shutil
from pathlib import Path

from app.pipeline.workspace import JobWorkspace


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def workspace(self, job_id: str) -> JobWorkspace:
        return JobWorkspace(self.root, job_id)

    def save_input(self, job_id: str, source: Path) -> Path:
        ws = self.workspace(job_id)
        ws.ensure_dirs()
        dest = ws.input_dir / source.name
        shutil.copy2(source, dest)
        return dest

    def save_inputs_from_dir(self, job_id: str, source_dir: Path) -> list[Path]:
        ws = self.workspace(job_id)
        ws.ensure_dirs()
        saved: list[Path] = []
        for item in source_dir.iterdir():
            if item.is_file():
                dest = ws.input_dir / item.name
                shutil.copy2(item, dest)
                saved.append(dest)
        return saved
