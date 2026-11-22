"""Dashboard pemilik toko di hansproject.app/akun/toko/<alamat>/.

Susunan: satu langganan (paket) berisi beberapa toko. SATU toko = SATU subdomain =
SATU akun kasir, dengan barang, transaksi, dan laporan sendiri. Semua pengelolaan
ada di sini; subdomain toko hanya untuk kasir.

Setiap view mengambil toko lewat ``owner_view`` (milik pelanggan yang login),
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
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.content import services as content_services
from apps.core.formatting import rupiah
from apps.members import auth
from apps.members.models import Order
from apps.members import charts
from apps.members.navigation import akun_tabs

from . import pages, palette, services
from .forms import (
    AddStoreOrderForm,
    CashierForm,
    CategoryForm,
    HighlightForm,
    NewStoreForm,
    ProductForm,
    RenewForm,
    StorePageForm,
    StoreSettingsForm,
    VoidForm,
)
from .models import CashierSession, Store, StorePage, Subscription

log = logging.getLogger("hans")

NOTICES = {
    "barang": "Barang tersimpan.",
    "barang-hapus": "Barang dihapus.",
    "kategori": "Kategori tersimpan.",
    "kategori-hapus": "Kategori dihapus. Barang di dalamnya sekarang tanpa kategori.",
    "kasir": "Akun kasir tersimpan.",
    "keluar-semua": "Semua perangkat kasir sudah dikeluarkan. Kasir perlu masuk lagi.",
    "toko-baru": "Toko baru siap. Isi barang dan bagikan alamat kasirnya ke kasir toko ini.",
    "aktif": "Toko diaktifkan kembali.",
    "nonaktif": "Toko dinonaktifkan. Kasirnya tidak bisa masuk sampai toko diaktifkan lagi.",
    "pengaturan": "Pengaturan toko tersimpan.",
    "batal": "Transaksi dibatalkan. Tidak lagi dihitung di laporan.",
    "halaman-draf": "Tersimpan sebagai draf. Lihat pratinjau, lalu tekan Terbitkan supaya pengunjung melihatnya.",
    "unggulan": "Barang unggulan ditambahkan (draf).",
    "unggulan-hapus": "Barang unggulan dihapus (draf).",
    "terbit": "Halaman toko terbit. Bagikan alamatnya ke pelanggan Anda.",
    "sembunyi": "Halaman toko disembunyikan. Pengunjung melihat halaman \"segera hadir\" lagi.",
    "terkunci": "Langganan sedang terkunci atau ditangguhkan, jadi data belum bisa diubah. Perpanjang dulu untuk membuka kembali.",
}

TABS = [
    ("ringkasan", "Ringkasan", "home", "toko:ringkasan"),
    ("barang", "Barang", "box", "toko:barang"),
    ("kasir", "Kasir", "user", "toko:kasir"),
    ("halaman", "Halaman toko", "globe", "toko:halaman"),
    ("transaksi", "Transaksi", "receipt", "toko:transaksi"),
    ("laporan", "Laporan", "chart", "toko:laporan"),
    ("pengaturan", "Pengaturan", "settings", "toko:pengaturan"),
]


def _with_query(url: str, **params) -> str:
    params = {k: v for k, v in params.items() if v not in (None, "")}
    return f"{url}?{urlencode(params)}" if params else url


def owner_view(tab: str, *, edit: bool = False):
    """Wajib login pelanggan & pemilik toko. ``edit``: tolak perubahan saat langganan terkunci."""

    def decorator(func):
        @auth.member_required
        @wraps(func)
        def wrapper(request, sub: str, *args, **kwargs):
            store = get_object_or_404(
                Store.objects.owned_by(request.member).select_related("subscription__package"), subdomain=sub
            )
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
        "subscription": store.subscription if store else None,
        "tabs": [
            {"key": key, "label": label, "icon": icon, "url": reverse(name, args=[store.subdomain]), "active": key == request.store_tab}
            for key, label, icon, name in TABS
        ] if store else [],
        "notice": NOTICES.get(request.GET.get("ok", "")),
        "renewal": _open_renewal(store) if store else None,
        "setup": pages.setup_steps(store) if store and store.can_edit else None,
        "akun_tabs": akun_tabs("toko", request.member),
    }
    ctx["setup_done"] = sum(step.done for step in ctx["setup"] or [])
    ctx.update(context or {})
    return render(request, template, ctx, status=status)


def _open_renewal(store: Store) -> Order | None:
    """Perpanjangan yang belum selesai untuk langganan toko ini (dari toko mana pun di dalamnya)."""
    return Order.objects.filter(
        store__subscription_id=store.subscription_id, order_type=Order.TYPE_RENEWAL, status__in=Order.OPEN_STATUSES
    ).first()


def _url(name: str, store: Store, *args, **query) -> str:
    return _with_query(reverse(name, args=[store.subdomain, *args]), **query)


def _subscriptions(member) -> list[Subscription]:
    """Langganan pelanggan (yang datanya belum dihapus) beserta tokonya."""
    subs = list(Subscription.objects.owned_by(member).not_deleted().select_related("package").prefetch_related("stores"))
    for sub in subs:
        sub.store_list = list(sub.stores.all())
        for store in sub.store_list:
            store.subscription = sub  # hindari query ulang
    return subs


# ---------------------------------------------------------------------------
# Daftar toko & ringkasan
# ---------------------------------------------------------------------------
@require_safe
@auth.member_required
def daftar(request):
    """Semua toko milik pelanggan, dikelompokkan per langganan (menu "Toko")."""
    request.store, request.store_tab = None, ""
    subs = _subscriptions(request.member)
    stores = [store for sub in subs for store in sub.store_list]
    overview = services.overview(stores)
    sums = {row["store"].pk: row for row in overview.rows}
    for store in stores:
        row = sums.get(store.pk, {})
        store.sum_today, store.sum_month = row.get("today_total", 0), row.get("month_total", 0)
    return _render(
        request,
        "toko/daftar.html",
        {
            "subscriptions": subs,
            # Ringkasan penjualan semua toko (dulu di Dashboard akun; Dashboard kini untuk semua layanan).
            "overview": overview if stores else None,
            "chart": charts.trend_bars(overview.trend, overview.trend_peak) if stores else None,
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
    cashier = store.cashier_or_none
    return _render(
        request,
        "toko/ringkasan.html",
        {
            "today": services.build_report(store, today, today),
            "month": services.build_report(store, today.replace(day=1), today),
            "cashier": cashier,
            "devices": CashierSession.objects.filter(cashier=cashier, expires_at__gt=timezone.now()).count() if cashier else 0,
            "product_count": store.products.filter(is_active=True).count(),
            "recent_sales": list(store.sales.all()[:5]),
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
# Akun kasir (satu per toko, boleh masuk di banyak perangkat)
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("kasir", edit=True)
def kasir(request, store: Store):
    cashier = store.cashier_or_none
    now = timezone.now()
    if request.method == "POST" and request.POST.get("aksi") == "keluar-semua":
        if cashier:
            cashier.sessions.all().delete()
            log.info("Toko #%s: semua perangkat kasir dikeluarkan pemilik.", store.pk)
        return redirect(_url("toko:kasir", store, ok="keluar-semua"))
    form = CashierForm(request.POST or None, instance=cashier, store=store)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
        log.info("Toko #%s: akun kasir disimpan.", store.pk)
        return redirect(_url("toko:kasir", store, ok="kasir"))
    sessions = list(cashier.sessions.filter(expires_at__gt=now).order_by("-last_seen_at")) if cashier else []
    return _render(
        request,
        "toko/kasir.html",
        {"form": form, "cashier": cashier, "sessions": sessions, "page_title": f"Akun kasir — {store.name}"},
        status=400 if form.errors else 200,
    )


# ---------------------------------------------------------------------------
# Transaksi
# ---------------------------------------------------------------------------
@require_safe
@owner_view("transaksi")
def transaksi(request, store: Store):
    period, start, end = services.parse_range(request.GET)
    sales = services.sales_in_range(store, start, end)
    page = Paginator(sales, 50).get_page(request.GET.get("hal"))
    return _render(
        request,
        "toko/transaksi.html",
        {
            "page": page,
            "report": services.build_report(store, start, end),
            **_filter_context(period, start, end),
            "page_title": "Transaksi",
        },
    )


def _filter_context(period, start, end) -> dict:
    return {
        "periods": services.PERIODS,
        "period": period,
        "start": start,
        "end": end,
        "query": urlencode(
            {k: v for k, v in {
                "periode": period if period != "pilih" else "",
                "dari": start.isoformat() if period == "pilih" else "",
                "sampai": end.isoformat() if period == "pilih" else "",
            }.items() if v}
        ),
    }


@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("transaksi", edit=True)
def transaksi_detail(request, store: Store, pk: int):
    sale = get_object_or_404(store.sales.prefetch_related("items"), pk=pk)
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
    sale = get_object_or_404(store.sales.prefetch_related("items"), pk=pk)
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
    report = services.build_report(store, start, end)
    peak = max((d["total"] for d in report.by_day), default=0)
    return _render(
        request,
        "toko/laporan.html",
        {
            "report": report,
            "peak": peak,
            **_filter_context(period, start, end),
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
    sales = services.sales_in_range(store, start, end).order_by("created_at")
    kind = "barang" if request.GET.get("jenis") == "barang" else "transaksi"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"{store.subdomain}-{kind}-{start:%Y%m%d}-{end:%Y%m%d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # supaya Excel membaca huruf dengan benar
    writer = csv.writer(response, delimiter=";")
    if kind == "barang":
        writer.writerow(["Nomor struk", "Waktu", "Barang", "Jumlah", "Harga", "Total", "Status"])
        for sale in sales.prefetch_related("items"):
            for item in sale.items.all():
                writer.writerow([
                    sale.number, timezone.localtime(sale.created_at).strftime("%Y-%m-%d %H:%M"),
                    _csv_safe(item.name), item.qty, item.price, item.line_total, sale.get_status_display(),
                ])
    else:
        writer.writerow(["Nomor struk", "Waktu", "Kasir", "Subtotal", "Diskon", "Total", "Dibayar", "Kembalian", "Cara bayar", "Status", "Alasan batal"])
        for sale in sales:
            writer.writerow([
                sale.number, timezone.localtime(sale.created_at).strftime("%Y-%m-%d %H:%M"),
                _csv_safe(sale.cashier_name), sale.subtotal, sale.discount, sale.total, sale.paid, sale.change,
                sale.get_method_display(), sale.get_status_display(), _csv_safe(sale.void_reason),
            ])
    return response


# ---------------------------------------------------------------------------
# Pengaturan, status toko & perpanjangan
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("pengaturan", edit=True)
def pengaturan(request, store: Store):
    form = StoreSettingsForm(request.POST or None, instance=store)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_url("toko:pengaturan", store, ok="pengaturan"))
    return _render(
        request, "toko/pengaturan.html",
        {"form": form, "free": store.subscription.stores_free, "page_title": "Pengaturan toko"},
        status=400 if form.errors else 200,
    )


@require_POST
@owner_view("pengaturan", edit=True)
def status_toko(request, store: Store):
    """Aktifkan / nonaktifkan toko (toko nonaktif tidak memakai kuota; datanya tetap)."""
    active = request.POST.get("aksi") == "aktifkan"
    try:
        services.set_store_active(store, active)
    except services.StoreError:
        return redirect(_url("toko:pengaturan", store))
    log.info("Toko #%s %s oleh pemilik.", store.pk, "diaktifkan" if active else "dinonaktifkan")
    return redirect(_url("toko:pengaturan", store, ok="aktif" if active else "nonaktif"))


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
        log.info("Perpanjangan %s untuk langganan #%s (paket %s).", order.code, store.subscription_id, package.code)
        return redirect(_with_query(reverse("akun:pesanan", args=[order.code]), ok="dibuat"))
    quotes = [(p, services.renewal_quote(store, p)) for p in form.fields["package"].queryset]
    return _render(
        request, "toko/perpanjang.html",
        {
            "form": form, "quotes": quotes, "addon": services.outlet_addon(),
            "siblings": list(store.subscription.stores.all()),
            "page_title": "Perpanjang langganan",
        },
        status=400 if form.errors else 200,
    )


# ---------------------------------------------------------------------------
# Tambah toko: pakai kuota langganan, beli toko tambahan, atau langganan baru
# ---------------------------------------------------------------------------
@require_safe
@auth.member_required
def tambah(request):
    request.store, request.store_tab = None, ""
    return _render(
        request,
        "toko/tambah.html",
        {"subscriptions": _subscriptions(request.member), "addon": services.outlet_addon(), "page_title": "Tambah toko"},
    )


@require_http_methods(["GET", "HEAD", "POST"])
@auth.member_required
def buat_toko(request, pk: int):
    """Toko baru dari sisa kuota: alamat (subdomain) sendiri + akun kasir sendiri, langsung aktif."""
    request.store, request.store_tab = None, ""
    sub = get_object_or_404(Subscription.objects.owned_by(request.member).not_deleted(), pk=pk)
    if not sub.can_edit or sub.stores_free <= 0:
        return redirect("toko:tambah")
    data = request.POST if request.method == "POST" else None
    store_form = NewStoreForm(data, prefix="toko")
    cashier_form = CashierForm(data, store=Store(subscription=sub), prefix="kasir")
    error = ""
    if request.method == "POST" and store_form.is_valid() and cashier_form.is_valid():
        try:
            with transaction.atomic():
                store = services.create_store(
                    sub, name=store_form.cleaned_data["name"], subdomain=store_form.cleaned_data["subdomain"]
                )
                cashier_form.store = store
                cashier_form.save()
        except services.StoreError as exc:
            error = str(exc)
        else:
            return redirect(_url("toko:ringkasan", store, ok="toko-baru"))
    return _render(
        request,
        "toko/buat.html",
        {"sub": sub, "store_form": store_form, "cashier_form": cashier_form, "error": error, "page_title": "Buat toko baru"},
        status=400 if (store_form.errors or cashier_form.errors or error) else 200,
    )


@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("ringkasan", edit=True)
def beli_toko(request, store: Store):
    addon = services.outlet_addon()
    if addon is None:
        raise Http404
    existing = Order.objects.filter(
        store__subscription_id=store.subscription_id, order_type=Order.TYPE_ADDON, status__in=Order.OPEN_STATUSES
    ).first()
    if existing:
        return redirect("akun:pesanan", code=existing.code)
    form = AddStoreOrderForm(request.POST or None)
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
        log.info("Pesanan tambahan toko %s untuk langganan #%s (%s).", order.code, store.subscription_id, qty)
        return redirect(_with_query(reverse("akun:pesanan", args=[order.code]), ok="dibuat"))
    return _render(
        request, "toko/beli_toko.html", {"form": form, "addon": addon, "page_title": "Beli toko tambahan"},
        status=400 if form.errors else 200,
    )


# ---------------------------------------------------------------------------
# Halaman toko (<toko>.hansproject.app/)
# ---------------------------------------------------------------------------
HALAMAN_ACTIONS = {"simpan", "template", "unggulan", "unggulan-hapus", "unggulan-naik", "unggulan-turun", "terbitkan", "sembunyikan"}


@require_http_methods(["GET", "HEAD", "POST"])
@owner_view("halaman", edit=True)
def halaman(request, store: Store):
    page = pages.get_page(store)
    form = StorePageForm(instance=page)
    hl_form = HighlightForm(page=page, prefix="unggulan")
    if request.method == "POST":
        action = request.POST.get("aksi", "")
        if action not in HALAMAN_ACTIONS:
            return HttpResponse("Aksi tidak dikenal.", status=400)
        back = _url("toko:halaman", store)
        if action == "simpan":
            form = StorePageForm(request.POST, request.FILES, instance=page)
            if form.is_valid():
                form.save()
                if request.POST.get("lalu") == "pratinjau":
                    return redirect(_url("toko:halaman-pratinjau", store))
                return redirect(_url("toko:halaman", store, ok="halaman-draf"))
        elif action == "template":  # dari pratinjau: "Pakai template ini"
            chosen = request.POST.get("template", "")
            if chosen in dict(StorePage.TEMPLATES):
                page.template = chosen
                page.save(update_fields=["template", "updated_at"])
            return redirect(_url("toko:halaman-pratinjau", store))
        elif action == "unggulan":
            hl_form = HighlightForm(request.POST, request.FILES, page=page, prefix="unggulan")
            if hl_form.is_valid():
                hl_form.save()
                return redirect(_url("toko:halaman", store, ok="unggulan") + "#unggulan")
        elif action == "unggulan-hapus":
            item = get_object_or_404(page.highlights, pk=request.POST.get("id") or 0)
            old = item.image.name
            item.delete()
            pages.cleanup(page, [old])
            return redirect(_url("toko:halaman", store, ok="unggulan-hapus") + "#unggulan")
        elif action in ("unggulan-naik", "unggulan-turun"):
            items = list(page.highlights.all())
            idx = next((i for i, h in enumerate(items) if str(h.pk) == request.POST.get("id")), None)
            if idx is None:
                raise Http404
            other = idx - 1 if action == "unggulan-naik" else idx + 1
            if 0 <= other < len(items):
                items[idx], items[other] = items[other], items[idx]
                with transaction.atomic():
                    for order, item in enumerate(items, start=1):
                        if item.order != order:
                            item.order = order
                            item.save(update_fields=["order"])
            return redirect(back + "#unggulan")
        elif action == "terbitkan":
            pages.publish(page)
            log.info("Halaman toko #%s diterbitkan.", store.pk)
            return redirect(_url("toko:halaman", store, ok="terbit"))
        elif action == "sembunyikan":
            pages.unpublish(page)
            return redirect(_url("toko:halaman", store, ok="sembunyi"))
    highlights = list(page.highlights.select_related("product"))
    return _render(
        request,
        "toko/halaman.html",
        {
            "page": page,
            "form": form,
            "hl_form": hl_form,
            "highlights": highlights,
            "max_highlights": StorePage.MAX_HIGHLIGHTS,
            "has_products": store.products.filter(is_active=True).exists(),
            "templates": [(value, label, StorePage.TEMPLATE_HINTS[value]) for value, label in StorePage.TEMPLATES],
            "presets": palette.PRESETS,
            "theme_url": pages.theme_url(page.color),
            "changed": pages.has_unpublished_changes(page),
            "page_title": f"Halaman toko — {store.name}",
        },
        status=400 if (form.errors or hl_form.errors) else 200,
    )


@require_safe
@owner_view("halaman")
def halaman_pratinjau(request, store: Store):
    """Pratinjau draf (hanya pemilik). ``?template=`` untuk mencoba template lain dengan isi toko sendiri."""
    page = pages.get_page(store)
    data = pages.draft_data(page)
    trying = request.GET.get("template", "")
    trying = trying if trying in dict(StorePage.TEMPLATES) and trying != page.template else ""
    if trying:
        data["template"] = trying
    response = render(request, "halaman/page.html", {
        "view": pages.build_view(store, data),
        "store": store,
        "preview": True,
        "trying": trying,
        "trying_label": dict(StorePage.TEMPLATES).get(trying, ""),
        "page": page,
        "changed": page.live is None or pages.has_unpublished_changes(page),
        "can_edit": store.can_edit,
    })
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
