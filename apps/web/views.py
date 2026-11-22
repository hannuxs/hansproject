"""Halaman publik. Tidak ada cookie, tidak ada sesi, tidak ada data pribadi."""
from __future__ import annotations

import logging
import mimetypes
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.db.models import F
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.template import loader
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe, require_POST

from apps.content import services
from apps.content.models import ContactClick, LegalPage
from apps.core import ratelimit
from apps.core.privacy import ip_hash

from . import seo

log = logging.getLogger("hans")

def _cached_page(key: str, render) -> HttpResponse:
    """Render sekali, simpan HTML di cache server. Halaman publik tidak berisi data per pengunjung.

    Browser boleh menyimpan halaman, tapi WAJIB bertanya ulang ke server setiap kali dibuka
    (no-cache). Bila tidak berubah, server cukup menjawab 304 (ETag dari ConditionalGetMiddleware)
    tanpa mengirim ulang isinya. Jadi setiap update langsung terlihat oleh semua pengunjung.
    """
    html = None if settings.DEBUG else cache.get(services.PAGE_KEY_PREFIX + key)
    if html is None:
        html = render()
        if not settings.DEBUG:
            cache.set(services.PAGE_KEY_PREFIX + key, html, settings.PAGE_CACHE_SECONDS)
    response = HttpResponse(html)
    patch_cache_control(response, public=True, no_cache=True)
    return response


# Barang contoh untuk demo kasir di mockup HP (hanya ilustrasi).
DEMO_ITEMS = [
    ("☕", "Kopi Susu", 5000),
    ("🍜", "Mi Goreng", 3500),
    ("🥤", "Es Teh", 4000),
    ("🍞", "Roti Manis", 6000),
    ("🍚", "Nasi Bungkus", 12000),
    ("🥚", "Telur", 2500),
]


@require_safe
def home(request):
    def render():
        snap = services.get_snapshot()
        context = {
            "snap": snap,
            "site": snap.settings,
            "structured_data": seo.structured_data(snap),
            # Tab harga: (kunci, paket, halaman solusi, nama singkat)
            "pricing_tabs": [
                ("kasir", snap.pos_packages, reverse("web:kasir"), "Kasir"),
                ("sim", snap.sim_packages, reverse("web:sim"), "SIM"),
            ],
        }
        return render_to_string("web/home.html", context, request=request)

    return _cached_page("home", render)


SOLUTION_TEMPLATES = {"kasir": "web/kasir.html", "sim": "web/sim.html", "jasa": "web/jasa.html"}


@require_safe
def solution_page(request, key: str):
    """Halaman lengkap satu solusi: /aplikasi-kasir/, /sistem-informasi-manajemen/, /website-aplikasi/."""
    def render():
        snap = services.get_snapshot()
        context = {
            "snap": snap,
            "site": snap.settings,
            "demo_items": DEMO_ITEMS,
            "structured_data": seo.structured_data(snap, solution=key),
        }
        return render_to_string(SOLUTION_TEMPLATES[key], context, request=request)

    return _cached_page(key, render)


@require_safe
def legal_page(request, slug: str):
    def render():
        page = services.get_legal_page(slug)
        if page is None:
            raise Http404
        snap = services.get_snapshot()
        return render_to_string(
            "web/legal.html", {"page": page, "snap": snap, "site": snap.settings}, request=request
        )

    return _cached_page(slug, render)


@require_safe
def robots_txt(request):
    # Alamat panel sengaja TIDAK ditulis di sini (supaya tidak ketahuan).
    # Panel dilindungi header X-Robots-Tag: noindex.
    body = f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /akun/\nDisallow: /cek/\nDisallow: /w/\nDisallow: /surat/\n\nSitemap: {settings.SITE_URL}/sitemap.xml\n"
    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    patch_cache_control(response, public=True, max_age=86400)
    return response


@require_safe
def sitemap_xml(request):
    snap = services.get_snapshot()
    pages = [("/", snap.settings.updated_at)] + [
        (reverse(f"web:{key}"), snap.settings.updated_at) for key in SOLUTION_TEMPLATES
    ] + [
        (f"/{p.slug}/", p.updated_at) for p in LegalPage.objects.only("slug", "updated_at")
    ]
    body = render_to_string("web/sitemap.xml", {"pages": pages})
    response = HttpResponse(body, content_type="application/xml; charset=utf-8")
    patch_cache_control(response, public=True, max_age=3600)
    return response


@require_safe
def manifest(request):
    body = render_to_string("web/manifest.webmanifest", {})
    response = HttpResponse(body, content_type="application/manifest+json; charset=utf-8")
    patch_cache_control(response, public=True, max_age=86400)
    return response


