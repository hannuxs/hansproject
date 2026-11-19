"""Dashboard pemilik toko di hansproject.app/akun/toko/<alamat>/.

Semua pengelolaan toko (barang, outlet & akun kasir, transaksi, laporan,
pengaturan struk, perpanjangan) ada di sini. Subdomain toko hanya untuk kasir.

Setiap view mengambil toko lewat ``_owned_store`` (milik pelanggan yang login),
lalu SEMUA data diambil dari relasi toko itu (``store.products``, dst.), jadi
pelanggan tidak bisa membuka data toko lain dengan menebak nomor.
"""
from __future__ import annotations

import csv
import logging
from functools import wraps
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q, RestrictedError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.content import services as content_services
from apps.members import auth
from apps.members.models import Order
from apps.members.navigation import akun_tabs

from . import services
from apps.core.formatting import rupiah

from .forms import (
    AddOutletOrderForm,
    CashierForm,
    CategoryForm,
    OutletForm,
    ProductForm,
    RenewForm,
    StoreSettingsForm,
    VoidForm,
)
from .models import Cashier, Store

log = logging.getLogger("hans")

NOTICES = {
    "barang": "Barang tersimpan.",
    "barang-hapus": "Barang dihapus.",
    "kategori": "Kategori tersimpan.",
    "kategori-hapus": "Kategori dihapus. Barang di dalamnya sekarang tanpa kategori.",
    "outlet": "Toko & akun kasir tersimpan.",
    "outlet-hapus": "Outlet dihapus.",
    "pengaturan": "Pengaturan toko tersimpan.",
    "batal": "Transaksi dibatalkan. Tidak lagi dihitung di laporan.",
    "terkunci": "Toko sedang terkunci atau ditangguhkan, jadi data belum bisa diubah. Perpanjang dulu untuk membuka kembali.",
}

TABS = [
    ("ringkasan", "Ringkasan", "home", "toko:ringkasan"),
    ("barang", "Barang", "box", "toko:barang"),
    ("outlet", "Toko & Kasir", "store", "toko:outlet"),
    ("transaksi", "Transaksi", "receipt", "toko:transaksi"),
    ("laporan", "Laporan", "chart", "toko:laporan"),
    ("pengaturan", "Pengaturan", "settings", "toko:pengaturan"),
]


def _with_query(url: str, **params) -> str:
    params = {k: v for k, v in params.items() if v not in (None, "")}
    return f"{url}?{urlencode(params)}" if params else url


def owner_view(tab: str, *, edit: bool = False):
    """Wajib login pelanggan & pemilik toko. ``edit``: tolak perubahan saat toko terkunci."""

    def decorator(func):
        @auth.member_required
        @wraps(func)
        def wrapper(request, sub: str, *args, **kwargs):
            store = get_object_or_404(Store.objects.owned_by(request.member).select_related("package"), subdomain=sub)
            if store.state() == Store.STATE_DELETED:
                raise Http404
            if edit and not store.can_edit and request.method == "POST":
                return redirect(_with_query(reverse("toko:ringkasan", args=[store.subdomain]), ok="terkunci"))
            request.store = store
            request.store_tab = tab
            return func(request, store, *args, **kwargs)

        return wrapper

    return decorator


def _render(request, template: str, context: dict | None = None, status: int = 200):
    snap = content_services.get_snapshot()
    store = getattr(request, "store", None)
    ctx = {
        "snap": snap,
        "site": snap.settings,
        "member": getattr(request, "_member", None),
        "store": store,
        "tabs": [
            {"key": key, "label": label, "icon": icon, "url": reverse(name, args=[store.subdomain]), "active": key == request.store_tab}
            for key, label, icon, name in TABS
        ] if store else [],
        "notice": NOTICES.get(request.GET.get("ok", "")),
        "renewal": _open_renewal(store) if store else None,
        "akun_tabs": akun_tabs("toko", request.member),
    }
    ctx.update(context or {})
    return render(request, template, ctx, status=status)


