from __future__ import annotations

import re

import requests
from django.conf import settings

from library.download_providers.base import RemoteDownloadFile
from library.downloads import DownloadError, downloadable_remote_filename, unsupported_files_message
from library.models import SavedModel
from library.provider_credentials import thingiverse_api_token

THINGIVERSE_API = "https://api.thingiverse.com"


class ThingiverseDownloadProvider:
    site_names = ("thingiverse", "thingiverse.com", "www.thingiverse.com")

    def supports(self, model: SavedModel) -> bool:
        return (model.source_site or "").lower() in self.site_names

    def list_files(self, model: SavedModel) -> list[RemoteDownloadFile]:
        token = thingiverse_api_token()
        if not token:
            raise DownloadError(
                "Thingiverse downloads need an API token. "
                "Add it in Settings → Integrations, or set THINGIVERSE_API_TOKEN in your environment."
            )

        thing_id = model.external_id or _extract_thing_id(model.source_url or "")
        if not thing_id:
            raise DownloadError("Could not determine Thingiverse thing id")

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{THINGIVERSE_API}/things/{thing_id}/files",
            headers=headers,
            timeout=settings.METADATA_FETCH_TIMEOUT,
        )
        if response.status_code == 401:
            raise DownloadError("Thingiverse API token is invalid or expired")
        response.raise_for_status()

        files: list[RemoteDownloadFile] = []
        skipped: list[str] = []
        for item in response.json() or []:
            name = item.get("name") or ""
            if not downloadable_remote_filename(name):
                if name:
                    skipped.append(name)
                continue
            url = item.get("download_url") or item.get("direct_url")
            if not url:
                continue
            files.append(
                RemoteDownloadFile(
                    name=name,
                    url=url,
                    file_size=item.get("size"),
                    headers=headers,
                )
            )
        if not files and skipped:
            raise DownloadError(unsupported_files_message(skipped))
        return files


def _extract_thing_id(url: str) -> str:
    match = re.search(r"thingiverse\.com/thing:(\d+)", url)
    return match.group(1) if match else ""
