"""Docker image and pipeline tool release checks for the About settings tab."""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGE_VERSIONS_FILE = BASE_DIR / "services" / "worker" / "image-versions.json"
CACHE_TTL_SECONDS = 3600
_cache: dict[str, tuple[float, object]] = {}
_fetch_lock = threading.Lock()

# Docker images from docker-compose.yml and Dockerfiles.
DOCKER_IMAGES = [
    {"service": "Object storage", "image": "minio/minio", "tag": "latest", "source": "docker-compose"},
    {"service": "Database", "image": "postgres", "tag": "16-alpine", "source": "docker-compose"},
    {"service": "Redis", "image": "redis", "tag": "7-alpine", "source": "docker-compose"},
    {"service": "Scan frontend", "image": "nginx", "tag": "alpine", "source": "docker-compose"},
    {"service": "Library web / worker", "image": "python", "tag": "3.12-slim", "source": "Dockerfile"},
    {"service": "Scan API", "image": "python", "tag": "3.12-slim", "source": "services/api/Dockerfile"},
    {"service": "Scan worker base", "image": "ubuntu", "tag": "24.04", "source": "services/worker/Dockerfile"},
]

# Pipeline tools in the scan worker image (see services/worker/image-versions.json).
PIPELINE_TOOLS = [
    {
        "name": "COLMAP",
        "version_key": "colmap",
        "github_repo": "colmap/colmap",
        "source": "worker image (apt)",
    },
    {
        "name": "FFmpeg",
        "version_key": "ffmpeg",
        "github_repo": "FFmpeg/FFmpeg",
        "source": "worker image (apt)",
    },
    {
        "name": "Blender",
        "version_key": "blender",
        "github_repo": "blender/blender",
        "source": "worker image (apt)",
    },
    {
        "name": "OpenMVS",
        "version_key": "openmvs",
        "github_repo": "cdcseacave/openMVS",
        "source": "worker image (GitHub release binary)",
    },
]


@dataclass
class ImageReleaseInfo:
    service: str
    image: str
    tag: str
    latest: str | None
    status: str  # up_to_date | update_available | floating | check_failed | checking
    source: str


@dataclass
class ToolReleaseInfo:
    name: str
    installed: str | None
    latest: str | None
    status: str  # up_to_date | update_available | not_installed | check_failed | checking
    source: str


def _load_image_versions() -> dict[str, str]:
    if not IMAGE_VERSIONS_FILE.is_file():
        return {}
    return json.loads(IMAGE_VERSIONS_FILE.read_text(encoding="utf-8"))


def _cache_get(key: str) -> object | None:
    if key not in _cache:
        return None
    ts, value = _cache[key]
    if time.time() - ts >= CACHE_TTL_SECONDS:
        return None
    return value


def _cache_set(key: str, value: object) -> None:
    _cache[key] = (time.time(), value)


def _version_tuple(version_str: str) -> tuple:
    version_str = version_str.strip().lstrip("v").split("+")[0]
    parts: list = []
    for segment in re.split(r"[.\-_]", version_str):
        match = re.match(r"(\d+)", segment)
        if match:
            parts.append(int(match.group(1)))
    return tuple(parts) if parts else (0,)


def _version_key(version_str: str) -> tuple:
    return _version_tuple(version_str)


def _is_newer(latest: str, current: str) -> bool:
    try:
        return _version_key(latest) > _version_key(current)
    except (TypeError, ValueError):
        return latest != current


def _fetch_docker_tags(image: str) -> list[str]:
    repo = image if "/" in image else f"library/{image}"
    try:
        response = requests.get(
            f"https://hub.docker.com/v2/repositories/{repo}/tags?page_size=100",
            timeout=8,
            headers={"Accept": "application/json"},
        )
        if response.status_code != 200:
            return []
        return [row["name"] for row in response.json().get("results", []) if row.get("name")]
    except requests.RequestException:
        return []


def _best_matching_tag(tags: list[str], current_tag: str) -> str | None:
    if not tags:
        return None

    if current_tag == "latest":
        release_tags = [t for t in tags if re.match(r"^RELEASE\.\d{4}-\d{2}-\d{2}T", t)]
        if release_tags:
            return max(release_tags)
        semver = [t for t in tags if re.match(r"^\d+\.\d+\.\d+$", t)]
        if semver:
            return max(semver, key=_version_key)
        numeric = [t for t in tags if re.match(r"^\d+\.\d+", t)]
        if numeric:
            return max(numeric, key=_version_key)
        return tags[0]

    if current_tag == "alpine":
        alpine_tags = [t for t in tags if t.endswith("-alpine") or t == "alpine"]
        versioned = [t for t in alpine_tags if re.match(r"^\d", t)]
        if versioned:
            return max(versioned, key=_version_key)
        return current_tag if current_tag in tags else alpine_tags[0] if alpine_tags else None

    slim_match = re.match(r"^(\d+\.\d+)-slim", current_tag)
    if slim_match:
        prefix = slim_match.group(1)
        family = [t for t in tags if t.startswith(prefix) and "slim" in t]
        if family:
            return max(family, key=_version_key)

    alpine_major = re.match(r"^(\d+)-alpine", current_tag)
    if alpine_major:
        major = alpine_major.group(1)
        family = [t for t in tags if re.match(rf"^{major}(\.\d+)?-alpine", t)]
        if family:
            return max(family, key=_version_key)

    version_alpine = re.match(r"^(\d+(?:\.\d+)?)-alpine", current_tag)
    if version_alpine:
        prefix = version_alpine.group(1)
        family = [t for t in tags if t.startswith(prefix) and "alpine" in t]
        if family:
            return max(family, key=_version_key)

    lts_match = re.match(r"^(\d+\.\d+)$", current_tag)
    if lts_match:
        prefix = lts_match.group(1)
        family = [t for t in tags if t == prefix or t.startswith(f"{prefix}.")]
        if family:
            return max(family, key=_version_key)

    if current_tag in tags:
        return current_tag
    return tags[0]


