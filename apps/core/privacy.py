"""Privasi pengunjung: alamat IP tidak pernah disimpan mentah."""
from __future__ import annotations

import hashlib
import hmac

from django.conf import settings
from django.utils import timezone


def _key() -> bytes:
    return hashlib.sha256(f"ip-hash|{settings.SECRET_KEY}".encode()).digest()


def client_ip(request) -> str:
    # REMOTE_ADDR sudah berisi IP asli pengunjung bila request datang lewat
    # reverse proxy tepercaya (diatur Waitress: trusted_proxy).
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def ip_hash(request, *, daily: bool = True) -> str:
    """Hash HMAC satu arah dari IP. Garamnya berganti setiap hari."""
    salt = timezone.localdate().isoformat() if daily else "static"
    digest = hmac.new(_key(), f"{salt}|{client_ip(request)}".encode(), hashlib.sha256)
    return digest.hexdigest()[:24]
