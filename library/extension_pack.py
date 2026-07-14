"""Build a personalized browser extension zip for the current user/server."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

EXTENSION_DIR = settings.BASE_DIR / "extension"
PACK_FILES = (
    "manifest.json",
    "background.js",
    "content.js",
    "content.css",
    "popup.html",
    "popup.js",
)


def extension_version() -> str:
    manifest = EXTENSION_DIR / "manifest.json"
    if not manifest.exists():
        return "0.0.0"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("version", "0.0.0")
    except (json.JSONDecodeError, OSError):
        return "0.0.0"


def _host_permission(origin: str) -> str | None:
    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/*"


def build_extension_zip(*, api_base: str, api_token: str, server_origin: str) -> bytes:
    """Return a zip containing the extension with API credentials and server host permission."""
    buf = BytesIO()
    host_perm = _host_permission(server_origin.rstrip("/"))
    folder = "pick-a-print-extension"

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in PACK_FILES:
            path = EXTENSION_DIR / name
            if not path.exists():
                continue
            content = path.read_bytes()
            if name == "manifest.json":
                data = json.loads(content.decode("utf-8"))
                perms: list[str] = list(data.get("host_permissions", []))
                if host_perm and host_perm not in perms:
                    perms.insert(0, host_perm)
                data["host_permissions"] = perms
                content = (json.dumps(data, indent=2) + "\n").encode("utf-8")
            archive.writestr(f"{folder}/{name}", content)

        defaults = {"apiBase": api_base, "apiToken": api_token}
        archive.writestr(
            f"{folder}/defaults.json",
            json.dumps(defaults, indent=2) + "\n",
        )

        readme = EXTENSION_DIR / "README.md"
        if readme.exists():
            archive.writestr(f"{folder}/README.md", readme.read_bytes())

    return buf.getvalue()