def _docker_status(tag: str, latest: str | None) -> str:
    if tag == "latest":
        return "floating"
    if latest is None:
        return "check_failed"
    if latest == tag:
        return "up_to_date"
    if _is_newer(latest, tag) or _version_key(latest) > _version_key(tag):
        return "update_available"
    return "up_to_date"


def _fetch_github_latest(repo: str) -> str | None:
    headers = {"Accept": "application/vnd.github+json"}

    def normalize_tag(tag: str) -> str:
        return tag.lstrip("v").lstrip("n")

    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            timeout=8,
            headers=headers,
        )
        if response.status_code == 200:
            data = response.json()
            tag = data.get("tag_name") or data.get("name")
            if tag:
                return normalize_tag(tag)

        response = requests.get(
            f"https://api.github.com/repos/{repo}/tags",
            params={"per_page": 30},
            timeout=8,
            headers=headers,
        )
        if response.status_code != 200:
            return None

        candidates: list[str] = []
        for row in response.json():
            raw = row.get("name") or ""
            if "-dev" in raw or "-rc" in raw:
                continue
            cleaned = normalize_tag(raw)
            if cleaned and re.match(r"^\d", cleaned):
                candidates.append(cleaned)
        if not candidates:
            return None
        return max(candidates, key=_version_key)
    except requests.RequestException:
        return None


def _tool_status(installed: str | None, latest: str | None) -> str:
    if latest is None or installed is None:
        return "check_failed"
    if _is_newer(latest, installed):
        return "update_available"
    return "up_to_date"


def _build_pipeline_tools() -> list[ToolReleaseInfo]:
    image_versions = _load_image_versions()
    results: list[ToolReleaseInfo] = []

    def check_tool(tool: dict) -> ToolReleaseInfo:
        installed = image_versions.get(tool["version_key"])
        latest = _fetch_github_latest(tool["github_repo"])
        return ToolReleaseInfo(
            name=tool["name"],
            installed=installed,
            latest=latest,
            status=_tool_status(installed, latest),
            source=tool["source"],
        )

    with ThreadPoolExecutor(max_workers=len(PIPELINE_TOOLS)) as pool:
        futures = [pool.submit(check_tool, tool) for tool in PIPELINE_TOOLS]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item.name)
    return results


def _build_docker_images() -> list[ImageReleaseInfo]:
    unique_images = {row["image"] for row in DOCKER_IMAGES}
    tag_cache: dict[str, list[str]] = {}

    with ThreadPoolExecutor(max_workers=len(unique_images)) as pool:
        futures = {pool.submit(_fetch_docker_tags, image): image for image in unique_images}
        for future in as_completed(futures):
            tag_cache[futures[future]] = future.result()

    results: list[ImageReleaseInfo] = []
    for row in DOCKER_IMAGES:
        latest = _best_matching_tag(tag_cache.get(row["image"], []), row["tag"])
        results.append(
            ImageReleaseInfo(
                service=row["service"],
                image=row["image"],
                tag=row["tag"],
                latest=latest,
                status=_docker_status(row["tag"], latest),
                source=row["source"],
            )
        )
    return results


def _build_about_payload() -> dict:
    with ThreadPoolExecutor(max_workers=2) as pool:
        docker_future = pool.submit(_build_docker_images)
        tools_future = pool.submit(_build_pipeline_tools)
        docker_images = docker_future.result()
        pipeline_tools = tools_future.result()

    updates_available = any(
        item.status == "update_available" for item in (*docker_images, *pipeline_tools)
    )
    return {
        "docker_images": [asdict(item) for item in docker_images],
        "pipeline_tools": [asdict(item) for item in pipeline_tools],
        "updates_available": updates_available,
        "checked_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "cache_ttl_minutes": CACHE_TTL_SECONDS // 60,
        "from_cache": False,
    }


def fetch_about_data(*, refresh: bool = False) -> dict:
    """Return release check results, using cache when valid."""
    if not refresh:
        cached = _cache_get("about_payload")
        if cached is not None:
            payload = dict(cached)
            payload["from_cache"] = True
            return payload

    with _fetch_lock:
        if not refresh:
            cached = _cache_get("about_payload")
            if cached is not None:
                payload = dict(cached)
                payload["from_cache"] = True
                return payload

        payload = _build_about_payload()
        _cache_set("about_payload", payload)
        return payload


def peek_cached_about() -> dict | None:
    """Return cached results without network I/O."""
    cached = _cache_get("about_payload")
    if cached is None:
        return None
    payload = dict(cached)
    payload["from_cache"] = True
    return payload


def get_cached_updates_available() -> bool:
    cached = peek_cached_about()
    return bool(cached and cached.get("updates_available"))