def _open_renewal(store: Store) -> Order | None:
    return store.orders.filter(order_type=Order.TYPE_RENEWAL, status__in=Order.OPEN_STATUSES).first()


def _url(name: str, store: Store, *args, **query) -> str:
    return _with_query(reverse(name, args=[store.subdomain, *args]), **query)


# ---------------------------------------------------------------------------
# Daftar toko & ringkasan
# ---------------------------------------------------------------------------
@require_safe
@auth.member_required
def daftar(request):
    """Semua toko milik pelanggan (menu "Toko")."""
    request.store, request.store_tab = None, ""
    stores = list(Store.objects.owned_by(request.member).not_deleted().select_related("package"))
    data = services.overview(stores)
    per_store = {}
    for row in data.outlets:
        item = per_store.setdefault(row["store"].pk, {"today": 0, "month": 0, "outlets": 0})
        item["today"] += row["today_total"]
        item["month"] += row["month_total"]
        item["outlets"] += 1 if row["outlet"].is_active else 0
    return _render(
        request,
        "toko/daftar.html",
        {
            "stores": [(store, per_store.get(store.pk, {"today": 0, "month": 0, "outlets": 0})) for store in stores],
            "pending": list(request.member.orders.filter(
                package_category="kasir", order_type=Order.TYPE_NEW, status__in=Order.OPEN_STATUSES
            )),
            "page_title": "Toko saya",
        },
    )


@require_safe
@owner_view("ringkasan")
def ringkasan(request, store: Store):
    today = timezone.localdate()
    return _render(
        request,
        "toko/ringkasan.html",
        {
            "today": services.build_report(store, today, today),
            "month": services.build_report(store, today.replace(day=1), today),
            "active_outlets": store.outlets.filter(is_active=True).count(),
            "has_cashier": store.cashiers.filter(is_active=True).exists(),
            "product_count": store.products.filter(is_active=True).count(),
            "recent_sales": list(store.sales.select_related("outlet")[:5]),
            "page_title": store.name,
        },
    )


# ---------------------------------------------------------------------------
# Barang & kategori
# ---------------------------------------------------------------------------
@require_safe
@owner_view("barang")
def barang(request, store: Store):
    products = store.products.select_related("category")
    q = request.GET.get("q", "").strip()[:60]
    cat = request.GET.get("kategori", "")
    if q:
        products = products.filter(Q(name__icontains=q) | Q(code__icontains=q))
    if cat == "tanpa":
        products = products.filter(category__isnull=True)
    elif cat.isdigit():
        products = products.filter(category_id=int(cat))
    page = Paginator(products, 50).get_page(request.GET.get("hal"))
    return _render(
        request,
        "toko/barang.html",
        {
            "page": page,
            "q": q,
            "cat": cat,
            "categories": list(store.categories.annotate(n=Count("products"))),
            "total": store.products.count(),
            "page_title": f"Barang — {store.name}",
        },
    )


@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("barang", edit=True)
def barang_form(request, store: Store, pk: int | None = None):
    product = get_object_or_404(store.products, pk=pk) if pk else None
    form = ProductForm(request.POST or None, instance=product, store=store)
    if request.method == "POST" and form.is_valid():
        form.save()
        if "lagi" in request.POST:
            return redirect(_url("toko:barang-baru", store, ok="barang"))
        return redirect(_url("toko:barang", store, ok="barang"))
    return _render(
        request,
        "toko/barang_form.html",
        {"form": form, "product": product, "page_title": "Ubah barang" if product else "Tambah barang"},
        status=400 if form.errors else 200,
    )


@require_POST
@owner_view("barang", edit=True)
def barang_hapus(request, store: Store, pk: int):
    get_object_or_404(store.products, pk=pk).delete()
    return redirect(_url("toko:barang", store, ok="barang-hapus"))


