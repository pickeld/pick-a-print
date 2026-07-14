"""Connection tests for download provider integrations."""

from __future__ import annotations

from dataclasses import dataclass

import requests
from django.conf import settings

from library.adapters.printables_api import PRINTABLES_GRAPHQL_URL, PRINTABLES_USER_AGENT
from library.bambu_cloud import BambuCloudAuthError, validate_access_token
from library.download_providers.thangs import THANGS_HEADERS
from library.models import UserBambuCloudAuth
from library.provider_credentials import bambu_lab_token, myminifactory_api_key, thingiverse_api_token

THINGIVERSE_API = "https://api.thingiverse.com"
THANGS_TEST_MODEL_ID = "169424"


@dataclass(frozen=True)
class IntegrationTestResult:
    ok: bool
    message: str


def _timeout() -> int:
    return getattr(settings, "METADATA_FETCH_TIMEOUT", 15)


def test_printables() -> IntegrationTestResult:
    try:
        response = requests.post(
            PRINTABLES_GRAPHQL_URL,
            headers={"User-Agent": PRINTABLES_USER_AGENT},
            json={"query": "query { __typename }"},
            timeout=_timeout(),
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            return IntegrationTestResult(False, "Printables API returned an error.")
        return IntegrationTestResult(True, "Printables API is reachable.")
    except requests.RequestException as exc:
        return IntegrationTestResult(False, f"Could not reach Printables API: {exc}")


def test_thangs() -> IntegrationTestResult:
    try:
        response = requests.get(
            f"https://thangs.com/api/models/{THANGS_TEST_MODEL_ID}",
            headers=THANGS_HEADERS,
            timeout=_timeout(),
        )
        if response.status_code == 403:
            return IntegrationTestResult(
                False,
                "Thangs blocked the request (Cloudflare). Upload STL files manually if downloads fail.",
            )
        response.raise_for_status()
        return IntegrationTestResult(True, "Thangs API is reachable from this server.")
    except requests.RequestException as exc:
        return IntegrationTestResult(False, f"Could not reach Thangs API: {exc}")


def test_makerworld(user, *, access_token: str = "") -> IntegrationTestResult:
    token = access_token.strip() or bambu_lab_token(user)
    if not token:
        return IntegrationTestResult(
            False,
            "Connect Bambu Cloud or add a MakerWorld session token first.",
        )

    region = "global"
    if user and getattr(user, "is_authenticated", False):
        auth = UserBambuCloudAuth.objects.filter(user=user).first()
        if auth and auth.access_token == token:
            region = auth.region

    try:
        validate_access_token(token, region=region)
        return IntegrationTestResult(True, "MakerWorld credentials are valid.")
    except BambuCloudAuthError as exc:
        return IntegrationTestResult(False, str(exc))


def test_thingiverse(*, api_token: str = "") -> IntegrationTestResult:
    token = api_token.strip() or thingiverse_api_token()
    if not token:
        return IntegrationTestResult(False, "Add a Thingiverse API token first.")

    try:
        response = requests.get(
            f"{THINGIVERSE_API}/users/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_timeout(),
        )
        if response.status_code == 401:
            return IntegrationTestResult(False, "Thingiverse API token is invalid or expired.")
        response.raise_for_status()
        profile = response.json() or {}
        name = profile.get("name") or profile.get("screen_name") or "your account"
        return IntegrationTestResult(True, f"Thingiverse token works for {name}.")
    except requests.RequestException as exc:
        return IntegrationTestResult(False, f"Could not verify Thingiverse token: {exc}")


def test_myminifactory(*, api_key: str = "", client_secret: str = "", user=None) -> IntegrationTestResult:
    from library.myminifactory_oauth import (
        MyMiniFactoryAuthError,
        client_key,
        client_secret as stored_client_secret,
        default_oauth_callback_url,
        user_access_token,
        validate_access_token,
        validate_app_credentials,
        validate_app_slug,
    )

    slug = api_key.strip() or client_key()
    if client_secret.strip():
        secret = client_secret.strip()
    elif api_key.strip():
        secret = ""
    else:
        secret = stored_client_secret()
    access_token = user_access_token(user) if user else ""

    if not slug:
        return IntegrationTestResult(
            False,
            "Add your MyMiniFactory app slug (client key) from the developer app page first.",
        )

    try:
        validate_app_slug(slug)
    except MyMiniFactoryAuthError as exc:
        return IntegrationTestResult(False, str(exc))

    if access_token:
        try:
            profile = validate_access_token(access_token)
        except MyMiniFactoryAuthError as exc:
            return IntegrationTestResult(False, str(exc))

        name = profile.get("username") or profile.get("name") or "your account"
        return IntegrationTestResult(True, f"MyMiniFactory connected as {name}. Downloads are enabled.")

    if secret:
        try:
            validate_app_credentials(slug, secret, redirect_uri=default_oauth_callback_url())
        except MyMiniFactoryAuthError as exc:
            return IntegrationTestResult(False, str(exc))

    return IntegrationTestResult(
        False,
        "App slug looks valid, but your MyMiniFactory account is not connected yet. "
        "Click Connect MyMiniFactory above, sign in, then test again.",
    )


def test_cults3d() -> IntegrationTestResult:
    return IntegrationTestResult(
        False,
        "Cults3D does not expose file downloads via API. Save links for metadata only.",
    )


def run_integration_test(integration_id: str, user, payload: dict | None = None) -> IntegrationTestResult:
    payload = payload or {}
    tests = {
        "printables": test_printables,
        "thangs": test_thangs,
        "makerworld": lambda: test_makerworld(
            user,
            access_token=str(payload.get("bambu_lab_token", "")),
        ),
        "thingiverse": lambda: test_thingiverse(
            api_token=str(payload.get("thingiverse_api_token", "")),
        ),
        "myminifactory": lambda: test_myminifactory(
            api_key=str(payload.get("myminifactory_api_key", "")),
            client_secret=str(payload.get("myminifactory_client_secret", "")),
            user=user,
        ),
        "cults3d": test_cults3d,
    }
    test_fn = tests.get(integration_id)
    if not test_fn:
        return IntegrationTestResult(False, "Unknown integration.")
    return test_fn()
