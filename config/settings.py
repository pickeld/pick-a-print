import os
from pathlib import Path

import mimetypes
from dotenv import load_dotenv

mimetypes.add_type("application/manifest+json", ".webmanifest")

load_dotenv(override=False)

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-only-change-in-production")
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

if os.getenv("USE_X_FORWARDED_PROTO", "").lower() in ("true", "1", "yes"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "corsheaders",
    "library",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "library.context_processors.sidebar_collections",
                "library.context_processors.upload_limits",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # postgres://user:pass@host:port/dbname
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": parsed.port or 5432,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "library" / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^chrome-extension://.*$",
]

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_TRACK_STARTED = True

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
SCAN_MAX_UPLOAD_MB = int(os.getenv("SCAN_MAX_UPLOAD_MB", "200"))
CLOUDFLARE_PROXY = os.getenv("CLOUDFLARE_PROXY", "true").lower() in ("true", "1", "yes")
CLOUDFLARE_MAX_UPLOAD_MB = int(os.getenv("CLOUDFLARE_MAX_UPLOAD_MB", "100"))
# Cloudflare rejects proxied request bodies above ~100 MB before they reach origin.
CHUNK_UPLOAD_SIZE_MB = int(os.getenv("CHUNK_UPLOAD_SIZE_MB", "25"))
EFFECTIVE_SCAN_MAX_UPLOAD_MB = (
    min(SCAN_MAX_UPLOAD_MB, max(1, CLOUDFLARE_MAX_UPLOAD_MB - 5))
    if CLOUDFLARE_PROXY
    else SCAN_MAX_UPLOAD_MB
)
_upload_limit_mb = max(MAX_UPLOAD_SIZE_MB, EFFECTIVE_SCAN_MAX_UPLOAD_MB, CHUNK_UPLOAD_SIZE_MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = _upload_limit_mb * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = _upload_limit_mb * 1024 * 1024

STATIC_ASSET_VERSION = os.getenv("STATIC_ASSET_VERSION", "3")

PIPELINE_DATA_DIR = Path(os.getenv("PIPELINE_DATA_DIR", str(BASE_DIR / "data" / "jobs")))
SCAN_CELERY_BROKER_URL = os.getenv("SCAN_CELERY_BROKER_URL", "redis://redis:6379/1")

# HTTP timeout for metadata fetching from external sites (seconds).
METADATA_FETCH_TIMEOUT = int(os.getenv("METADATA_FETCH_TIMEOUT", "15"))

DOWNLOAD_ALLOWED_HOSTS = tuple(
    host.strip()
    for host in os.getenv(
        "DOWNLOAD_ALLOWED_HOSTS",
        ",".join(
            [
                "files.printables.com",
                "media.printables.com",
                "*.printables.com",
                "thangs.com",
                "*.thangs.com",
                "api.thingiverse.com",
                "cdn.thingiverse.com",
                "*.thingiverse.com",
                "www.myminifactory.com",
                "myminifactory.com",
                "*.myminifactory.com",
                "makerworld.com",
                "*.makerworld.com",
                "public-cdn.bblmw.com",
                "*.amazonaws.com",
                "*.cloudfront.net",
            ]
        ),
    ).split(",")
    if host.strip()
)

THINGIVERSE_API_TOKEN = os.getenv("THINGIVERSE_API_TOKEN", "")
BAMBU_LAB_TOKEN = os.getenv("BAMBU_LAB_TOKEN", "")
MYMINIFACTORY_API_KEY = os.getenv("MYMINIFACTORY_API_KEY", "")

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"