@require_safe
def security_txt(request):
    site = services.get_snapshot().settings
    expires = (timezone.now() + timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z")
    contact = f"mailto:{site.email}" if site.email else site.instagram_profile_url
    body = (
        f"Contact: {contact}\nExpires: {expires}\nPreferred-Languages: id, en\n"
        f"Canonical: {settings.SITE_URL}/.well-known/security.txt\n"
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


@require_safe
def favicon(request):
    from django.shortcuts import redirect
    from django.templatetags.static import static

    response = redirect(static("img/favicon.ico"))
    patch_cache_control(response, public=True, max_age=86400)
    return response


@require_safe
def health(request):
    """Cek sederhana untuk pemantauan: 'ok' bila aplikasi & database jalan."""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("db-error", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


@csrf_exempt  # dikirim navigator.sendBeacon; tidak mengubah data pengunjung, hanya menambah angka
@require_POST
def contact_click(request):
    """Mencatat klik tombol kontak (DM Instagram): hanya (tanggal, tujuan, jumlah). Tanpa IP/cookie."""
    if request.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
        return HttpResponse(status=403)
    target = (request.POST.get("t") or "")[:40]
    if target not in services.get_snapshot().valid_targets:
        return HttpResponseBadRequest("target tidak dikenal")
    if not ratelimit.allow(f"klik:{ip_hash(request)}", limit=20, window=600):
        return HttpResponse(status=429)
    today = timezone.localdate()
    if not ContactClick.objects.filter(date=today, target=target).update(count=F("count") + 1):
        try:
            ContactClick.objects.create(date=today, target=target, count=1)
        except IntegrityError:  # dibuat bersamaan oleh request lain
            ContactClick.objects.filter(date=today, target=target).update(count=F("count") + 1)
    return HttpResponse(status=204)


def _mask(text: str) -> str:
    """'Sari Wulandari' -> 'Sa** Wu******' (cukup untuk dikenali pemiliknya, tidak membuka data lengkap)."""
    return " ".join(w[:2] + "*" * max(1, len(w) - 2) for w in (text or "").split()) or "–"


@require_safe
def cek_pesanan(request, token: str):
    """Halaman publik dari kode QR: memastikan pesanan benar terdaftar di HANS Project."""
    from apps.members.models import Order

    if not 10 <= len(token) <= 40 or not ratelimit.allow(f"cek:{ip_hash(request)}", limit=60, window=600):
        raise Http404
    order = Order.objects.filter(verify_token=token).select_related("member").first()
    # Bukti hanya sah setelah pembayaran dicek admin. Pesanan yang lalu dibatalkan tetap
    # bisa dicek (supaya bukti cetakan lama ketahuan tidak berlaku lagi).
    if order is None or not (order.has_verified_proof or order.status == Order.STATUS_CANCELLED):
        raise Http404
    snap = services.get_snapshot()
    response = HttpResponse(render_to_string("web/cek_pesanan.html", {
        "order": order,
        "buyer": _mask(order.customer_name),
        "business": _mask(order.customer_business),
        "snap": snap,
        "site": snap.settings,
    }, request=request))
    response["Cache-Control"] = "no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


ALLOWED_MEDIA_TYPES = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg"}


@require_safe
def media_file(request, path: str):
    """Menyajikan gambar hasil upload (QRIS, foto testimoni) dengan aman."""
    root = Path(settings.MEDIA_ROOT).resolve()
    file_path = (root / path).resolve()
    if root not in file_path.parents or not file_path.is_file():
        raise Http404
    content_type = ALLOWED_MEDIA_TYPES.get(file_path.suffix.lower()) or mimetypes.guess_type(file_path.name)[0]
    if content_type not in ALLOWED_MEDIA_TYPES.values():
        raise Http404
    response = FileResponse(file_path.open("rb"), content_type=content_type)
    response["Content-Disposition"] = "inline"
    response["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'none'; sandbox"
    patch_cache_control(response, public=True, max_age=86400)
    return response


# ---------------------------------------------------------------------------
# Halaman error: ramah, tanpa stack trace / versi software / path file.
# ---------------------------------------------------------------------------
ERRORS = {
    400: ("Permintaan tidak bisa diproses", "Ada yang salah dengan permintaan Anda. Silakan muat ulang halaman."),
    403: ("Akses ditolak", "Anda tidak punya izin untuk membuka halaman ini."),
    404: ("Halaman tidak ditemukan", "Maaf, halaman yang Anda cari tidak ada atau sudah dipindah. Coba mulai dari beranda."),
    "csrf": (
        "Formulir kedaluwarsa",
        "Demi keamanan, formulir perlu dimuat ulang. Kembali ke halaman sebelumnya, muat ulang, lalu coba lagi.",
    ),
}


def _error(request, status: int, key=None):
    title, text = ERRORS[key or status]
    context = {"error_code": status, "error_title": title, "error_text": text}
    if getattr(request, "store_subdomain", None):
        # Subdomain toko: halaman error sederhana tanpa menu situs utama.
        return HttpResponse(loader.render_to_string("kasir/error.html", context, request=request), status=status)
    try:
        snap = services.get_snapshot()
        context.update(snap=snap, site=snap.settings)
    except Exception:  # database mati, dll. Halaman error tetap harus tampil.  # nosec B110
        pass
    try:
        body = loader.render_to_string("errors/error.html", context, request=request)
    except Exception:
        body = f"<h1>{title}</h1><p>{text}</p>"
    return HttpResponse(body, status=status)


def error_400(request, exception=None):
    return _error(request, 400)


def error_403(request, exception=None):
    return _error(request, 403)


def error_404(request, exception=None):
    return _error(request, 404)


def error_500(request):
    # Tanpa akses database: render template statis saja.
    try:
        body = loader.render_to_string("errors/500.html", {})
    except Exception:
        body = "<h1>Terjadi kesalahan</h1><p>Silakan coba lagi beberapa saat lagi.</p>"
    return HttpResponse(body, status=500)


def csrf_failure(request, reason=""):
    log.warning("CSRF ditolak di %s", request.path)
    return _error(request, 403, "csrf")
