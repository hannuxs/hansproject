"""Setelan server produksi.

Mode ini MENOLAK berjalan bila konfigurasinya berbahaya, supaya keamanan
tidak bergantung pada pemilik yang harus "ingat menyalakan" sesuatu.
"""
from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_int

from .base import *  # noqa: F401,F403
from .base import (
    ADMIN_URL_PATH,
    ALLOWED_HOSTS,
    CONTENT_SECURITY_POLICY,
    DATABASES,
    SECRET_KEY,
    SITE_URL,
    STORE_BASE_DOMAIN,
    WEAK_ADMIN_PATHS,
)

DEBUG = False


def _validate() -> list[str]:
    problems: list[str] = []
    if env_bool("DEBUG", False):
        problems.append("DEBUG=true. Di server produksi DEBUG wajib false.")
    key = SECRET_KEY
    if not key or len(key) < 50 or len(set(key)) < 12 or key.lower().startswith(("ganti", "dev-only", "contoh")):
        problems.append(
            "SECRET_KEY kosong, terlalu pendek, atau masih contoh. Jalankan install.bat "
            "(otomatis membuat kunci acak) atau isi minimal 50 karakter acak."
        )
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        problems.append("ALLOWED_HOSTS belum diisi (contoh: hansproject.app,www.hansproject.app). Tanda * tidak diizinkan.")
    if not SITE_URL.startswith("https://"):
        problems.append("SITE_URL harus diawali https:// (contoh: https://hansproject.app).")
    if ADMIN_URL_PATH in WEAK_ADMIN_PATHS or ADMIN_URL_PATH.startswith("kelola-dev") or len(ADMIN_URL_PATH) < 10:
        problems.append(
            "ADMIN_URL_PATH mudah ditebak. Pakai alamat acak minimal 10 karakter "
            "(install.bat otomatis membuatkannya)."
        )
    db = DATABASES["default"]
    if db["USER"].lower() == "root":
        problems.append("DB_USER=root tidak diizinkan. Pakai user database khusus aplikasi.")
    if not db["PASSWORD"]:
        problems.append("DB_PASSWORD kosong. User database khusus aplikasi wajib memakai password.")
    return problems


_problems = _validate()
if _problems:
    raise ImproperlyConfigured(
        "\n\nMode produksi DITOLAK berjalan karena konfigurasi berbahaya di file .env:\n  - "
        + "\n  - ".join(_problems)
        + "\n"
    )

# Semua subdomain toko (warungbudi.hansproject.app, ...) diizinkan.
ALLOWED_HOSTS = [*ALLOWED_HOSTS, f".{STORE_BASE_DOMAIN}"]

# HTTPS wajib (domain .app memang selalu HTTPS).
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = env_int("HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
MEMBER_COOKIE_SECURE = True

CONTENT_SECURITY_POLICY = {**CONTENT_SECURITY_POLICY, "upgrade-insecure-requests": []}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
