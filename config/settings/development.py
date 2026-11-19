"""Setelan untuk komputer pengembangan."""
from config.env import env_bool, env_list, env_str

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, LOG_DIR, LOG_LEVEL, build_logging

DEBUG = env_bool("DEBUG", True)
# Komputer pengembangan: masuk panel cukup dengan password (tanpa kode Authenticator).
# Server produksi SELALU mewajibkan 2FA (lihat production.py). Nyalakan lagi: ADMIN_REQUIRE_2FA=true di .env.
ADMIN_REQUIRE_2FA = env_bool("ADMIN_REQUIRE_2FA", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost")
SITE_URL = env_str("SITE_URL", "http://127.0.0.1:8432").rstrip("/")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") or [SITE_URL]
# Toko dibuka di http://<nama>.localhost:8432 (Chrome/Edge/Firefox langsung mengenalinya).
STORE_BASE_DOMAIN = env_str("STORE_BASE_DOMAIN", "localhost").strip(". ").lower()
ALLOWED_HOSTS = [*ALLOWED_HOSTS, f".{STORE_BASE_DOMAIN}"]

# Kunci khusus pengembangan bila .env belum berisi SECRET_KEY.
# Mode production MENOLAK kunci ini.
SECRET_KEY = env_str("SECRET_KEY") or "dev-only-insecure-key-" + "x" * 40

INSTALLED_APPS = ["whitenoise.runserver_nostatic", *INSTALLED_APPS]  # noqa: F405

LOGGING = build_logging(LOG_DIR, LOG_LEVEL, env_bool("LOG_TO_FILE", False))
STATICFILES_DIRS = [BASE_DIR / "static"]

# File statis dilayani langsung dari folder static/ (tanpa collectstatic).
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
# Browser tidak menyimpan file statis di cache: perubahan CSS/JS/ikon langsung terlihat.
WHITENOISE_MAX_AGE = 0
