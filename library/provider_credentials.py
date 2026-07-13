"""Site-wide download provider credentials (DB with env fallback)."""

from __future__ import annotations

from django.conf import settings

from library.models import SiteConfig


def _db_value(field_name: str) -> str:
    return str(getattr(SiteConfig.get(), field_name, "") or "").strip()


def thingiverse_api_token() -> str:
    return _db_value("thingiverse_api_token") or getattr(settings, "THINGIVERSE_API_TOKEN", "") or ""


def bambu_lab_token() -> str:
    return _db_value("bambu_lab_token") or getattr(settings, "BAMBU_LAB_TOKEN", "") or ""


def myminifactory_api_key() -> str:
    return _db_value("myminifactory_api_key") or getattr(settings, "MYMINIFACTORY_API_KEY", "") or ""
