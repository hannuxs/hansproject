"""Memisahkan domain utama dan subdomain toko di satu aplikasi.

- ``hansproject.app`` (dan alamat lain)  -> URL biasa (config/urls.py)
- ``<toko>.hansproject.app``              -> URL toko (apps/pos/urls_store.py):
  hanya halaman toko dan ``/kasir/``. Panel, /akun/, dan halaman lain TIDAK ada di subdomain.
"""
from __future__ import annotations

import ipaddress

from django.http import HttpResponse

from . import subdomains
from .models import Store

TLS_ASK_PATH = "/_tls/izin/"


class TlsAskMiddleware:
    """Jawaban untuk Caddy (On-Demand TLS): "bolehkah membuat sertifikat HTTPS untuk alamat ini?"

    Hanya melayani permintaan langsung dari komputer server sendiri (Caddy memanggil
    ``http://127.0.0.1:<port>/_tls/izin/?domain=...``). Ditaruh paling atas supaya
    tidak terkena pemeriksaan ALLOWED_HOSTS / pengalihan HTTPS.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info != TLS_ASK_PATH:
            return self.get_response(request)
        if not _is_loopback(request.META.get("REMOTE_ADDR", "")) or request.META.get("HTTP_X_FORWARDED_FOR"):
            return HttpResponse(status=404)
        name = subdomains.subdomain_from_host(request.GET.get("domain", ""))
        allowed = bool(name) and Store.objects.not_deleted().filter(subdomain=name).exists()
        return HttpResponse("ok" if allowed else "tidak", status=200 if allowed else 404, content_type="text/plain")


def _is_loopback(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


class StoreHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        name = subdomains.subdomain_from_host(request.get_host())
        request.store_subdomain = name
        if name is None:
            return self.get_response(request)
        request.urlconf = "apps.pos.urls_store"
        response = self.get_response(request)
        # Halaman toko belum untuk mesin pencari (halaman promosi menyusul di fase 2),
        # dan halaman kasir berisi data toko: jangan disimpan di cache.
        response["X-Robots-Tag"] = "noindex, nofollow"
        if request.path.startswith("/kasir/"):
            response["Cache-Control"] = "no-store, max-age=0"
        return response
