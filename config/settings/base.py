"""Setelan bersama untuk semua mode (development, production, test)."""
from __future__ import annotations

import re

from django.core.exceptions import ImproperlyConfigured

from config.env import (
    APP_ENV,
    BASE_DIR,
    env_bool,
    env_int,
    env_list,
    env_path,
    env_str,
)

# ---------------------------------------------------------------------------
# Inti
# ---------------------------------------------------------------------------
SECRET_KEY = env_str("SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
SITE_URL = env_str("SITE_URL", "https://hansproject.app").rstrip("/")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") or [SITE_URL]

# fields.W161: "versi S&K" (SiteSettings.legal_version) memang sengaja bertanggal tetap.
SILENCED_SYSTEM_CHECKS = ["fields.W161"]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Semua tabel aplikasi (termasuk tabel bawaan Django) diberi awalan ini supaya
# tidak bertabrakan dengan tabel lain yang sudah ada di database server.
# JANGAN diubah setelah migrasi pertama dijalankan.
DB_TABLE_PREFIX = "hp_"

# ---------------------------------------------------------------------------
# Alamat panel pengelola (admin). Bukan /admin dan bisa diatur dari .env.
# ---------------------------------------------------------------------------
ADMIN_URL_PATH = env_str("ADMIN_URL_PATH", "kelola-dev").strip("/").lower()
WEAK_ADMIN_PATHS = {
    "admin", "administrator", "panel", "login", "masuk", "kelola", "dashboard",
    "wp-admin", "backend", "cms", "ganti-alamat-panel-ini",
}
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{3,62}", ADMIN_URL_PATH):
    raise ImproperlyConfigured(
        "ADMIN_URL_PATH hanya boleh berisi huruf kecil, angka, dan tanda minus (4-63 karakter)."
    )
ADMIN_REQUIRE_2FA = env_bool("ADMIN_REQUIRE_2FA", True)
ADMIN_SESSION_MINUTES = env_int("ADMIN_SESSION_MINUTES", 30)
ADMIN_SESSION_MAX_HOURS = env_int("ADMIN_SESSION_MAX_HOURS", 12)
LOGIN_MAX_FAILURES = env_int("LOGIN_MAX_FAILURES", 5)
LOGIN_LOCK_MINUTES = env_int("LOGIN_LOCK_MINUTES", 15)

# ---------------------------------------------------------------------------
# Aplikasi
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # apps.core HARUS paling atas: ia memasang awalan tabel "hp_".
    "apps.core",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.forms",
    "apps.accounts",
    "apps.content",
    "apps.web",
    "apps.members",
    "apps.pos",
    "apps.panel",
]

MIDDLEWARE = [
    # Paling atas: jawaban izin sertifikat HTTPS untuk Caddy (hanya dari 127.0.0.1).
    "apps.pos.middleware.TlsAskMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # <toko>.hansproject.app memakai URL khusus toko (hanya /kasir/).
    "apps.pos.middleware.StoreHostMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            # Sengaja minimal: halaman publik tidak menyentuh sesi/cookie.
            "context_processors": [
                "django.template.context_processors.request",
                "apps.core.context_processors.site",
            ],
            "builtins": ["apps.core.templatetags.ui"],
        },
    }
]
FORM_RENDERER = "apps.panel.forms.PanelFormRenderer"

# ---------------------------------------------------------------------------
# Database MariaDB
# ---------------------------------------------------------------------------
DB_NAME = env_str("DB_NAME", "hansproject_web")
DB_USER = env_str("DB_USER", "hansproject_app")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": env_str("DB_HOST", "127.0.0.1"),
        "PORT": env_int("DB_PORT", 3307),
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": env_str("DB_PASSWORD"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'",
            "isolation_level": "read committed",
            "connect_timeout": 10,
        },
        "TEST": {
            "NAME": f"test_{DB_NAME}",
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_ci",
        },
    }
}
MARIADB_BIN_DIR = env_str("MARIADB_BIN_DIR")

