from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
ARCHIVE_EXTENSIONS = {".zip"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

SKIP_DIR_NAMES = {"__MACOSX"}
SKIP_FILE_NAMES = {".ds_store"}


@dataclass
class ExtractResult:
    archives: list[Path] = field(default_factory=list)
    extracted_files: int = 0
    images: list[Path] = field(default_factory=list)
    videos: list[Path] = field(default_factory=list)

    @property
    def media_count(self) -> int:
        return len(self.images) + len(self.videos)


def _should_skip(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    if path.name.lower() in SKIP_FILE_NAMES:
        return True
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> int:
    """Extract zip contents; reject path traversal. Returns number of files extracted."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest_dir.resolve()
    extracted = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            member = Path(info.filename)
            if _should_skip(member):
                continue
            # Flatten: keep only the filename to avoid deep nesting issues
            target = (dest_dir / member.name).resolve()
            if dest_resolved not in target.parents and target != dest_resolved:
                continue
            if target.exists():
                stem, suffix = target.stem, target.suffix
                counter = 1
                while target.exists():
                    target = dest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, target.open("wb") as dst:
                dst.write(src.read())
            extracted += 1

    return extracted


def extract_zip_archives(input_dir: Path) -> tuple[list[Path], int]:
    """Extract all .zip files in input_dir into input/_extracted/<archive-name>/."""
    archives: list[Path] = []
    total_files = 0
    seen: set[Path] = set()

    for zip_path in sorted(input_dir.iterdir()):
        if not zip_path.is_file():
            continue
        if zip_path.suffix.lower() not in ARCHIVE_EXTENSIONS:
            continue
        if zip_path in seen:
            continue
        seen.add(zip_path)
        extract_dir = input_dir / "_extracted" / zip_path.stem
        total_files += _safe_extract_zip(zip_path, extract_dir)
        archives.append(zip_path)

    return archives, total_files


def collect_media_files(input_dir: Path) -> tuple[list[Path], list[Path]]:
    """Recursively find images and videos under input_dir."""
    images: list[Path] = []
    videos: list[Path] = []

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        if _should_skip(path):
            continue
        ext = path.suffix.lower()
        if ext in ARCHIVE_EXTENSIONS:
            continue
        if ext in IMAGE_EXTENSIONS:
            images.append(path)
        elif ext in VIDEO_EXTENSIONS:
            videos.append(path)

    return images, videos


def prepare_scan_input(input_dir: Path) -> ExtractResult:
    """Extract zip archives and collect all images/videos for the scan pipeline."""
    archives, extracted_count = extract_zip_archives(input_dir)
    images, videos = collect_media_files(input_dir)
    return ExtractResult(
        archives=archives,
        extracted_files=extracted_count,
        images=images,
        videos=videos,
    )
