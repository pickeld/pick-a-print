from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from library.models import SavedModel


@dataclass(frozen=True)
class RemoteDownloadFile:
    name: str
    url: str
    file_size: int | None = None
    headers: dict[str, str] = field(default_factory=dict)


class DownloadProvider(Protocol):
    site_names: tuple[str, ...]

    def supports(self, model: SavedModel) -> bool: ...

    def list_files(self, model: SavedModel) -> list[RemoteDownloadFile]: ...
