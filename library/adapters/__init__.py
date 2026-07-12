from urllib.parse import urlparse

from library.adapters.base import FetchedMetadata, SourceAdapter, normalize_url
from library.adapters.sites import GenericOpenGraphAdapter, MakerWorldAdapter, PrintablesAdapter, ThangsAdapter

_ADAPTERS: list[SourceAdapter] = [
    PrintablesAdapter(),
    MakerWorldAdapter(),
    ThangsAdapter(),
    GenericOpenGraphAdapter(),
]


def get_adapter(url: str) -> SourceAdapter:
    normalized = normalize_url(url)
    for adapter in _ADAPTERS:
        if adapter.can_handle(normalized):
            return adapter
    return GenericOpenGraphAdapter()


def fetch_metadata_from_url(url: str) -> FetchedMetadata:
    adapter = get_adapter(url)
    return adapter.fetch_metadata(normalize_url(url))


def detect_source_site(url: str) -> str:
    adapter = get_adapter(url)
    if adapter.site_name != "generic":
        return adapter.site_name
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host
