"""Bambu Lab Cloud authentication (community-documented API)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings

from library.models import UserBambuCloudAuth

logger = logging.getLogger(__name__)

BAMBU_API_GLOBAL = "https://api.bambulab.com"
BAMBU_API_CHINA = "https://api.bambulab.cn"
TFA_URL_GLOBAL = "https://bambulab.com/api/sign-in/tfa"
TFA_URL_CHINA = "https://bambulab.cn/api/sign-in/tfa"
USER_AGENT = "pick-a-print/1.0"

_CF_MESSAGE = (
    "Bambu Cloud is temporarily blocking automated requests from your network. "
    "Wait a few minutes and try again, or sign in to bambulab.com once from a browser on the same network."
)


class BambuCloudError(Exception):
    pass


class BambuCloudAuthError(BambuCloudError):
    pass


def api_base(region: str) -> str:
    return BAMBU_API_CHINA if region == "china" else BAMBU_API_GLOBAL


def tfa_url(region: str) -> str:
    return TFA_URL_CHINA if region == "china" else TFA_URL_GLOBAL


def _timeout() -> int:
    return getattr(settings, "METADATA_FETCH_TIMEOUT", 15)


def _json_headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "User-Agent": USER_AGENT}


def _detect_cloudflare(response: requests.Response) -> str | None:
    body = response.text or ""
    if "Just a moment..." in body or "challenges.cloudflare.com" in body:
        return _CF_MESSAGE
    if response.status_code == 403 and "cf-mitigated" in response.headers:
        return _CF_MESSAGE
    if response.status_code == 503 and "cf-ray" in response.headers:
        return _CF_MESSAGE
    return None


def _parse_json(response: requests.Response) -> dict:
    try:
        return response.json()
    except ValueError as exc:
        cf = _detect_cloudflare(response)
        raise BambuCloudAuthError(cf or "Invalid response from Bambu Cloud") from exc


def login_request(*, email: str, password: str, region: str = "global") -> dict:
    response = requests.post(
        f"{api_base(region)}/v1/user-service/user/login",
        headers=_json_headers(),
        json={"account": email.strip(), "password": password},
        timeout=_timeout(),
    )
    data = _parse_json(response)

    if response.status_code == 200:
        login_type = data.get("loginType")
        tfa_key = data.get("tfaKey")

        if login_type == "tfa" or (tfa_key and login_type != "verifyCode"):
            return {
                "needs_verification": True,
                "verification_type": "totp",
                "tfa_key": tfa_key,
                "message": "Enter the code from your authenticator app.",
            }

        if login_type == "verifyCode":
            return {
                "needs_verification": True,
                "verification_type": "email",
                "tfa_key": None,
                "message": "Verification code sent to your email.",
            }

        if data.get("accessToken"):
            profile = fetch_profile(data["accessToken"], region=region)
            return {
                "needs_verification": False,
                "access_token": data["accessToken"],
                "refresh_token": data.get("refreshToken", ""),
                "expires_in": int(data.get("expiresIn") or 0),
                "profile": profile,
                "message": "Login successful.",
            }

    message = data.get("message") or data.get("error") or "Login failed"
    raise BambuCloudAuthError(str(message))


def verify_email_code(*, email: str, code: str, region: str = "global") -> dict:
    response = requests.post(
        f"{api_base(region)}/v1/user-service/user/login",
        headers=_json_headers(),
        json={"account": email.strip(), "code": code.strip()},
        timeout=_timeout(),
    )
    data = _parse_json(response)
    if response.status_code == 200 and data.get("accessToken"):
        profile = fetch_profile(data["accessToken"], region=region)
        return {
            "access_token": data["accessToken"],
            "refresh_token": data.get("refreshToken", ""),
            "expires_in": int(data.get("expiresIn") or 0),
            "profile": profile,
            "message": "Login successful.",
        }
    message = data.get("message") or "Verification failed"
    raise BambuCloudAuthError(str(message))


def verify_totp(*, tfa_key: str, code: str, region: str = "global") -> dict:
    response = requests.post(
        tfa_url(region),
        headers={**_json_headers(), "Accept": "application/json"},
        json={"tfaKey": tfa_key, "tfaCode": code.strip()},
        timeout=_timeout(),
    )
    if not (response.text or "").strip():
        raise BambuCloudAuthError("Bambu Cloud returned an empty response. Please try again.")

    data = _parse_json(response)
    access_token = data.get("accessToken") or data.get("token")
    if not access_token:
        for name, value in response.cookies.items():
            if "token" in name.lower() and value:
                access_token = value
                break

    if response.status_code == 200 and access_token:
        profile = fetch_profile(access_token, region=region)
        return {
            "access_token": access_token,
            "refresh_token": data.get("refreshToken", ""),
            "expires_in": int(data.get("expiresIn") or 0),
            "profile": profile,
            "message": "Login successful.",
        }

    message = data.get("message") or f"TOTP verification failed (HTTP {response.status_code})"
    if "expired" in message.lower():
        message = "TOTP session expired. Please sign in again."
    raise BambuCloudAuthError(str(message))


def fetch_profile(access_token: str, *, region: str = "global") -> dict:
    response = requests.get(
        f"{api_base(region)}/v1/design-user-service/my/preference",
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": USER_AGENT},
        timeout=_timeout(),
    )
    if response.status_code == 401:
        raise BambuCloudAuthError("Access token is invalid or expired")
    response.raise_for_status()
    return response.json()


def validate_access_token(access_token: str, *, region: str = "global") -> dict:
    token = access_token.strip()
    if not token:
        raise BambuCloudAuthError("Access token is required")
    return fetch_profile(token, region=region)


def _token_expiry(expires_in: int) -> datetime:
    if expires_in > 0:
        return datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return datetime.now(timezone.utc) + timedelta(days=90)


def save_user_cloud_auth(
    user,
    *,
    access_token: str,
    refresh_token: str = "",
    expires_in: int = 0,
    profile: dict | None = None,
    region: str = "global",
    email: str = "",
) -> UserBambuCloudAuth:
    profile = profile or {}
    auth, _ = UserBambuCloudAuth.objects.update_or_create(
        user=user,
        defaults={
            "access_token": access_token.strip(),
            "refresh_token": (refresh_token or "").strip(),
            "token_expiry": _token_expiry(expires_in),
            "bambu_uid": str(profile.get("uid") or ""),
            "bambu_name": str(profile.get("name") or profile.get("handle") or ""),
            "bambu_email": email.strip() or str(profile.get("name") or ""),
            "region": region if region in ("global", "china") else "global",
        },
    )
    return auth


def clear_user_cloud_auth(user) -> None:
    UserBambuCloudAuth.objects.filter(user=user).delete()


def cloud_auth_status(user) -> dict:
    auth = UserBambuCloudAuth.objects.filter(user=user).first()
    if not auth or not auth.access_token:
        return {"connected": False}

    expired = auth.is_expired
    return {
        "connected": True,
        "expired": expired,
        "name": auth.bambu_name or auth.bambu_email or "Bambu Cloud account",
        "region": auth.region,
        "updated_at": auth.updated_at.isoformat() if auth.updated_at else None,
    }


def user_access_token(user) -> str:
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    auth = UserBambuCloudAuth.objects.filter(user=user).first()
    if auth and auth.access_token and not auth.is_expired:
        return auth.access_token.strip()
    return ""
