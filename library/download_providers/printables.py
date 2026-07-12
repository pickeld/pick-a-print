from __future__ import annotations

import re

from library.adapters.printables_api import PrintablesApiError, list_stl_files, resolve_download_url
from library.download_providers.base import RemoteDownloadFile
from library.downloads import supported_remote_filename
from library.models import SavedModel


class PrintablesDownloadProvider:
    site_names = ("printables", "printables.com")

    def supports(self, model: SavedModel) -> bool:
        return (model.source_site or "").lower() in self.site_names

    def list_files(self, model: SavedModel) -> list[RemoteDownloadFile]:
        model_id = model.external_id or _extract_id(model.source_url or "")
        if not model_id:
            raise PrintablesApiError("Could not determine Printables model id")

        files: list[RemoteDownloadFile] = []
        for remote in list_stl_files(model_id):
            if not supported_remote_filename(remote.name):
                continue
            url = resolve_download_url(remote.file_id, remote.model_id)
            files.append(RemoteDownloadFile(name=remote.name, url=url, file_size=remote.file_size))
        return files


def _extract_id(url: str) -> str:
    match = re.search(r"/model/(\d+)", url)
    return match.group(1) if match else ""
