"""Setelan untuk tes otomatis (manage.py test)."""
from .development import *  # noqa: F401,F403
from .base import build_logging, LOG_DIR

DEBUG = False
SECRET_KEY = "test-secret-key-" + "abcdefghijklmnopqrstuvwxyz0123456789"
SITE_URL = "https://hansproject.app"
STORE_BASE_DOMAIN = "hansproject.app"
ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost", "hansproject.app", ".hansproject.app"]
# Tes TIDAK PERNAH memakai kunci Google asli dari .env dan tidak menghubungi Google.
GOOGLE_CLIENT_ID = "uji-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "uji-client-secret"  # nosec B105 - nilai palsu khusus tes
GOOGLE_REDIRECT_URI = ""
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

PRIVATE_MEDIA_ROOT = Path(tempfile.gettempdir()) / "hansproject-test-private"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ADMIN_REQUIRE_2FA = True  # tes memakai alur 2FA seperti server produksi
LOGGING = build_logging(LOG_DIR, "CRITICAL", False)
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "whitenoise.runserver_nostatic"]  # noqa: F405

import logging  # noqa: E402

logging.disable(logging.CRITICAL)  # keluaran tes tetap bersih
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
