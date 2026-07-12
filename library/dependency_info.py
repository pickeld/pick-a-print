"""Docker image and pipeline tool release checks for the About settings tab."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import requests

CACHE_TTL_SECONDS = 3600
_cache: dict[str, tuple[float, object]] = {}

# Docker images from docker-compose.yml and Dockerfiles.
DOCKER_IMAGES = [
    {"service": "Object storage", "image": "minio/minio", "tag": "latest", "source": "docker-compose"},
    {"service": "Database", "image": "postgres", "tag": "16-alpine", "source": "docker-compose"},
    {"service": "Redis", "image": "redis", "tag": "7-alpine", "source": "docker-compose"},
    {"service": "Scan frontend", "image": "nginx", "tag": "alpine", "source": "docker-compose"},
    {"service": "Library web / worker", "image": "python", "tag": "3.12-slim", "source": "Dockerfile"},
    {"service": "Scan API", "image": "python", "tag": "3.12-slim", "source": "services/api/Dockerfile"},
    {"service": "Scan worker base", "image": "ubuntu", "tag": "22.04", "source": "services/worker/Dockerfile"},
]

# Pipeline tools baked into the scan worker image (apt on Ubuntu 22.04).
PIPELINE_TOOLS = [
    {
        "name": "COLMAP",
        "ubuntu_package": "colmap",
        "github_repo": "colmap/colmap",
        "source": "services/worker/Dockerfile (apt)",
    },
    {
        "name": "FFmpeg",
        "ubuntu_package": "ffmpeg",
        "github_repo": "FFmpeg/FFmpeg",
        "source": "services/worker/Dockerfile (apt)",
    },
    {
        "name": "Blender",
        "ubuntu_package": "blender",
        "github_repo": "blender/blender",
        "source": "services/worker/Dockerfile (apt)",
    },
    {
        "name": "OpenMVS",
        "ubuntu_package": None,
        "github_repo": "cdcseacave/openMVS",
        "source": "optional — not in base image",
    },
]


@dataclass
class ImageReleaseInfo:
    service: str
    image: str
    tag: str
    latest: str | None
    status: str  # up_to_date | update_available | floating | check_failed
    source: str


@dataclass
class ToolReleaseInfo:
    name: str
    installed: str | None
    latest: str | None
    status: str  # up_to_date | update_available | not_installed | check_failed
    source: str


def _cached(key: str, factory, *, refresh: bool = False):
    now = time.time()
    if not refresh and key in _cache:
        ts, value = _cache[key]
        if now - ts < CACHE_TTL_SECONDS:
            return value
    value = factory()
    _cache[key] = (now, value)
    return value


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
    tags: list[str] = []
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags?page_size=100"
    try:
        while url and len(tags) < 300:
            response = requests.get(url, timeout=10, headers={"Accept": "application/json"})
            if response.status_code != 200:
                break
            payload = response.json()
            for row in payload.get("results", []):
                tag_name = row.get("name")
                if tag_name:
                    tags.append(tag_name)
            url = payload.get("next")
    except requests.RequestException:
        return []
    return tags


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
            timeout=10,
            headers=headers,
        )
        if response.status_code == 200:
            data = response.json()
            tag = data.get("tag_name") or data.get("name")
            if tag:
                return normalize_tag(tag)

        response = requests.get(
            f"https://api.github.com/repos/{repo}/tags",
            params={"per_page": 50},
            timeout=10,
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


def _fetch_ubuntu_package_version(package: str, suite: str = "jammy") -> str | None:
    try:
        response = requests.get(
            f"https://packages.ubuntu.com/{suite}/{package}",
            timeout=10,
            headers={"User-Agent": "3d-collection-about-tab"},
        )
        if response.status_code != 200:
            return None
        match = re.search(rf"<h1>Package:\s*{re.escape(package)}\s*\(([^)]+)\)", response.text)
        if not match:
            return None
        return match.group(1).split(" and others")[0].strip()
    except requests.RequestException:
        return None


def _upstream_version(version: str | None) -> str | None:
    """Strip distro revision suffix, e.g. 3.7-2 -> 3.7, 7:5.1.2-3ubuntu1 -> 5.1.2."""
    if not version:
        return None
    cleaned = version.split(":")[-1]  # epoch
    cleaned = re.split(r"[-~]", cleaned, maxsplit=1)[0]
    return cleaned


def _tool_status(installed: str | None, latest: str | None, *, in_image: bool) -> str:
    if not in_image:
        return "not_installed"
    if latest is None or installed is None:
        return "check_failed"
    current = _upstream_version(installed)
    if current and _is_newer(latest, current):
        return "update_available"
    return "up_to_date"


def get_docker_images(refresh: bool = False) -> list[ImageReleaseInfo]:
    def build():
        tag_cache: dict[str, list[str]] = {}
        results: list[ImageReleaseInfo] = []
        for row in DOCKER_IMAGES:
            image = row["image"]
            if image not in tag_cache:
                tag_cache[image] = _fetch_docker_tags(image)
            latest = _best_matching_tag(tag_cache[image], row["tag"])
            results.append(
                ImageReleaseInfo(
                    service=row["service"],
                    image=image,
                    tag=row["tag"],
                    latest=latest,
                    status=_docker_status(row["tag"], latest),
                    source=row["source"],
                )
            )
        return results

    return _cached("docker_images", build, refresh=refresh)


def get_pipeline_tools(refresh: bool = False) -> list[ToolReleaseInfo]:
    def build():
        results: list[ToolReleaseInfo] = []
        for tool in PIPELINE_TOOLS:
            in_image = tool["ubuntu_package"] is not None
            installed = (
                _fetch_ubuntu_package_version(tool["ubuntu_package"])
                if in_image
                else None
            )
            latest = _fetch_github_latest(tool["github_repo"])
            results.append(
                ToolReleaseInfo(
                    name=tool["name"],
                    installed=installed,
                    latest=latest,
                    status=_tool_status(installed, latest, in_image=in_image),
                    source=tool["source"],
                )
            )
        return results

    return _cached("pipeline_tools", build, refresh=refresh)


def get_cached_updates_available() -> bool:
    for key in ("docker_images", "pipeline_tools"):
        if key not in _cache:
            continue
        _, value = _cache[key]
        if any(item.status == "update_available" for item in value):
            return True
    return False


def get_about_context(refresh: bool = False) -> dict:
    docker_images = get_docker_images(refresh=refresh)
    pipeline_tools = get_pipeline_tools(refresh=refresh)

    updates_available = any(
        item.status == "update_available" for item in (*docker_images, *pipeline_tools)
    )

    return {
        "docker_images": docker_images,
        "pipeline_tools": pipeline_tools,
        "updates_available": updates_available,
        "checked_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "cache_ttl_minutes": CACHE_TTL_SECONDS // 60,
    }
