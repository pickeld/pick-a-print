from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils import timezone as django_timezone

from library.models import SiteConfig

HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)
TEST_STALE_AFTER = timedelta(minutes=5)


@dataclass
class ScanWorkerTestResult:
    ok: bool
    host_reachable: bool
    celery_workers: int
    message: str


def normalize_jetson_host(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if "://" in value:
        parsed = urlparse(value)
        value = parsed.hostname or ""
    if "/" in value:
        value = value.split("/", 1)[0]
    if value.startswith("[") and "]" in value:
        return value[1 : value.index("]")]
    if ":" in value:
        host_part, port_part = value.rsplit(":", 1)
        if port_part.isdigit():
            value = host_part
    return value.strip()


def validate_jetson_host(host: str) -> str | None:
    if not host:
        return "Enter a Jetson hostname or IP address."
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    if HOSTNAME_RE.match(host):
        return None
    return "Invalid hostname or IP address."


def validate_jetson_health_token(token: str) -> str | None:
    if not token:
        return "Set a health check token (must match JETSON_HEALTH_TOKEN on the Jetson)."
    if len(token) < 16:
        return "Health check token must be at least 16 characters."
    return None


def _count_workers_via_redis_clients() -> int:
    import redis
    from urllib.parse import urlparse

    broker = os.getenv("SCAN_CELERY_BROKER_URL", settings.SCAN_CELERY_BROKER_URL)
    parsed = urlparse(broker)
    db = int((parsed.path or "/0").lstrip("/") or "0")
    client = redis.Redis(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        db=0,
        socket_connect_timeout=3,
    )
    workers = 0
    for entry in client.client_list():
        if int(entry.get("db", -1)) != db:
            continue
        if entry.get("cmd") in {"brpop", "blpop", "bzpopmin"}:
            workers += 1
    return workers


def count_celery_scan_workers() -> tuple[int, str | None]:
    try:
        from kombu import Connection

        from app.workers.celery_app import celery_app

        broker = os.getenv("SCAN_CELERY_BROKER_URL", settings.SCAN_CELERY_BROKER_URL)
        with Connection(broker) as conn:
            inspect = celery_app.control.inspect(connection=conn, timeout=3.0)
            ping = inspect.ping() or {}
            if ping:
                return len(ping), None
    except Exception as exc:
        inspect_error = str(exc)
    else:
        inspect_error = None

    try:
        workers = _count_workers_via_redis_clients()
        if workers:
            return workers, None
    except Exception as exc:
        redis_error = str(exc)
        if inspect_error:
            return 0, f"{inspect_error}; redis fallback: {redis_error}"
        return 0, redis_error

    if inspect_error:
        return 0, inspect_error
    return 0, None


def probe_jetson_health(host: str, port: int, *, token: str = "", timeout: float = 5.0) -> tuple[bool, str]:
    host_error = validate_jetson_host(host)
    if host_error:
        return False, host_error

    url = f"http://{host}:{port}/health"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        return False, f"Could not reach {host}:{port} ({exc})"

    if response.status_code == 401:
        return False, "Health check unauthorized — verify the token matches JETSON_HEALTH_TOKEN on the Jetson."

    if response.status_code != 200:
        return False, f"Health check returned HTTP {response.status_code}"

    try:
        payload = response.json()
    except ValueError:
        return False, "Health endpoint did not return JSON"

    if payload.get("status") != "ok":
        return False, "Health endpoint returned an unexpected status"

    return True, f"Reachable at {host}:{port}"


def run_jetson_connection_test(
    *,
    host: str,
    port: int,
    token: str = "",
) -> ScanWorkerTestResult:
    host = normalize_jetson_host(host)
    host_reachable, host_message = probe_jetson_health(host, port, token=token)
    worker_count, worker_error = count_celery_scan_workers()

    if not host_reachable:
        message = host_message
    elif worker_count == 0:
        message = worker_error or "Jetson is reachable but no scan worker is connected to Redis."
    else:
        message = f"{host_message}; {worker_count} scan worker(s) connected."

    return ScanWorkerTestResult(
        ok=host_reachable and worker_count > 0,
        host_reachable=host_reachable,
        celery_workers=worker_count,
        message=message,
    )


def _test_is_stale(config: SiteConfig) -> bool:
    if not config.last_test_at:
        return True
    return django_timezone.now() - config.last_test_at > TEST_STALE_AFTER


def save_connection_test_result(config: SiteConfig, result: ScanWorkerTestResult) -> SiteConfig:
    config.last_test_at = django_timezone.now()
    config.last_test_ok = result.ok
    config.last_test_message = result.message
    config.save(
        update_fields=[
            "last_test_at",
            "last_test_ok",
            "last_test_message",
        ]
    )
    return config


def refresh_jetson_connection_test(config: SiteConfig | None = None) -> ScanWorkerTestResult:
    config = config or SiteConfig.get()
    result = run_jetson_connection_test(
        host=config.jetson_host,
        port=config.jetson_health_port,
        token=config.jetson_health_token,
    )
    save_connection_test_result(config, result)
    return result


def scan_worker_status() -> dict:
    config = SiteConfig.get()
    worker_count, _ = count_celery_scan_workers()
    return {
        "jetson_enabled": config.jetson_enabled,
        "jetson_host": config.jetson_host,
        "jetson_health_port": config.jetson_health_port,
        "has_health_token": bool(config.jetson_health_token),
        "last_test_at": config.last_test_at.isoformat() if config.last_test_at else None,
        "last_test_ok": config.last_test_ok,
        "last_test_message": config.last_test_message,
        "celery_workers": worker_count,
        "ready": is_scan_worker_ready(config=config, worker_count=worker_count),
    }


def is_scan_worker_ready(*, config: SiteConfig | None = None, worker_count: int | None = None) -> bool:
    config = config or SiteConfig.get()
    if config.jetson_enabled:
        return bool(config.jetson_host and config.last_test_ok)
    if worker_count is None:
        worker_count, _ = count_celery_scan_workers()
    return worker_count > 0


def assert_scan_worker_ready() -> None:
    from library.scan_services import ScanError

    config = SiteConfig.get()

    if config.jetson_enabled:
        if not config.jetson_host:
            raise ScanError(
                "Jetson GPU scanning is enabled but no address is configured. "
                "Set the Jetson domain in Settings."
            )

        host_error = validate_jetson_host(config.jetson_host)
        if host_error:
            raise ScanError(host_error)

        token_error = validate_jetson_health_token(config.jetson_health_token)
        if token_error:
            raise ScanError(token_error)

        if not config.last_test_ok or _test_is_stale(config):
            result = refresh_jetson_connection_test(config)
            if not result.ok:
                raise ScanError(
                    result.message
                    or "Jetson connection test failed. Check Settings and try Test connection."
                )
        return

    worker_count, worker_error = count_celery_scan_workers()
    if worker_count == 0:
        detail = f" ({worker_error})" if worker_error else ""
        raise ScanError(
            "No scan worker is connected."
            f"{detail} Enable the Jetson worker in Settings or start the local scan worker."
        )
