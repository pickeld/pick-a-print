from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.conf import settings

SUPPORTED_DOWNLOAD_EXTENSIONS = {".stl", ".3mf"}
CONVERTIBLE_DOWNLOAD_EXTENSIONS = {".obj"}
MODEL_UPLOAD_EXTENSIONS = SUPPORTED_DOWNLOAD_EXTENSIONS


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


def downloadable_remote_filename(name: str) -> bool:
    ext = Path(name).suffix.lower()
    return ext in SUPPORTED_DOWNLOAD_EXTENSIONS or ext in CONVERTIBLE_DOWNLOAD_EXTENSIONS


def is_convertible_remote_filename(name: str) -> bool:
    return Path(name).suffix.lower() in CONVERTIBLE_DOWNLOAD_EXTENSIONS


def unsupported_files_message(found_names: list[str]) -> str:
    if not found_names:
        return "No STL or 3MF files found for this model"
    sample = ", ".join(found_names[:4])
    if len(found_names) > 4:
        sample = f"{sample} (+{len(found_names) - 4} more)"
    extensions = sorted({Path(name).suffix.lower() or "unknown" for name in found_names})
    ext_label = ", ".join(ext.lstrip(".") or "unknown" for ext in extensions)
    return (
        f"This model only has unsupported file types ({ext_label}): {sample}. "
        "Pick-a-Print needs STL or 3MF files — upload them manually on this page."
    )


def _is_presigned_s3_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host.endswith(".amazonaws.com") or "amazonaws.com" in host


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DownloadError(f"Redirect not allowed for presigned download URL (HTTP {code})")


def _download_presigned_url(
    url: str,
    dest: Path,
    *,
    max_bytes: int,
    headers: dict[str, str],
) -> int:
    opener = urllib.request.build_opener(_NoRedirectHandler())
    request = urllib.request.Request(url, headers=headers)
    downloaded = 0
    try:
        with opener.open(request, timeout=settings.METADATA_FETCH_TIMEOUT) as response:
            with dest.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 64)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise DownloadError(f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit")
                    handle.write(chunk)
    except urllib.error.HTTPError as exc:
        raise DownloadError(f"Download failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise DownloadError(f"Download failed: {exc.reason}") from exc

    if downloaded == 0:
        dest.unlink(missing_ok=True)
        raise DownloadError("Downloaded file is empty")
    return downloaded


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

    if _is_presigned_s3_url(url):
        return _download_presigned_url(url, dest, max_bytes=max_bytes, headers=request_headers)

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
