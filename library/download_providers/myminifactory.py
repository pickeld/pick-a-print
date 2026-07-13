from __future__ import annotations

import re

import requests
from django.conf import settings

from library.download_providers.base import RemoteDownloadFile
from library.downloads import DownloadError, supported_remote_filename
from library.models import SavedModel
from library.provider_credentials import myminifactory_api_key

MMF_API = "https://www.myminifactory.com/api/v2"


class MyMiniFactoryDownloadProvider:
    site_names = ("myminifactory", "myminifactory.com", "www.myminifactory.com")

    def supports(self, model: SavedModel) -> bool:
        site = (model.source_site or "").lower()
        return site in self.site_names or "myminifactory" in site

    def list_files(self, model: SavedModel) -> list[RemoteDownloadFile]:
        api_key = myminifactory_api_key()
        if not api_key:
            raise DownloadError(
                "MyMiniFactory downloads need an API key. "
                "Add it in Settings → Auto-download, or set MYMINIFACTORY_API_KEY in your environment."
            )

        object_id = model.external_id or _extract_object_id(model.source_url or "")
        if not object_id:
            raise DownloadError("Could not determine MyMiniFactory object id")

        response = requests.get(
            f"{MMF_API}/objects/{object_id}",
            params={"key": api_key},
            timeout=settings.METADATA_FETCH_TIMEOUT,
        )
        if response.status_code in (401, 403):
            raise DownloadError("MyMiniFactory API key is invalid or lacks download permission")
        response.raise_for_status()

        payload = response.json()
        files: list[RemoteDownloadFile] = []
        for item in payload.get("files") or []:
            name = item.get("filename") or ""
            if not supported_remote_filename(name):
                continue
            url = item.get("download_url")
            if not url:
                continue
            size_raw = item.get("size")
            file_size = int(size_raw) if size_raw and str(size_raw).isdigit() else None
            files.append(
                RemoteDownloadFile(
                    name=name,
                    url=url,
                    file_size=file_size,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            )
        return files


def _extract_object_id(url: str) -> str:
    match = re.search(r"myminifactory\.com/object/[\w-]+-(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"myminifactory\.com/object/(\d+)", url)
    return match.group(1) if match else ""
