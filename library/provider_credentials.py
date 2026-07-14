"""Site-wide download provider credentials stored in SiteConfig."""

from __future__ import annotations

from library.models import SiteConfig


def _db_value(field_name: str) -> str:
    return str(getattr(SiteConfig.get(), field_name, "") or "").strip()


def thingiverse_api_token() -> str:
    return _db_value("thingiverse_api_token")


def bambu_lab_token(user=None) -> str:
    if user is not None and getattr(user, "is_authenticated", False):
        from library.bambu_cloud import user_access_token

        token = user_access_token(user)
        if token:
            return token
    return _db_value("bambu_lab_token")