# ---------------------------------------------------------------------------
# Akun & password
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.AdminUser"
LOGIN_URL = "panel:login"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Sesi & cookie
# - Sesi Django (hp_panel) HANYA untuk panel pengelola (path panel saja).
# - Pelanggan memakai sesi sendiri (cookie hp_akun, lihat apps/members/auth.py).
# - Pengunjung yang belum login tidak mendapat cookie apa pun di halaman publik.
# ---------------------------------------------------------------------------
_PANEL_PATH = f"/{ADMIN_URL_PATH}/"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "hp_panel"
SESSION_COOKIE_PATH = _PANEL_PATH
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = ADMIN_SESSION_MINUTES * 60
SESSION_SAVE_EVERY_REQUEST = True  # batas waktu dihitung sejak aktivitas terakhir
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# Token formulir dipakai panel DAN halaman akun pelanggan, jadi berlaku di seluruh situs.
# (Halaman publik tidak berisi formulir, jadi tidak pernah membuat cookie ini.)
CSRF_COOKIE_NAME = "hp_token"
CSRF_COOKIE_PATH = "/"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_FAILURE_VIEW = "apps.web.views.csrf_failure"
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# ---------------------------------------------------------------------------
# Akun pelanggan: login dengan Google
# Client ID & Client Secret dibuat di Google Cloud Console (lihat README).
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = env_str("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = env_str("GOOGLE_CLIENT_SECRET")
# Kosong = otomatis SITE_URL + /akun/google/callback/ (harus sama persis dengan
# "Authorized redirect URIs" di Google Cloud Console).
GOOGLE_REDIRECT_URI = env_str("GOOGLE_REDIRECT_URI")
MEMBER_SESSION_DAYS = env_int("MEMBER_SESSION_DAYS", 30)
MEMBER_COOKIE_SECURE = False  # produksi: True

# ---------------------------------------------------------------------------
# Aplikasi kasir: setiap toko punya alamat <nama>.STORE_BASE_DOMAIN
# (produksi: warungbudi.hansproject.app). ALLOWED_HOSTS otomatis ditambah
# ".STORE_BASE_DOMAIN" di setiap file setelan.
# ---------------------------------------------------------------------------
STORE_BASE_DOMAIN = env_str("STORE_BASE_DOMAIN", "hansproject.app").strip(". ").lower()

# ---------------------------------------------------------------------------
# Header keamanan
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_REDIRECT_EXEMPT = [r"^sehat/$", r"^_tls/izin/$"]

# Content-Security-Policy ketat: tanpa 'unsafe-inline' / 'unsafe-eval'.
# Semua script & CSS berupa file terpisah yang di-host sendiri.
CONTENT_SECURITY_POLICY = {
    "default-src": ["'none'"],
    "script-src": ["'self'"],
    "style-src": ["'self'"],
    "img-src": ["'self'"],
    "font-src": ["'self'"],
    "connect-src": ["'self'"],
    "manifest-src": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'none'"],
    "object-src": ["'none'"],
}
PERMISSIONS_POLICY = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), encrypted-media=(), "
    "fullscreen=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), "
    "midi=(), payment=(), picture-in-picture=(), publickey-credentials-get=(), "
    "screen-wake-lock=(), sync-xhr=(), usb=(), interest-cohort=(), browsing-topics=()"
)

# ---------------------------------------------------------------------------
# Bahasa & waktu
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "id"
TIME_ZONE = env_str("TIME_ZONE", "Asia/Makassar")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# File statis & upload
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = env_path("MEDIA_DIR", "media")
# File pribadi (bukti bayar pelanggan): TIDAK punya alamat publik.
PRIVATE_MEDIA_ROOT = env_path("PRIVATE_MEDIA_DIR", "private")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
WHITENOISE_MAX_AGE = 60 * 60 * 24  # file tanpa hash: 1 hari; file ber-hash: 1 tahun
UPLOAD_MAX_BYTES = 3 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = UPLOAD_MAX_BYTES
DATA_UPLOAD_MAX_MEMORY_SIZE = 4 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 3000
FILE_UPLOAD_PERMISSIONS = 0o640

# ---------------------------------------------------------------------------
# Cache (data jarang berubah, jadi halaman publik disimpan di memori)
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "hansproject",
        "TIMEOUT": 600,
        "OPTIONS": {"MAX_ENTRIES": 2000},
    }
}
PAGE_CACHE_SECONDS = env_int("PAGE_CACHE_SECONDS", 600)

# ---------------------------------------------------------------------------
# Server produksi (Waitress) & folder kerja
# ---------------------------------------------------------------------------
SERVER_HOST = env_str("SERVER_HOST", "127.0.0.1")
SERVER_PORT = env_int("SERVER_PORT", 8432)
SERVER_THREADS = env_int("SERVER_THREADS", 8)
TRUSTED_PROXY = env_str("TRUSTED_PROXY", "127.0.0.1")
LOG_DIR = env_path("LOG_DIR", "logs")
BACKUP_DIR = env_path("BACKUP_DIR", "backups")
BACKUP_KEEP = env_int("BACKUP_KEEP", 14)
BACKUP_MAX_DAYS = env_int("BACKUP_MAX_DAYS", 60)
RUN_DIR = BASE_DIR / "run"

# ---------------------------------------------------------------------------
# Log (dengan rotasi otomatis, tanpa data sensitif)
# ---------------------------------------------------------------------------
LOG_LEVEL = env_str("LOG_LEVEL", "INFO").upper()
LOG_TO_FILE = env_bool("LOG_TO_FILE", True)


def build_logging(log_dir, level: str, to_file: bool) -> dict:
    handlers: dict = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "filters": ["redact"],
        }
    }
    app_handlers = ["console"]
    security_handlers = ["console"]
    if to_file:
        log_dir.mkdir(parents=True, exist_ok=True)
        common = {
            "class": "apps.core.logging.SafeRotatingFileHandler",
            "formatter": "plain",
            "filters": ["redact"],
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 10,
            "encoding": "utf-8",
        }
        handlers["app_file"] = {**common, "filename": str(log_dir / "app.log")}
        handlers["security_file"] = {**common, "filename": str(log_dir / "security.log")}
        app_handlers.append("app_file")
        security_handlers += ["security_file", "app_file"]
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"redact": {"()": "apps.core.logging.RedactSecretsFilter"}},
        "formatters": {
            "plain": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
        },
        "handlers": handlers,
        "root": {"handlers": app_handlers, "level": level},
        "loggers": {
            "django": {"handlers": app_handlers, "level": level, "propagate": False},
            # Jangan catat isi request yang ditolak (bisa berisi data sensitif).
            "django.security.DisallowedHost": {"handlers": app_handlers, "level": "ERROR", "propagate": False},
            "hans.security": {"handlers": security_handlers, "level": "INFO", "propagate": False},
            "hans": {"handlers": app_handlers, "level": level, "propagate": False},
            "waitress": {"handlers": app_handlers, "level": "WARNING", "propagate": False},
        },
    }


LOGGING = build_logging(LOG_DIR, LOG_LEVEL, LOG_TO_FILE)

__all__ = [name for name in dir() if name.isupper()] + ["APP_ENV", "build_logging"]
