from __future__ import annotations

import re

import requests
from django.conf import settings

from library.download_providers.base import RemoteDownloadFile
from library.downloads import DownloadError, supported_remote_filename
from library.models import SavedModel
from library.myminifactory_oauth import (
    MMF_API,
    api_headers,
    parse_api_error,
    user_access_token,
)


class MyMiniFactoryDownloadProvider:
    site_names = ("myminifactory", "myminifactory.com", "www.myminifactory.com")

    def supports(self, model: SavedModel) -> bool:
        site = (model.source_site or "").lower()
        return site in self.site_names or "myminifactory" in site

    def list_files(self, model: SavedModel) -> list[RemoteDownloadFile]:
        access_token = user_access_token(model.user)
        if not access_token:
            raise DownloadError(
                "MyMiniFactory downloads need your account connected. "
                "Open Settings → Integrations → MyMiniFactory, save your app slug, "
                "then click Connect MyMiniFactory."
            )

        object_id = model.external_id or _extract_object_id(model.source_url or "")
        if not object_id:
            raise DownloadError("Could not determine MyMiniFactory object id")

        headers = api_headers(access_token)
        object_payload = _fetch_object(object_id, headers=headers)
        files = _collect_remote_files(object_payload, object_id, headers=headers)

        if files:
            return files

        price = _object_price_label(object_payload)
        if price:
            raise DownloadError(
                f"This model costs {price} on MyMiniFactory. Purchase it there first, "
                "then retry the download from Pick-a-Print."
            )

        raise DownloadError(
            "MyMiniFactory did not return downloadable mesh files for this model. "
            "It may be paid, private, or require Tribe membership on MyMiniFactory."
        )


def _fetch_object(object_id: str, *, headers: dict[str, str]) -> dict:
    response = requests.get(
        f"{MMF_API}/objects/{object_id}",
        headers=headers,
        timeout=settings.METADATA_FETCH_TIMEOUT,
    )
    if response.status_code in (401, 403):
        raise DownloadError(
            f"MyMiniFactory access denied: {parse_api_error(response)} "
            "Reconnect your MyMiniFactory account in Settings."
        )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise DownloadError("Unexpected MyMiniFactory object response.")
    return payload


def _collect_remote_files(
    object_payload: dict,
    object_id: str,
    *,
    headers: dict[str, str],
) -> list[RemoteDownloadFile]:
    files: list[RemoteDownloadFile] = []

    archive_url = object_payload.get("archive_download_url")
    if archive_url:
        files.append(
            RemoteDownloadFile(
                name=f"object-{object_id}.zip",
                url=str(archive_url),
                headers=headers,
            )
        )
        return files

    for item in _iter_object_file_items(object_id, headers=headers):
        if not isinstance(item, dict):
            continue
        name = str(item.get("filename") or "").strip()
        if not name or not supported_remote_filename(name):
            continue

        url = item.get("download_url")
        if not url:
            file_id = item.get("id")
            if file_id:
                detail = _fetch_file_detail(file_id, headers=headers)
                url = detail.get("download_url") if detail else None

        if not url:
            continue

        size_raw = item.get("size")
        file_size = int(size_raw) if size_raw and str(size_raw).isdigit() else None
        files.append(
            RemoteDownloadFile(
                name=name,
                url=str(url),
                file_size=file_size,
                headers=headers,
            )
        )

    return files


def _iter_object_file_items(object_id: str, *, headers: dict[str, str]) -> list[dict]:
    items: list[dict] = []
    page = 1
    per_page = 50

    while True:
        response = requests.get(
            f"{MMF_API}/objects/{object_id}/files",
            headers=headers,
            params={"page": page, "per_page": per_page},
            timeout=settings.METADATA_FETCH_TIMEOUT,
        )
        if response.status_code in (401, 403):
            raise DownloadError(
                f"MyMiniFactory access denied: {parse_api_error(response)} "
                "Reconnect your MyMiniFactory account in Settings."
            )
        response.raise_for_status()
        payload = response.json()
        page_items = _file_items_from_payload(payload)
        items.extend(page_items)

        total_count = payload.get("total_count") if isinstance(payload, dict) else None
        if total_count is not None:
            try:
                if len(items) >= int(total_count):
                    break
            except (TypeError, ValueError):
                pass
        if len(page_items) < per_page:
            break
        page += 1

    return items


def _file_items_from_payload(payload) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    files = payload.get("files")
    if isinstance(files, dict):
        items = files.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    items = payload.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _fetch_file_detail(file_id, *, headers: dict[str, str]) -> dict | None:
    response = requests.get(
        f"{MMF_API}/files/{file_id}",
        headers=headers,
        timeout=settings.METADATA_FETCH_TIMEOUT,
    )
    if not response.ok:
        return None
    payload = response.json()
    return payload if isinstance(payload, dict) else None


def _object_price_label(object_payload: dict) -> str:
    price = object_payload.get("price")
    if not isinstance(price, dict):
        return ""
    value = str(price.get("value") or "").strip()
    if not value or value in {"0", "0.0", "0.00"}:
        return ""
    symbol = str(price.get("symbol") or price.get("currency") or "").strip()
    return f"{symbol}{value}" if symbol else value


def _extract_object_id(url: str) -> str:
    match = re.search(r"myminifactory\.com/object/[\w-]+-(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"myminifactory\.com/object/(\d+)", url)
    return match.group(1) if match else ""
