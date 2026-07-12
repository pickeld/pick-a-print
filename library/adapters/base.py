from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse


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


def site_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host
