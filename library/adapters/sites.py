import json
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings

from library.adapters.base import FetchedMetadata, normalize_url, site_from_url


class GenericOpenGraphAdapter:
    site_name = "generic"

    def can_handle(self, url: str) -> bool:
        return True

    def fetch_metadata(self, url: str) -> FetchedMetadata:
        url = normalize_url(url)
        response = requests.get(
            url,
            timeout=settings.METADATA_FETCH_TIMEOUT,
            headers={"User-Agent": "3d-collection-bot/0.1 (+https://github.com/local/3d-collection)"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        og = {tag.get("property", tag.get("name", "")): tag.get("content", "") for tag in soup.find_all("meta")}

        title = (
            og.get("og:title")
            or (soup.title.string.strip() if soup.title and soup.title.string else "")
            or url
        )
        thumbnail = og.get("og:image", "")
        description = og.get("og:description", "") or og.get("description", "")

        metadata = {"description": description}
        metadata.update(self._extract_json_ld(soup))

        return FetchedMetadata(
            title=title,
            thumbnail_url=thumbnail,
            source_site=site_from_url(url),
            metadata=metadata,
        )

    def _extract_json_ld(self, soup: BeautifulSoup) -> dict:
        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k in ("author", "license", "keywords")}
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return {k: v for k, v in data[0].items() if k in ("author", "license", "keywords")}
        return {}


class PrintablesAdapter(GenericOpenGraphAdapter):
    site_name = "printables"

    def can_handle(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "printables.com" in host

    def fetch_metadata(self, url: str) -> FetchedMetadata:
        url = normalize_url(url)
        fetched = super().fetch_metadata(url)
        external_id = self._extract_id(url)
        designer = fetched.metadata.get("author", "")
        if isinstance(designer, dict):
            designer = designer.get("name", "")

        likes = fetched.metadata.get("interactionStatistic", "")
        extra = {
            "likes": likes,
            "platform": "printables",
        }

        return FetchedMetadata(
            title=fetched.title,
            designer=str(designer) if designer else "",
            license=fetched.license,
            thumbnail_url=fetched.thumbnail_url,
            source_site="printables.com",
            external_id=external_id,
            metadata={**fetched.metadata, **extra},
        )

    def _extract_id(self, url: str) -> str:
        match = re.search(r"/model/(\d+)", url)
        return match.group(1) if match else ""


class MakerWorldAdapter(GenericOpenGraphAdapter):
    site_name = "makerworld"

    def can_handle(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "makerworld.com" in host

    def fetch_metadata(self, url: str) -> FetchedMetadata:
        url = normalize_url(url)
        fetched = super().fetch_metadata(url)
        external_id = self._extract_id(url)

        return FetchedMetadata(
            title=fetched.title,
            designer=fetched.designer,
            license=fetched.license,
            thumbnail_url=fetched.thumbnail_url,
            source_site="makerworld.com",
            external_id=external_id,
            metadata={**fetched.metadata, "platform": "makerworld"},
        )

    def _extract_id(self, url: str) -> str:
        match = re.search(r"/models/(\d+)", url) or re.search(r"/model/(\d+)", url)
        return match.group(1) if match else ""


class ThangsAdapter(GenericOpenGraphAdapter):
    site_name = "thangs"

    def can_handle(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "thangs.com" in host

    def fetch_metadata(self, url: str) -> FetchedMetadata:
        url = normalize_url(url)
        fetched = super().fetch_metadata(url)
        external_id = self._extract_id(url)
        designer = fetched.metadata.get("author", "")
        if isinstance(designer, dict):
            designer = designer.get("name", "")

        return FetchedMetadata(
            title=fetched.title,
            designer=str(designer) if designer else "",
            license=fetched.license,
            thumbnail_url=fetched.thumbnail_url,
            source_site="thangs.com",
            external_id=external_id,
            metadata={**fetched.metadata, "platform": "thangs"},
        )

    def _extract_id(self, url: str) -> str:
        match = re.search(r"/model/([^/?#]+)", url) or re.search(r"/designer/[^/]+/([^/?#]+)", url)
        return match.group(1) if match else ""
