from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from django.conf import settings

from library.scan_services import ScanError, workspace_root

UPLOAD_ID_RE = re.compile(r"^[0-9a-f-]{36}$")


def _uploads_root() -> Path:
    root = workspace_root() / "_chunk_uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _session_dir(user_id: int, upload_id: str) -> Path:
    if not UPLOAD_ID_RE.match(upload_id):
        raise ScanError("Invalid upload id.")
    path = _uploads_root() / str(user_id) / upload_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_filename(name: str) -> str:
    base = Path(name).name
    if not base or base in {".", ".."}:
        raise ScanError("Invalid filename.")
    return base


def save_scan_chunk(
    *,
    user_id: int,
    upload_id: str,
    chunk_index: int,
    total_chunks: int,
    filename: str,
    chunk_file,
) -> None:
    if total_chunks < 1 or chunk_index < 0 or chunk_index >= total_chunks:
        raise ScanError("Invalid chunk index.")
    if total_chunks > 500:
        raise ScanError("Too many chunks.")

    safe_name = _safe_filename(filename)
    session = _session_dir(user_id, upload_id)
    meta_path = session / "meta.json"
    meta = {
        "filename": safe_name,
        "total_chunks": total_chunks,
        "title": "",
        "tag_names": [],
        "collection_ids": [],
    }
    if meta_path.exists():
        meta.update(json.loads(meta_path.read_text(encoding="utf-8")))
        if meta.get("filename") != safe_name or meta.get("total_chunks") != total_chunks:
            raise ScanError("Upload metadata mismatch.")
    else:
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

    chunk_path = session / f"chunk_{chunk_index:06d}"
    with chunk_path.open("wb") as out:
        for data in chunk_file.chunks():
            out.write(data)


def complete_scan_chunk_upload(
    *,
    user_id: int,
    upload_id: str,
    title: str = "",
    tag_names: list[str] | None = None,
    collection_ids: list[int] | None = None,
) -> Path:
    session = _session_dir(user_id, upload_id)
    meta_path = session / "meta.json"
    if not meta_path.exists():
        raise ScanError("Upload session not found.")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    total_chunks = int(meta["total_chunks"])
    filename = meta["filename"]

    if title:
        meta["title"] = title
    if tag_names is not None:
        meta["tag_names"] = tag_names
    if collection_ids is not None:
        meta["collection_ids"] = collection_ids
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    assembled = session / filename
    written = 0
    with assembled.open("wb") as out:
        for index in range(total_chunks):
            chunk_path = session / f"chunk_{index:06d}"
            if not chunk_path.exists():
                raise ScanError(f"Missing chunk {index + 1} of {total_chunks}.")
            data = chunk_path.read_bytes()
            written += len(data)
            out.write(data)

    max_bytes = settings.SCAN_MAX_UPLOAD_MB * 1024 * 1024
    if written > max_bytes:
        raise ScanError(f"Assembled file exceeds {settings.SCAN_MAX_UPLOAD_MB} MB limit.")

    return assembled


def cleanup_chunk_upload(user_id: int, upload_id: str) -> None:
    session = _uploads_root() / str(user_id) / upload_id
    if session.exists():
        shutil.rmtree(session, ignore_errors=True)


class AssembledScanFile:
    def __init__(self, path: Path):
        self.name = path.name
        self.size = path.stat().st_size
        self._path = path

    def chunks(self, chunk_size: int = 64 * 1024):
        with self._path.open("rb") as handle:
            while True:
                data = handle.read(chunk_size)
                if not data:
                    break
                yield data
