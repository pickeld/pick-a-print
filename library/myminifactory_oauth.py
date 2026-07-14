"""MyMiniFactory OAuth and API helpers."""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.urls import reverse

from library.models import SiteConfig, UserMyMiniFactoryAuth

logger = logging.getLogger(__name__)

MMF_API = "https://www.myminifactory.com/api/v2"
MMF_AUTH_BASE = "https://auth.myminifactory.com"
MMF_AUTHORIZE_URL = f"{MMF_AUTH_BASE}/web/authorize"
MMF_TOKEN_URL = f"{MMF_AUTH_BASE}/v1/oauth/tokens"
MMF_OAUTH_STATE_SESSION_KEY = "mmf_oauth_state"
_APP_SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class MyMiniFactoryError(Exception):
    pass


class MyMiniFactoryAuthError(MyMiniFactoryError):
    pass


def _timeout() -> int:
    return getattr(settings, "METADATA_FETCH_TIMEOUT", 15)


def client_key() -> str:
    return str(getattr(SiteConfig.get(), "myminifactory_api_key", "") or "").strip()


def client_secret() -> str:
    return str(getattr(SiteConfig.get(), "myminifactory_client_secret", "") or "").strip()


def app_credentials_configured() -> bool:
    return bool(client_key())


def oauth_callback_url(request) -> str:
    return request.build_absolute_uri(reverse("mmf_oauth_callback"))


def default_oauth_callback_url() -> str:
    override = str(getattr(settings, "MMF_OAUTH_CALLBACK_URL", "") or "").strip()
    if override:
        return override

    trusted = getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or []
    if trusted:
        return f"{str(trusted[0]).rstrip('/')}/settings/mmf/oauth/callback/"

    return "http://localhost:8000/settings/mmf/oauth/callback/"


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "token",
        "state": state,
    }
    return f"{MMF_AUTHORIZE_URL}?{urlencode(params)}"


def new_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def parse_api_error(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"

    for key in ("error_description", "detail", "error", "message", "title"):
        value = data.get(key)
        if value:
            return str(value)
    return f"HTTP {response.status_code}"


def validate_app_slug(client_id: str) -> None:
    key = client_id.strip()
    if not key:
        raise MyMiniFactoryAuthError("Add your MyMiniFactory app slug (client key) first.")
    if not _APP_SLUG_RE.match(key):
        raise MyMiniFactoryAuthError(
            "App slug format looks invalid. Use the OAuth client key from your MMF developer app "
            "(letters, numbers, underscores, hyphens only)."
        )


def _looks_like_legacy_api_key(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value.strip().lower()))


def _legacy_api_key_works(api_key: str) -> bool:
    response = requests.get(
        f"{MMF_API}/search",
        params={"key": api_key.strip(), "q": "test", "per_page": 1},
        timeout=_timeout(),
    )
    return response.status_code == 200


def validate_app_credentials(
    client_id: str,
    client_secret_value: str = "",
    *,
    redirect_uri: str | None = None,
) -> None:
    validate_app_slug(client_id)
    secret = client_secret_value.strip()
    if not secret:
        return

    if _looks_like_legacy_api_key(secret):
        if not _legacy_api_key_works(secret):
            raise MyMiniFactoryAuthError("That API key is not valid for MyMiniFactory.")
        return

    raise MyMiniFactoryAuthError(
        "MMF developer apps no longer expose a client secret. "
        "Save your app slug, then click Connect MyMiniFactory to sign in."
    )


def validate_app_key(api_key: str) -> None:
    """OAuth client keys are not API search keys — only check slug format here."""
    validate_app_slug(api_key)


def validate_access_token(access_token: str) -> dict:
    token = access_token.strip()
    if not token:
        raise MyMiniFactoryAuthError("Access token is required")

    response = requests.get(
        f"{MMF_API}/user",
        headers={"Authorization": f"Bearer {token}"},
        timeout=_timeout(),
    )
    if response.status_code in (401, 403):
        raise MyMiniFactoryAuthError("MyMiniFactory access token is invalid or expired.")
    response.raise_for_status()
    return response.json()


def exchange_authorization_code(
    *,
    client_id: str,
    client_secret_value: str,
    code: str,
    redirect_uri: str,
) -> dict:
    response = requests.post(
        MMF_TOKEN_URL,
        auth=(client_id.strip(), client_secret_value.strip()),
        data={
            "grant_type": "authorization_code",
            "code": code.strip(),
            "redirect_uri": redirect_uri,
        },
        timeout=_timeout(),
    )
    if response.status_code >= 400:
        raise MyMiniFactoryAuthError(parse_api_error(response))

    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise MyMiniFactoryAuthError("MyMiniFactory did not return an access token.")
    return data


def _token_expiry(expires_in: int) -> datetime | None:
    if expires_in > 0:
        return datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return None


def save_user_auth(user, *, token_data: dict, profile: dict | None = None) -> UserMyMiniFactoryAuth:
    profile = profile or {}
    expires_in = int(token_data.get("expires_in") or 0)
    auth, _ = UserMyMiniFactoryAuth.objects.update_or_create(
        user=user,
        defaults={
            "access_token": str(token_data["access_token"]),
            "refresh_token": str(token_data.get("refresh_token") or ""),
            "token_expiry": _token_expiry(expires_in),
            "mmf_user_id": str(token_data.get("user_id") or profile.get("id") or ""),
            "username": str(profile.get("username") or profile.get("name") or ""),
        },
    )
    return auth


def clear_user_auth(user) -> None:
    UserMyMiniFactoryAuth.objects.filter(user=user).delete()


def auth_status(user) -> dict:
    auth = UserMyMiniFactoryAuth.objects.filter(user=user).first()
    if not auth or not auth.access_token:
        return {"connected": False}

    return {
        "connected": True,
        "expired": auth.is_expired,
        "username": auth.username or "MyMiniFactory account",
        "updated_at": auth.updated_at.isoformat() if auth.updated_at else None,
    }


def user_access_token(user) -> str:
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    auth = UserMyMiniFactoryAuth.objects.filter(user=user).first()
    if auth and auth.access_token and not auth.is_expired:
        return auth.access_token.strip()
    return ""


def api_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}", "User-Agent": "pick-a-print/1.0"}
