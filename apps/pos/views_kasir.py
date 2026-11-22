"""Halaman di subdomain toko (``<toko>.hansproject.app``): halaman depan toko & kasir.

Di subdomain HANYA ada login kasir. Pengelolaan toko ada di hansproject.app/akun/toko/.
"""
from __future__ import annotations

import json
import logging
from functools import wraps

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.core import ratelimit
from apps.core.privacy import ip_hash

from . import cashier_auth, pages, palette, services
from .forms import CashierLoginForm
from .models import Store

log = logging.getLogger("hans.security")

MAX_BODY = 64 * 1024


def current_store(request) -> Store:
    name = getattr(request, "store_subdomain", None)
    if not name:
        raise Http404
    store = Store.objects.filter(subdomain=name).select_related("subscription").first()
    if store is None or store.state() == Store.STATE_DELETED:
        raise Http404
    return store


def cashier_required(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        store = current_store(request)
        cashier = cashier_auth.get_cashier(request, store)
        if cashier is None:
            if request.headers.get("Accept", "").startswith("application/json"):
                response = JsonResponse({"ok": False, "error": "Sesi berakhir. Silakan masuk lagi.", "login": True}, status=401)
            else:
                response = redirect("kasir:masuk")
        elif not store.can_sell:
            response = _locked(request, store)
        else:
            request.store, request.cashier = store, cashier
            response = func(request, *args, **kwargs)
        return cashier_auth.finish_response(request, response)

    return wrapper


def _locked(request, store: Store):
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"ok": False, "error": "Aplikasi kasir toko ini sedang terkunci."}, status=403)
    return render(request, "kasir/terkunci.html", {"store": store}, status=403)


# ---------------------------------------------------------------------------
# Halaman depan toko (Halaman toko buatan pemilik, atau "segera hadir")
# ---------------------------------------------------------------------------
@require_safe
def toko_home(request):
    """Halaman toko yang sudah diterbitkan pemilik; bila belum, halaman "segera hadir"."""
    store = current_store(request)
    page = pages.page_or_none(store)
    if page and page.is_published and page.live and store.can_sell:
        response = render(request, "halaman/page.html", {"view": pages.build_view(store, page.live), "store": store})
        response.store_indexable = True  # boleh muncul di Google (lihat StoreHostMiddleware)
    else:
        response = render(request, "kasir/toko_home.html", {"store": store, "available": store.can_sell})
    response["Cache-Control"] = "no-cache"
    return response


@require_safe
def robots_txt(request):
    store = Store.objects.filter(subdomain=getattr(request, "store_subdomain", None) or "").first()
    page = pages.page_or_none(store) if store else None
    if page and page.is_published and store.can_sell:
        body = "User-agent: *\nAllow: /$\nDisallow: /\n"
    else:
        body = "User-agent: *\nDisallow: /\n"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


@require_safe
def tema_css(request, version: str, color: str):
    """Palet warna halaman toko dari satu warna (lihat palette.py). Isinya hanya bergantung pada alamatnya."""
    if int(version) != palette.VERSION or not palette.normalize(color):
        raise Http404
    response = HttpResponse(palette.css(color), content_type="text/css; charset=utf-8")
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


# ---------------------------------------------------------------------------
# Masuk / keluar kasir
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
def masuk(request):
    store = current_store(request)
    if cashier_auth.get_cashier(request, store):
        return redirect("kasir:pos")
    if not store.can_sell:
        return _locked(request, store)
    form = CashierLoginForm(request.POST or None)
    error = ""
    if request.method == "POST":
        if not ratelimit.allow(f"kasir-masuk:{store.pk}:{ip_hash(request)}", limit=20, window=600):
            error = "Terlalu banyak percobaan masuk. Tunggu beberapa menit, lalu coba lagi."
        elif form.is_valid():
            result = cashier_auth.authenticate(store, form.cleaned_data["username"], form.cleaned_data["pin"])
            if result.cashier:
                response = redirect("kasir:pos")
                cashier_auth.login(request, response, result.cashier)
                log.info("Kasir #%s masuk di toko #%s.", result.cashier.pk, store.pk)
                return response
            error = result.error
            log.warning("Login kasir gagal di toko #%s. ip=%s", store.pk, ip_hash(request))
        else:
            error = "Isi nama pengguna dan PIN 6 angka."
    return render(
        request, "kasir/masuk.html", {"store": store, "form": form, "error": error}, status=400 if error else 200
    )


@require_POST
def keluar(request):
    store = current_store(request)
    cashier_auth.get_cashier(request, store)
    response = redirect("kasir:masuk")
    cashier_auth.logout(request, response)
    return response


# ---------------------------------------------------------------------------
# Layar kasir
# ---------------------------------------------------------------------------
@require_safe
@cashier_required
def pos(request):
    store = request.store
    products = [
        {"id": p.pk, "n": p.name, "p": p.price, "c": p.category_id or 0, "k": p.code}
        for p in store.products.filter(is_active=True).only("pk", "name", "price", "category_id", "code")
    ]
    used = {p["c"] for p in products}
    categories = [{"id": c.pk, "n": c.name} for c in store.categories.all() if c.pk in used]
    return render(
        request,
        "kasir/pos.html",
        {
            "store": store,
            "cashier": request.cashier,
            "pos_data": {"products": products, "categories": categories, "pay_url": reverse("kasir:bayar")},
            "in_grace": store.state() == Store.STATE_GRACE,
        },
    )


@require_POST
@cashier_required
def bayar(request):
    if len(request.body) > MAX_BODY:
        return JsonResponse({"ok": False, "error": "Data transaksi terlalu besar."}, status=413)
    if not ratelimit.allow(f"kasir-bayar:{request.cashier.pk}", limit=120, window=60):
        return JsonResponse({"ok": False, "error": "Terlalu cepat. Tunggu sebentar, lalu coba lagi."}, status=429)
    try:
        payload = json.loads(request.body or b"{}")
        result = services.checkout(request.cashier, payload)
    except (ValueError, services.CheckoutError) as exc:
        message = str(exc) if isinstance(exc, services.CheckoutError) else "Data transaksi tidak valid."
        return JsonResponse({"ok": False, "error": message}, status=400)
    sale = result.sale
    return JsonResponse(
        {
            "ok": True,
            "duplicate": result.duplicate,
            "sale": {
                "number": sale.number,
                "total": sale.total,
                "paid": sale.paid,
                "change": sale.change,
                "method": sale.get_method_display(),
                "receipt_url": reverse("kasir:struk", args=[sale.pk]),
            },
        },
        status=200 if result.duplicate else 201,
    )


@require_safe
@cashier_required
def riwayat(request):
    today = timezone.localdate()
    sales = services.sales_in_range(request.store, today, today)
    report = services.build_report(request.store, today, today)
    return render(
        request,
        "kasir/riwayat.html",
        {"store": request.store, "cashier": request.cashier, "sales": sales, "report": report},
    )


@require_safe
@cashier_required
def struk(request, pk: int):
    # Kasir hanya bisa membuka struk dari tokonya sendiri.
    sale = get_object_or_404(request.store.sales.prefetch_related("items"), pk=pk)
    return render(request, "kasir/struk.html", {"store": request.store, "sale": sale, "back_url": reverse("kasir:pos")})
