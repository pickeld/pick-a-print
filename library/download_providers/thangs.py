from __future__ import annotations

import re

import requests
from django.conf import settings

from library.download_providers.base import RemoteDownloadFile
from library.downloads import DownloadError, supported_remote_filename
from library.models import SavedModel

THANGS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://thangs.com/",
}


class ThangsDownloadProvider:
    site_names = ("thangs", "thangs.com")

    def supports(self, model: SavedModel) -> bool:
        return (model.source_site or "").lower() in self.site_names

    def list_files(self, model: SavedModel) -> list[RemoteDownloadFile]:
        model_id = model.external_id or _resolve_model_id(model.source_url or "")
        if not model_id:
            raise DownloadError("Could not determine Thangs model id")

        response = requests.get(
            f"https://thangs.com/api/models/{model_id}",
            headers=THANGS_HEADERS,
            timeout=settings.METADATA_FETCH_TIMEOUT,
        )
        if response.status_code == 403:
            raise DownloadError(
                "Thangs blocked the download request (Cloudflare). Try uploading the STL manually."
            )
        response.raise_for_status()

        detail = response.json()
        files: list[RemoteDownloadFile] = []
        for part in detail.get("parts") or []:
            name = part.get("originalFileName") or part.get("filename") or ""
            if not supported_remote_filename(name):
                continue
            filename = part.get("filename") or name
            url = (
                f"https://thangs.com/api/v4/models/{model_id}/viewerFile"
                f"?part={requests.utils.quote(filename)}&useDraco=false"
            )
            files.append(
                RemoteDownloadFile(
                    name=name,
                    url=url,
                    file_size=part.get("size"),
                    headers=dict(THANGS_HEADERS),
                )
            )
        return files


def _resolve_model_id(url: str) -> str:
    match = re.search(r"thangs\.com/m/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"thangs\.com/designer/.+?/3d-model/.+-(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"thangs\.com/model/([^/?#]+)", url)
    if match:
        return match.group(1)
    return ""