@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("barang", edit=True)
def kategori(request, store: Store, pk: int | None = None):
    category = get_object_or_404(store.categories, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, instance=category, store=store)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_url("toko:kategori", store, ok="kategori"))
    return _render(
        request,
        "toko/kategori.html",
        {
            "form": form,
            "category": category,
            "categories": list(store.categories.annotate(n=Count("products"))),
            "page_title": "Kategori barang",
        },
        status=400 if form.errors else 200,
    )


@require_POST
@owner_view("barang", edit=True)
def kategori_hapus(request, store: Store, pk: int):
    get_object_or_404(store.categories, pk=pk).delete()
    return redirect(_url("toko:kategori", store, ok="kategori-hapus"))


# ---------------------------------------------------------------------------
# Toko & akun kasir
# ---------------------------------------------------------------------------
@require_safe
@owner_view("outlet")
def outlet(request, store: Store):
    outlets = list(store.outlets.annotate(n_sales=Count("sales")).select_related("cashier"))
    active = sum(1 for o in outlets if o.is_active)
    return _render(
        request,
        "toko/outlet.html",
        {
            "outlets": outlets,
            "active_count": active,
            "can_add": active < store.outlet_limit,
            "page_title": "Toko & akun kasir",
        },
    )


@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("outlet", edit=True)
def outlet_form(request, store: Store, pk: int | None = None):
    outlet_obj = get_object_or_404(store.outlets, pk=pk) if pk else None
    if outlet_obj is None and store.outlets.filter(is_active=True).count() >= store.outlet_limit:
        return redirect(_url("toko:outlet", store))
    cashier = Cashier.objects.filter(outlet=outlet_obj).first() if outlet_obj else None
    data = request.POST if request.method == "POST" else None
    outlet_form_ = OutletForm(data, instance=outlet_obj, store=store, prefix="outlet")
    if outlet_obj is None and data is None:
        outlet_form_.initial["is_active"] = True
    cashier_form = CashierForm(data, instance=cashier, store=store, outlet=outlet_obj or store.outlets.model(store=store), prefix="kasir")
    if request.method == "POST" and outlet_form_.is_valid() and cashier_form.is_valid():
        with transaction.atomic():
            saved = outlet_form_.save()
            cashier_form.outlet = saved
            cashier_form.save()
            if not saved.is_active:
                saved_cashier = Cashier.objects.filter(outlet=saved).first()
                if saved_cashier:
                    saved_cashier.sessions.all().delete()
        log.info("Toko #%s: outlet #%s & akun kasir disimpan.", store.pk, saved.pk)
        return redirect(_url("toko:outlet", store, ok="outlet"))
    return _render(
        request,
        "toko/outlet_form.html",
        {
            "outlet_form": outlet_form_,
            "cashier_form": cashier_form,
            "outlet": outlet_obj,
            "cashier": cashier,
            "page_title": f"Outlet {outlet_obj.name}" if outlet_obj else "Tambah toko",
        },
        status=400 if (outlet_form_.errors or cashier_form.errors) else 200,
    )


@require_POST
@owner_view("outlet", edit=True)
def outlet_hapus(request, store: Store, pk: int):
    outlet_obj = get_object_or_404(store.outlets, pk=pk)
    if store.outlets.count() <= 1:
        return redirect(_url("toko:outlet", store))
    try:
        outlet_obj.delete()
    except (ProtectedError, RestrictedError):
        return redirect(_url("toko:outlet-ubah", store, outlet_obj.pk))
    return redirect(_url("toko:outlet", store, ok="outlet-hapus"))


# ---------------------------------------------------------------------------
# Transaksi
# ---------------------------------------------------------------------------
def _outlet_filter(request, store: Store):
    value = request.GET.get("outlet", "")
    return store.outlets.filter(pk=int(value)).first() if value.isdigit() else None


@require_safe
@owner_view("transaksi")
def transaksi(request, store: Store):
    period, start, end = services.parse_range(request.GET)
    outlet_obj = _outlet_filter(request, store)
    sales = services.sales_in_range(store, start, end, outlet_obj).select_related("outlet")
    page = Paginator(sales, 50).get_page(request.GET.get("hal"))
    return _render(
        request,
        "toko/transaksi.html",
        {
            "page": page,
            "report": services.build_report(store, start, end, outlet_obj),
            **_filter_context(store, period, start, end, outlet_obj),
            "page_title": "Transaksi",
        },
    )


