"""Alamat toko: ``<nama>.hansproject.app``.

Satu aplikasi melayani semua toko. Toko dikenali dari nama alamat (Host) yang
dibuka pengunjung, bukan dari port. Lihat docs/06-aplikasi-kasir.md.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError

SUBDOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,28})[a-z0-9]$")

# Nama yang tidak boleh dipakai toko: layanan sendiri, istilah teknis umum,
# dan nama yang bisa dipakai untuk menipu (mis. "login", "bayar").
RESERVED = frozenset(
    """
    www www1 www2 web m mobile app apps api apis cdn static media assets img images files upload uploads
    admin administrator root sysadmin panel kelola dashboard backend cms akun account accounts login masuk
    daftar register signup signin logout keluar auth oauth sso id user users member members profil profile
    kasir pos toko store shop stores shops outlet billing bayar pembayaran payment payments invoice tagihan
    mail email smtp imap pop pop3 webmail mx ns ns1 ns2 ns3 dns ftp sftp ssh vpn proxy cpanel whm autodiscover
    autoconfig hans hansproject hans-project official resmi support bantuan help cs halo info kontak contact
    blog news berita docs doc dokumentasi status statistik stats dev test tes uji staging demo beta alpha
    sandbox localhost local internal intranet secure security keamanan wpad git svn backup db database
    tambah baru daftar-toko
    """.split()
)


def normalize(value: str) -> str:
    return (value or "").strip().lower().rstrip(".")


def validate(value: str) -> str:
    """Kembalikan nama yang sudah dirapikan, atau ValidationError dengan pesan ramah."""
    name = normalize(value)
    suffix = "." + settings.STORE_BASE_DOMAIN
    if name.endswith(suffix):  # pelanggan mengetik alamat lengkap
        name = name[: -len(suffix)]
    if not name:
        raise ValidationError("Isi nama alamat toko.")
    if len(name) < 3 or len(name) > 30:
        raise ValidationError("Nama alamat toko harus 3 sampai 30 karakter.")
    if not SUBDOMAIN_RE.fullmatch(name):
        raise ValidationError(
            "Hanya boleh huruf kecil, angka, dan tanda minus (-), tanpa spasi. "
            "Tidak boleh diawali atau diakhiri tanda minus."
        )
    if "--" in name:
        raise ValidationError("Tanda minus tidak boleh dobel (--).")
    if name in RESERVED or name == settings.ADMIN_URL_PATH:
        raise ValidationError("Nama ini tidak bisa dipakai. Silakan pilih nama lain.")
    return name


def _site_parts() -> tuple[str, str]:
    parts = urlsplit(settings.SITE_URL)
    port = f":{parts.port}" if parts.port else ""
    return parts.scheme or "https", port


def store_url(subdomain: str, path: str = "/") -> str:
    """Contoh: https://warungbudi.hansproject.app/kasir/ (development: http://warungbudi.localhost:8432/kasir/)."""
    scheme, port = _site_parts()
    return f"{scheme}://{subdomain}.{settings.STORE_BASE_DOMAIN}{port}{path}"


def store_host(subdomain: str) -> str:
    """Alamat yang ditampilkan ke pelanggan, tanpa https://. Contoh: warungbudi.hansproject.app"""
    return f"{subdomain}.{settings.STORE_BASE_DOMAIN}"


def subdomain_from_host(host: str) -> str | None:
    """'warungbudi.hansproject.app:443' -> 'warungbudi'. Domain utama / www / lainnya -> None."""
    host = (host or "").lower().rsplit(":", 1)[0] if not host.startswith("[") else ""
    suffix = "." + settings.STORE_BASE_DOMAIN
    if not host.endswith(suffix):
        return None
    name = host[: -len(suffix)]
    if not name or "." in name or name == "www":
        return None
    return name
