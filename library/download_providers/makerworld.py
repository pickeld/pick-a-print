from __future__ import annotations

import re

import requests
from django.conf import settings

from library.download_providers.base import RemoteDownloadFile
from library.downloads import DownloadError
from library.models import SavedModel
from library.provider_credentials import bambu_lab_token

BAMBU_API = "https://api.bambulab.com"


class MakerWorldDownloadProvider:
    site_names = ("makerworld", "makerworld.com")

    def supports(self, model: SavedModel) -> bool:
        return (model.source_site or "").lower() in self.site_names

    def list_files(self, model: SavedModel) -> list[RemoteDownloadFile]:
        token = bambu_lab_token(model.user)
        if not token:
            raise DownloadError(
                "MakerWorld downloads need a Bambu Cloud login. "
                "Connect in Settings → Integrations, paste your MakerWorld session token, "
                "or set BAMBU_LAB_TOKEN in your environment."
            )

        design_id = model.external_id or _extract_design_id(model.source_url or "")
        if not design_id:
            raise DownloadError("Could not determine MakerWorld design id")

        design = _fetch_design(design_id)
        bambu_model_id = design.get("modelId")
        if not bambu_model_id:
            raise DownloadError("MakerWorld design metadata did not include modelId")

        files: list[RemoteDownloadFile] = []
        for instance in design.get("instances") or []:
            profile_id = instance.get("profileId")
            if not profile_id:
                continue
            download = _fetch_profile_download(token, profile_id, bambu_model_id)
            name = download.get("name") or f"plate-{profile_id}.3mf"
            url = download.get("url")
            if not url:
                continue
            if not name.lower().endswith((".stl", ".3mf")):
                name = f"{name}.3mf" if ".3mf" not in name.lower() else name
            files.append(RemoteDownloadFile(name=name, url=url))

        return files


def _fetch_design(design_id: str) -> dict:
    response = requests.get(
        f"{BAMBU_API}/v1/design-service/design/{design_id}",
        headers={"User-Agent": "pick-a-print/1.0"},
        timeout=settings.METADATA_FETCH_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _fetch_profile_download(token: str, profile_id: int | str, model_id: str) -> dict:
    response = requests.get(
        f"{BAMBU_API}/v1/iot-service/api/user/profile/{profile_id}",
        params={"model_id": model_id},
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "pick-a-print/1.0",
        },
        timeout=settings.METADATA_FETCH_TIMEOUT,
    )
    if response.status_code == 401:
        raise DownloadError("Bambu Lab token is invalid or expired")
    response.raise_for_status()
    payload = response.json()
    if not payload.get("url"):
        raise DownloadError("MakerWorld did not return a download URL for this plate")
    return payload


def _extract_design_id(url: str) -> str:
    match = re.search(r"/models/(\d+)", url) or re.search(r"/model/(\d+)", url)
    return match.group(1) if match else ""