def _filter_context(store, period, start, end, outlet_obj) -> dict:
    return {
        "periods": services.PERIODS,
        "period": period,
        "start": start,
        "end": end,
        "outlets": list(store.outlets.all()),
        "outlet": outlet_obj,
        "query": urlencode(
            {k: v for k, v in {
                "periode": period if period != "pilih" else "",
                "dari": start.isoformat() if period == "pilih" else "",
                "sampai": end.isoformat() if period == "pilih" else "",
                "outlet": outlet_obj.pk if outlet_obj else "",
            }.items() if v}
        ),
    }


@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("transaksi", edit=True)
def transaksi_detail(request, store: Store, pk: int):
    sale = get_object_or_404(store.sales.select_related("outlet").prefetch_related("items"), pk=pk)
    form = VoidForm(request.POST or None)
    if request.method == "POST" and not sale.is_void and form.is_valid():
        services.void_sale(sale, form.cleaned_data["reason"])
        log.info("Toko #%s: transaksi %s dibatalkan pemilik.", store.pk, sale.number)
        return redirect(_url("toko:transaksi-detail", store, sale.pk, ok="batal"))
    return _render(
        request,
        "toko/transaksi_detail.html",
        {"sale": sale, "form": form, "page_title": f"Transaksi {sale.number}"},
        status=400 if form.errors else 200,
    )


@require_safe
@owner_view("transaksi")
def transaksi_struk(request, store: Store, pk: int):
    sale = get_object_or_404(store.sales.select_related("outlet").prefetch_related("items"), pk=pk)
    return render(
        request,
        "kasir/struk.html",
        {"store": store, "sale": sale, "back_url": _url("toko:transaksi-detail", store, sale.pk)},
    )


# ---------------------------------------------------------------------------
# Laporan
# ---------------------------------------------------------------------------
@require_safe
@owner_view("laporan")
def laporan(request, store: Store):
    period, start, end = services.parse_range(request.GET)
    outlet_obj = _outlet_filter(request, store)
    report = services.build_report(store, start, end, outlet_obj)
    peak = max((d["total"] for d in report.by_day), default=0)
    return _render(
        request,
        "toko/laporan.html",
        {
            "report": report,
            "peak": peak,
            **_filter_context(store, period, start, end, outlet_obj),
            "page_title": "Laporan penjualan",
        },
    )


