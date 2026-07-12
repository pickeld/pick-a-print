from __future__ import annotations

from library.download_providers.base import DownloadProvider
from library.download_providers.makerworld import MakerWorldDownloadProvider
from library.download_providers.myminifactory import MyMiniFactoryDownloadProvider
from library.download_providers.printables import PrintablesDownloadProvider
from library.download_providers.thangs import ThangsDownloadProvider
from library.download_providers.thingiverse import ThingiverseDownloadProvider
from library.models import SavedModel

_PROVIDERS: list[DownloadProvider] = [
    PrintablesDownloadProvider(),
    ThangsDownloadProvider(),
    MakerWorldDownloadProvider(),
    ThingiverseDownloadProvider(),
    MyMiniFactoryDownloadProvider(),
]


def list_download_providers() -> list[DownloadProvider]:
    return list(_PROVIDERS)


def get_download_provider(model: SavedModel) -> DownloadProvider | None:
    site = (model.source_site or "").lower()
    for provider in _PROVIDERS:
        if site in provider.site_names:
            return provider
    return None
