from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse
import re


@dataclass
class FetchedMetadata:
    title: str
    designer: str = ""
    license: str = ""
    thumbnail_url: str = ""
    source_site: str = ""
    external_id: str = ""
    metadata: dict = field(default_factory=dict)


class SourceAdapter(Protocol):
  site_name: str

  def can_handle(self, url: str) -> bool: ...

  def fetch_metadata(self, url: str) -> FetchedMetadata: ...


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL")
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"
    return normalized


PRINTABLES_TAB_SUFFIXES = ("/files", "/comments", "/remixes", "/make", "/collections")


def canonicalize_model_url(url: str) -> str:
    """Normalize site-specific model URLs to their canonical model page."""
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL")

    path = parsed.path.rstrip("/") or "/"
    host = parsed.netloc.lower()

    if "printables.com" in host:
        for suffix in PRINTABLES_TAB_SUFFIXES:
            if path.endswith(suffix):
                path = path[: -len(suffix)]
                break
        match = re.match(r"^(/model/\d+[^/]*)", path)
        if match:
            path = match.group(1)

    if "makerworld.com" in host:
        match = re.match(r"^(/(?:en/)?models/\d+)", path)
        if match:
            path = match.group(1).replace("/en/", "/")

    if "thingiverse.com" in host:
        match = re.match(r"^(/thing:\d+)", path)
        if match:
            path = match.group(1)

    if "myminifactory.com" in host:
        match = re.match(r"^(/object/[\w-]+-\d+)", path) or re.match(r"^(/object/\d+)", path)
        if match:
            path = match.group(1)

    if "thangs.com" in host:
        match = re.match(r"^(/m/\d+)", path)
        if match:
            path = match.group(1)
        else:
            match = re.match(r"^(/designer/[^/]+/3d-model/[^/]+)", path)
            if match:
                path = match.group(1)

    normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"
    return normalized


def site_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host