def _csv_safe(value) -> str:
    """Cegah 'CSV injection': teks yang diawali = + - @ dianggap rumus oleh Excel."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@require_safe
@owner_view("laporan")
def laporan_unduh(request, store: Store):
    period, start, end = services.parse_range(request.GET)
    outlet_obj = _outlet_filter(request, store)
    sales = services.sales_in_range(store, start, end, outlet_obj).select_related("outlet").order_by("created_at")
    kind = "barang" if request.GET.get("jenis") == "barang" else "transaksi"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"{store.subdomain}-{kind}-{start:%Y%m%d}-{end:%Y%m%d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # supaya Excel membaca huruf dengan benar
    writer = csv.writer(response, delimiter=";")
    if kind == "barang":
        writer.writerow(["Nomor struk", "Waktu", "Outlet", "Barang", "Jumlah", "Harga", "Total", "Status"])
        for sale in sales.prefetch_related("items"):
            for item in sale.items.all():
                writer.writerow([
                    sale.number, timezone.localtime(sale.created_at).strftime("%Y-%m-%d %H:%M"), _csv_safe(sale.outlet.name),
                    _csv_safe(item.name), item.qty, item.price, item.line_total, sale.get_status_display(),
                ])
    else:
        writer.writerow(["Nomor struk", "Waktu", "Outlet", "Kasir", "Subtotal", "Diskon", "Total", "Dibayar", "Kembalian", "Cara bayar", "Status", "Alasan batal"])
        for sale in sales:
            writer.writerow([
                sale.number, timezone.localtime(sale.created_at).strftime("%Y-%m-%d %H:%M"), _csv_safe(sale.outlet.name),
                _csv_safe(sale.cashier_name), sale.subtotal, sale.discount, sale.total, sale.paid, sale.change,
                sale.get_method_display(), sale.get_status_display(), _csv_safe(sale.void_reason),
            ])
    return response


# ---------------------------------------------------------------------------
# Pengaturan & perpanjangan
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("pengaturan", edit=True)
def pengaturan(request, store: Store):
    form = StoreSettingsForm(request.POST or None, instance=store)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_url("toko:pengaturan", store, ok="pengaturan"))
    return _render(
        request, "toko/pengaturan.html", {"form": form, "page_title": "Pengaturan toko"}, status=400 if form.errors else 200
    )


@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("ringkasan")
def perpanjang(request, store: Store):
    existing = _open_renewal(store)
    if existing:
        return redirect("akun:pesanan", code=existing.code)
    form = RenewForm(request.POST or None, store=store)
    if request.method == "POST" and form.is_valid():
        package = form.cleaned_data["package"]
        quote = services.renewal_quote(store, package)
        order = Order.objects.create(
            member=request.member,
            order_type=Order.TYPE_RENEWAL,
            store=store,
            subdomain=form.cleaned_data["new_subdomain"],
            package=package,
            package_name=package.name,
            package_category=package.category,
            price_text=quote.text,
            amount=quote.amount,
            status=Order.STATUS_PAYMENT,
        )
        log.info("Perpanjangan %s untuk toko #%s (paket %s).", order.code, store.pk, package.code)
        return redirect(_with_query(reverse("akun:pesanan", args=[order.code]), ok="dibuat"))
    quotes = [(p, services.renewal_quote(store, p)) for p in form.fields["package"].queryset]
    return _render(
        request, "toko/perpanjang.html",
        {"form": form, "quotes": quotes, "addon": services.outlet_addon(), "page_title": "Perpanjang langganan"},
        status=400 if form.errors else 200,
    )


# ---------------------------------------------------------------------------
# Tambah toko (cabang): pakai kuota paket, beli tambahan, atau langganan baru
# ---------------------------------------------------------------------------
@require_safe
@auth.member_required
def tambah(request):
    request.store, request.store_tab = None, ""
    stores = list(Store.objects.owned_by(request.member).not_deleted().select_related("package"))
    return _render(
        request,
        "toko/tambah.html",
        {
            "stores": stores,
            "addon": services.outlet_addon(),
            "page_title": "Tambah toko",
        },
    )


@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("outlet", edit=True)
def beli_toko(request, store: Store):
    addon = services.outlet_addon()
    if addon is None:
        raise Http404
    existing = store.orders.filter(order_type=Order.TYPE_ADDON, status__in=Order.OPEN_STATUSES).first()
    if existing:
        return redirect("akun:pesanan", code=existing.code)
    form = AddOutletOrderForm(request.POST or None)
    if request.method == "POST" and store.can_edit and form.is_valid():
        qty = form.cleaned_data["quantity"]
        order = Order.objects.create(
            member=request.member,
            order_type=Order.TYPE_ADDON,
            store=store,
            quantity=qty,
            package_name="Tambahan toko",
            package_category="kasir",
            price_text=f"{rupiah(addon.price * qty)} ({qty} toko x {rupiah(addon.price)}{addon.unit})",
            amount=addon.price * qty,
            status=Order.STATUS_PAYMENT,
        )
        log.info("Pesanan tambahan toko %s untuk toko #%s (%s).", order.code, store.pk, qty)
        return redirect(_with_query(reverse("akun:pesanan", args=[order.code]), ok="dibuat"))
    return _render(
        request, "toko/beli_toko.html", {"form": form, "addon": addon, "page_title": "Beli toko tambahan"},
        status=400 if form.errors else 200,
    )
