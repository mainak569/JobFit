"""
Django settings for jobfit_api.

Every environment-specific value comes from environment variables (optionally
loaded from a local .env file). See .env.example for the full list.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Real environment variables win over .env; .env is a local convenience only.
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default):
    value = os.environ.get(name, "")
    if value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# WHY default to False: if the variable is forgotten on a deploy, the failure
# mode should be "no debug pages", not "stack traces and settings shown to the
# public". Local development sets DJANGO_DEBUG=True in .env.
DEBUG = env_bool("DJANGO_DEBUG", default=False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-local-development-only"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is False.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "resumes",
    "analysis",
]

MIDDLEWARE = [
    # WHY first: CorsMiddleware must add headers to every response, including
    # ones short-circuited by later middleware, or the browser hides the error.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "jobfit_api.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "jobfit_api.wsgi.application"

# WHY DATABASE_URL: Render and Supabase both hand out a single connection URL.
# One variable is harder to get half-wrong than five separate HOST/PORT/USER
# settings. The default points at a local Postgres database named "jobfit".
DATABASES = {
    "default": dj_database_url.config(
        default="postgres://localhost:5432/jobfit",
        conn_max_age=600,
    )
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
STATIC_ROOT = BASE_DIR / "staticfiles"

# Local fallback for resume PDFs when R2 credentials are absent (storage/r2.py).
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cloudflare R2. Leave any of these empty to use MEDIA_ROOT instead.
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "")
R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "")

# WHY log to stdout: Render (like most PaaS hosts) captures stdout as the log
# stream. Writing to files would lose logs on every restart.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # boto and pdfminer are chatty at INFO; only their problems are useful.
        "botocore": {"level": "WARNING"},
        "boto3": {"level": "WARNING"},
        "pdfminer": {"level": "WARNING"},
    },
}

# ---------------------------------------------------------------- REST API

REST_FRAMEWORK = {
    # WHY no authentication classes: the API has no accounts. Leaving DRF's
    # default SessionAuthentication on would enforce CSRF tokens on every POST,
    # which a cross-origin React app on Vercel has no session cookie to supply.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": (
        ["rest_framework.renderers.JSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer"]
        if DEBUG
        else ["rest_framework.renderers.JSONRenderer"]
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # WHY throttle /api/analyze/: it is the one endpoint that does real CPU
    # work and writes rows on every call, and the demo is public with no login.
    # 20/hour is plenty for a person comparing a resume against several JDs and
    # stops a script from filling the free-tier database or pinning the single
    # worker. Counts live in the default local-memory cache, so each gunicorn
    # worker counts separately; acceptable at one or two workers, and the
    # first thing to move to Redis if the app ever scales out.
    "DEFAULT_THROTTLE_RATES": {"analyze": "20/hour"},
    # WHY NUM_PROXIES: behind Render's proxy, REMOTE_ADDR is the proxy's IP,
    # so every visitor would share one throttle bucket. Setting this to 1 in
    # production makes DRF read the client IP from X-Forwarded-For instead.
    "NUM_PROXIES": int(os.environ["NUM_PROXIES"]) if os.environ.get("NUM_PROXIES") else None,
    "EXCEPTION_HANDLER": "jobfit_api.exceptions.api_exception_handler",
}

# WHY an explicit list, never "*": the API accepts file uploads from a browser.
# A wildcard would let any site script uploads and analyses from its visitors'
# browsers against our quota.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", default="http://localhost:5173")
