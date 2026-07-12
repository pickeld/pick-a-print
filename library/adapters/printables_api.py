from __future__ import annotations

from dataclasses import dataclass

import requests
from django.conf import settings

PRINTABLES_GRAPHQL_URL = "https://api.printables.com/graphql/"
PRINTABLES_USER_AGENT = "pick-a-print/1.0 (+https://github.com/local/pick-a-print)"

MODEL_FILES_QUERY = """
query ModelFiles($id: ID!) {
  model: print(id: $id) {
    stls { id name fileSize __typename }
  }
}
"""

GET_DOWNLOAD_LINK_MUTATION = """
mutation GetDownloadLink(
  $id: ID!,
  $modelId: ID!,
  $fileType: DownloadFileTypeEnum!,
  $source: DownloadSourceEnum!
) {
  getDownloadLink(id: $id, printId: $modelId, fileType: $fileType, source: $source) {
    ok
    errors { messages __typename }
    output { link ttl __typename }
    __typename
  }
}
"""


@dataclass(frozen=True)
class PrintablesRemoteFile:
    file_id: str
    model_id: str
    name: str
    file_size: int | None


class PrintablesApiError(Exception):
    pass


def _graphql(operation_name: str, query: str, variables: dict) -> dict:
    response = requests.post(
        PRINTABLES_GRAPHQL_URL,
        headers={"User-Agent": PRINTABLES_USER_AGENT},
        json={"operationName": operation_name, "query": query, "variables": variables},
        timeout=settings.METADATA_FETCH_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise PrintablesApiError(str(payload["errors"]))
    return payload.get("data") or {}


def list_stl_files(model_id: str) -> list[PrintablesRemoteFile]:
    data = _graphql("ModelFiles", MODEL_FILES_QUERY, {"id": model_id})
    model = data.get("model") or {}
    files: list[PrintablesRemoteFile] = []
    for item in model.get("stls") or []:
        file_id = item.get("id")
        name = (item.get("name") or "").strip()
        if not file_id or not name:
            continue
        files.append(
            PrintablesRemoteFile(
                file_id=str(file_id),
                model_id=str(model_id),
                name=name,
                file_size=item.get("fileSize"),
            )
        )
    return files


def resolve_download_url(file_id: str, model_id: str) -> str:
    data = _graphql(
        "GetDownloadLink",
        GET_DOWNLOAD_LINK_MUTATION,
        {
            "id": file_id,
            "modelId": model_id,
            "fileType": "stl",
            "source": "model_detail",
        },
    )
    result = data.get("getDownloadLink") or {}
    if not result.get("ok"):
        messages = []
        for error in result.get("errors") or []:
            messages.extend(error.get("messages") or [])
        raise PrintablesApiError("; ".join(messages) or "download link unavailable")

    link = (result.get("output") or {}).get("link")
    if not link:
        raise PrintablesApiError("download link missing from response")
    return link
