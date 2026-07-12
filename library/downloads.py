from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.conf import settings

SUPPORTED_DOWNLOAD_EXTENSIONS = {".stl", ".3mf"}


class DownloadError(Exception):
    pass


def _allowed_download_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    allowed = getattr(settings, "DOWNLOAD_ALLOWED_HOSTS", ())
    for pattern in allowed:
        pattern = pattern.lower()
        if pattern.startswith("*."):
            suffix = pattern[1:]
            if host.endswith(suffix) or host == pattern[2:]:
                return True
        elif host == pattern:
            return True
    return False


def _resolve_public_host(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise DownloadError(f"Could not resolve host: {host}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise DownloadError(f"Blocked download host: {host}")


def _validate_download_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise DownloadError("Only HTTPS downloads are allowed")
    if not parsed.netloc:
        raise DownloadError("Invalid download URL")
    host = parsed.hostname or ""
    if not _allowed_download_host(host):
        raise DownloadError(f"Download host not allowed: {host}")
    _resolve_public_host(host)
    return url


def supported_remote_filename(name: str) -> bool:
    return Path(name).suffix.lower() in SUPPORTED_DOWNLOAD_EXTENSIONS


def download_to_path(
    url: str,
    dest: Path,
    *,
    max_bytes: int | None = None,
    headers: dict[str, str] | None = None,
) -> int:
    url = _validate_download_url(url)
    max_bytes = max_bytes or settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    dest.parent.mkdir(parents=True, exist_ok=True)

    request_headers = {"User-Agent": "pick-a-print/1.0"}
    if headers:
        request_headers.update(headers)

    downloaded = 0
    with requests.get(
        url,
        headers=request_headers,
        stream=True,
        timeout=settings.METADATA_FETCH_TIMEOUT,
        allow_redirects=True,
    ) as response:
        response.raise_for_status()
        final_host = urlparse(response.url).hostname or ""
        if not _allowed_download_host(final_host):
            raise DownloadError(f"Redirected to disallowed host: {final_host}")
        _resolve_public_host(final_host)

        with dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    raise DownloadError(f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit")
                handle.write(chunk)

    if downloaded == 0:
        dest.unlink(missing_ok=True)
        raise DownloadError("Downloaded file is empty")

    return downloaded
