"""AI Compass backend: explicit development/LAN profiles and strict RBAC."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY.startswith("REPLACE_WITH_"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a secure value")

DEBUG = False
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,api").split(",")
    if host.strip()
]
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Wildcard ALLOWED_HOSTS is not permitted")
# FUT-02: single protected Server, with explicit fail-closed exposure modes.
from .deployment_profiles import configuration, ProfileError
try:
    _profile = configuration(os.environ)
except ProfileError as exc:
    raise ImproperlyConfigured(str(exc)) from exc
AI_COMPASS_PROFILE = _profile["profile"]
ALLOWED_HOSTS = _profile["allowed_hosts"]
CSRF_TRUSTED_ORIGINS = _profile["csrf_origins"]
SECURE_PROXY_SSL_HEADER = _profile["proxy_header"]


INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "config",
    "restore_tracking",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "ai_compass"),
        "USER": os.environ.get("DB_USER", "ai_compass"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Development is HTTP on loopback only; production LAN requires TLS at Caddy.
# Internet exposure remains forbidden pending FUT-20 review.
SESSION_COOKIE_SECURE = _profile["secure"]
CSRF_COOKIE_SECURE = _profile["secure"]
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# PLAT-17: private writable storage (never served by Caddy or published as static).
EVIDENCE_STORE_ROOT = Path(os.environ.get("AI_COMPASS_EVIDENCE_ROOT", "/var/lib/ai-compass/evidence"))
EVIDENCE_MAX_BYTES = 16 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 0  # stream uploaded files via Django's temp file handler
DATA_UPLOAD_MAX_MEMORY_SIZE = 128 * 1024
# FUT-19: private directory for immutable archive artifacts (never served by Caddy).
ARCHIVE_STORE_ROOT = Path(os.environ.get("AI_COMPASS_ARCHIVE_ROOT", "/var/lib/ai-compass/archives"))
ARCHIVE_GRANT_TTL = 3600  # short-lived, artifact-scoped download grant lifetime (seconds)
ARCHIVE_JOB_TIMEOUT = int(os.environ.get("AI_COMPASS_ARCHIVE_JOB_TIMEOUT", "3600"))


# PLAT-33 mock adapter: intentionally impossible to switch on in a normal
# production Server. Runs only in a disposable restore staging identity.
import re
EXTERNAL_MOCK_IMPORT_ENABLED = bool(
    os.environ.get("AI_COMPASS_MOCK_IMPORT_ENABLED") == "1"
    and os.environ.get("AI_COMPASS_STAGING") == "1"
    and re.fullmatch(r"[0-9a-f]{16}", os.environ.get("AI_COMPASS_STAGING_CANDIDATE", ""))
    and DATABASES["default"]["NAME"] == "ai_compass_restore_verify"
    and DATABASES["default"]["USER"] == "ai_compass_restore"
    and DATABASES["default"]["HOST"] == "db"
)
