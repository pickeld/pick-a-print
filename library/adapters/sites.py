import json
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils.html import strip_tags

from library.adapters.base import FetchedMetadata, canonicalize_model_url, normalize_url, site_from_url

BAMBU_API = "https://api.bambulab.com"


def _plain_description(html: str) -> str:
    text = strip_tags(html or "").strip()
    return re.sub(r"\n{3,}", "\n\n", text)


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
        url = canonicalize_model_url(url)
        fetched = super().fetch_metadata(url)
        external_id = self._extract_id(url)
        title, designer = self._parse_printables_title(fetched.title)
        if not designer:
            author = fetched.metadata.get("author", "")
            if isinstance(author, dict):
                designer = author.get("name", "")

        likes = fetched.metadata.get("interactionStatistic", "")
        extra = {
            "likes": likes,
            "platform": "printables",
        }

        return FetchedMetadata(
            title=title,
            designer=str(designer) if designer else "",
            license=fetched.license,
            thumbnail_url=fetched.thumbnail_url,
            source_site="printables.com",
            external_id=external_id,
            metadata={**fetched.metadata, **extra},
        )

    def _parse_printables_title(self, raw: str) -> tuple[str, str]:
        designer = ""
        title = raw.strip()
        if " by " in title:
            title, rest = title.split(" by ", 1)
            designer = rest.split(" | ", 1)[0].strip()
        if " | " in title:
            title = title.split(" | ", 1)[0]
        return title.strip(), designer

    def _extract_id(self, url: str) -> str:
        match = re.search(r"/model/(\d+)", url)
        return match.group(1) if match else ""


class MakerWorldAdapter(GenericOpenGraphAdapter):
    site_name = "makerworld"

    def can_handle(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "makerworld.com" in host

    def fetch_metadata(self, url: str) -> FetchedMetadata:
        url = canonicalize_model_url(url)
        external_id = self._extract_id(url)
        if external_id:
            try:
                response = requests.get(
                    f"{BAMBU_API}/v1/design-service/design/{external_id}",
                    headers={"User-Agent": "pick-a-print/1.0"},
                    timeout=settings.METADATA_FETCH_TIMEOUT,
                )
                if response.ok:
                    design = response.json()
                    creator = (design.get("designCreator") or {}).get("name", "")
                    summary = design.get("summary") or design.get("summaryTranslated") or ""
                    tags = design.get("tagsTranslated") or design.get("tags") or []
                    return FetchedMetadata(
                        title=design.get("title") or url,
                        designer=creator,
                        license=str(design.get("license") or ""),
                        thumbnail_url=design.get("coverUrl", ""),
                        source_site="makerworld.com",
                        external_id=external_id,
                        metadata={
                            "platform": "makerworld",
                            "fetch_status": "complete",
                            "description": _plain_description(summary),
                            "source_tags": tags,
                        },
                    )
            except Exception:
                pass

        fetched = super().fetch_metadata(url)
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
        url = canonicalize_model_url(url)
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
        if match:
            slug = match.group(1)
            trailing = re.search(r"-(\d+)$", slug)
            if trailing:
                return trailing.group(1)
            return slug
        match = re.search(r"/m/(\d+)", url)
        return match.group(1) if match else ""


class ThingiverseAdapter(GenericOpenGraphAdapter):
    site_name = "thingiverse"

    def can_handle(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "thingiverse.com" in host

    def fetch_metadata(self, url: str) -> FetchedMetadata:
        url = canonicalize_model_url(url)
        external_id = self._extract_id(url)
        fetched = super().fetch_metadata(url)
        return FetchedMetadata(
            title=fetched.title,
            designer=fetched.designer,
            license=fetched.license,
            thumbnail_url=fetched.thumbnail_url,
            source_site="thingiverse.com",
            external_id=external_id,
            metadata={**fetched.metadata, "platform": "thingiverse"},
        )

    def _extract_id(self, url: str) -> str:
        match = re.search(r"/thing:(\d+)", url)
        return match.group(1) if match else ""


class Cults3dAdapter(GenericOpenGraphAdapter):
    site_name = "cults3d"

    def can_handle(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "cults3d.com" in host

    def fetch_metadata(self, url: str) -> FetchedMetadata:
        url = canonicalize_model_url(url)
        external_id = self._extract_id(url)
        fetched = super().fetch_metadata(url)
        return FetchedMetadata(
            title=fetched.title,
            designer=fetched.designer,
            license=fetched.license,
            thumbnail_url=fetched.thumbnail_url,
            source_site="cults3d.com",
            external_id=external_id,
            metadata={**fetched.metadata, "platform": "cults3d"},
        )

    def _extract_id(self, url: str) -> str:
        match = re.search(r"/3d-model/[\w-]+/([\w-]+)", url)
        return match.group(1) if match else ""
