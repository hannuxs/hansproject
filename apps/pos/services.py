"""Logika aplikasi kasir: aktivasi pesanan, transaksi, laporan, pembersihan data.

View hanya memanggil fungsi di sini, supaya aturan bisnis ada di satu tempat
dan mudah diuji.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Sum
from django.utils import timezone

from .models import (
    DELETE_AFTER_DAYS,
    MAX_PRICE,
    MAX_QTY,
    Cashier,
    CashierSession,
    Outlet,
    Product,
    Sale,
    SaleItem,
    Store,
    add_months,
)

log = logging.getLogger("hans")

MAX_ITEMS_PER_SALE = 200
MAX_PRODUCTS_PER_STORE = 5000
MAX_CATEGORIES_PER_STORE = 100
CLIENT_KEY_RE = re.compile(r"^[A-Za-z0-9-]{8,40}$")


# ---------------------------------------------------------------------------
# Alamat toko
# ---------------------------------------------------------------------------
def subdomain_taken(name: str, *, exclude_store=None, exclude_order=None) -> bool:
    """Nama sudah dipakai toko lain, atau sedang dipesan di pesanan yang belum selesai."""
    from apps.members.models import Order

    stores = Store.objects.filter(subdomain=name)
    if exclude_store is not None:
        stores = stores.exclude(pk=exclude_store.pk)
    orders = Order.objects.filter(subdomain=name, status__in=Order.OPEN_STATUSES)
    if exclude_order is not None:
        orders = orders.exclude(pk=exclude_order.pk)
    if exclude_store is not None:
        orders = orders.exclude(store=exclude_store)
    return stores.exists() or orders.exists()


# ---------------------------------------------------------------------------
# Aktivasi pesanan (dipanggil saat admin mengubah status pesanan menjadi Aktif)
# ---------------------------------------------------------------------------
class ActivationError(Exception):
    pass


def activation_problem(order, *, approve_subdomain: bool = False) -> str:
    """Pesan kesalahan bila pesanan kasir belum bisa diaktifkan; kosong bila bisa."""
    if order.member_id is None:
        return "Akun pemesan sudah dihapus, jadi pesanan ini tidak bisa diaktifkan."
    if order.is_addon:
        if order.store is None or order.store.state() == Store.STATE_DELETED:
            return "Toko untuk tambahan ini sudah tidak ada."
        return ""
    if order.is_renewal:
        store = order.store
        if store is None or store.state() == Store.STATE_DELETED:
            return "Data toko untuk perpanjangan ini sudah dihapus. Minta pelanggan membuat pesanan baru."
        if approve_subdomain and order.subdomain and subdomain_taken(order.subdomain, exclude_store=store, exclude_order=order):
            return f"Alamat {order.subdomain} sudah dipakai toko lain. Jangan centang 'setujui ganti alamat'."
        return ""
    if not order.subdomain:
        return "Pesanan ini belum punya alamat toko."
    if Store.objects.filter(subdomain=order.subdomain).exists():
        return f"Alamat {order.subdomain} sudah dipakai toko lain. Hubungi pelanggan untuk memilih alamat lain."
    return ""


def _package_outlets(package, fallback: int) -> int:
    return package.outlet_count if package is not None and package.outlet_count else fallback


@transaction.atomic
def activate_order(order, *, approve_subdomain: bool = False) -> Store:
    """Buat toko baru, atau perpanjang toko lama (boleh pindah paket & ganti alamat)."""
    problem = activation_problem(order, approve_subdomain=approve_subdomain)
    if problem:
        raise ActivationError(problem)
    today = timezone.localdate()
    if order.is_addon:
        store = Store.objects.select_for_update().get(pk=order.store_id)
        store.extra_outlets += order.quantity
        store.save(update_fields=["extra_outlets", "updated_at"])
        order.activated_at = timezone.now()
        log.info("Pesanan %s: toko #%s mendapat %s toko tambahan.", order.code, store.pk, order.quantity)
        return store
    if order.is_renewal:
        store = Store.objects.select_for_update().get(pk=order.store_id)
        start = store.active_until if store.active_until >= today else today
        store.active_until = add_months(start)
        if order.package_id:
            store.package = order.package
            store.package_name = order.package_name
            store.base_outlets = _package_outlets(order.package, store.base_outlets)
        if approve_subdomain and order.subdomain and order.subdomain != store.subdomain:
            log.info("Toko #%s ganti alamat %s -> %s.", store.pk, store.subdomain, order.subdomain)
            store.subdomain = order.subdomain
        store.save()
        enforce_outlet_limit(store)
        # Pesanan aktif sebelumnya untuk toko ini sudah tergantikan.
        type(order).objects.filter(store=store, status=order.STATUS_ACTIVE).exclude(pk=order.pk).update(
            status=order.STATUS_DONE
        )
    else:
        member = order.member
        store = Store.objects.create(
            owner=member,
            subdomain=order.subdomain,
            name=(member.business_name or member.display_name)[:60],
            package=order.package,
            package_name=order.package_name,
            base_outlets=_package_outlets(order.package, 1),
            active_until=add_months(today),
        )
        Outlet.objects.create(store=store, number=1, name="Toko utama")
        order.store = store
    order.activated_at = timezone.now()
    log.info("Pesanan %s diaktifkan: toko #%s aktif sampai %s.", order.code, store.pk, store.active_until)
    return store


def outlet_addon():
    """Harga "Tambah toko/cabang" dari daftar Biaya Tambahan (panel)."""
    from apps.content.models import AddOn

    return AddOn.objects.filter(group=AddOn.GROUP_OUTLET, is_active=True).order_by("order", "pk").first()


@dataclass
class Quote:
    amount: int
    text: str
    package_price: int = 0
    extra_count: int = 0
    extra_price: int = 0


def renewal_quote(store: Store, package) -> Quote:
    """Biaya perpanjangan 1 bulan: harga paket + toko tambahan yang sudah dibeli."""
    from apps.core.formatting import rupiah

    addon = outlet_addon()
    extra = store.extra_outlets
    extra_price = addon.price * extra if addon and extra else 0
    amount = package.price + extra_price
    if not extra_price:
        return Quote(amount, package.price_text, package.price)
    text = f"{rupiah(amount)}/bulan (Paket {package.name} {rupiah(package.price)} + {extra} toko tambahan {rupiah(extra_price)})"
    return Quote(amount, text, package.price, extra, extra_price)


def enforce_outlet_limit(store: Store) -> list[Outlet]:
    """Bila paket turun (mis. Tumbuh -> Tunas), outlet terbaru di atas batas dinonaktifkan (data tetap ada)."""
    active = list(store.outlets.filter(is_active=True).order_by("number"))
    over = active[store.outlet_limit :]
    if over:
        Outlet.objects.filter(pk__in=[o.pk for o in over]).update(is_active=False)
        CashierSession.objects.filter(cashier__outlet__in=over).delete()
    return over


def next_outlet_number(store: Store) -> int:
    last = store.outlets.order_by("-number").values_list("number", flat=True).first()
    return (last or 0) + 1


# ---------------------------------------------------------------------------
# Transaksi kasir
# ---------------------------------------------------------------------------
class CheckoutError(Exception):
    pass


@dataclass
class CheckoutResult:
    sale: Sale
    duplicate: bool = False


def _int(value, name: str, *, low: int = 0, high: int = MAX_PRICE) -> int:
    if isinstance(value, bool):
        raise CheckoutError(f"Isian {name} tidak valid.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise CheckoutError(f"Isian {name} tidak valid.") from None
    if not low <= number <= high:
        raise CheckoutError(f"Isian {name} di luar batas.")
    return number


def checkout(cashier: Cashier, payload: dict) -> CheckoutResult:
    """Simpan satu transaksi. Harga & total SELALU dihitung ulang dari database."""
    if not isinstance(payload, dict):
        raise CheckoutError("Data transaksi tidak valid.")
    store = cashier.store
    key = str(payload.get("key") or "")
    if not CLIENT_KEY_RE.fullmatch(key):
        raise CheckoutError("Kode transaksi tidak valid. Muat ulang halaman kasir.")
    existing = Sale.objects.filter(store=store, client_key=key).first()
    if existing:
        return CheckoutResult(existing, duplicate=True)

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise CheckoutError("Keranjang masih kosong.")
    if len(raw_items) > MAX_ITEMS_PER_SALE:
        raise CheckoutError("Terlalu banyak jenis barang dalam satu transaksi.")
    quantities: dict[int, int] = defaultdict(int)
    for row in raw_items:
        if not isinstance(row, dict):
            raise CheckoutError("Data barang tidak valid.")
        quantities[_int(row.get("id"), "barang", low=1, high=2**62)] += _int(row.get("qty"), "jumlah", low=1, high=MAX_QTY)
    if any(qty > MAX_QTY for qty in quantities.values()):
        raise CheckoutError(f"Jumlah satu barang maksimal {MAX_QTY}.")

    products = {p.pk: p for p in Product.objects.filter(store=store, pk__in=quantities.keys(), is_active=True)}
    if len(products) != len(quantities):
        raise CheckoutError("Ada barang yang sudah tidak dijual atau harganya berubah. Muat ulang daftar barang.")

    lines = [(products[pk], qty, products[pk].price * qty) for pk, qty in quantities.items()]
    subtotal = sum(line_total for _, _, line_total in lines)
    if subtotal > MAX_PRICE:
        raise CheckoutError("Total transaksi terlalu besar.")

    discount_type = str(payload.get("discount_type") or "")
    discount_value = 0
    discount = 0
    if discount_type == Sale.DISCOUNT_AMOUNT:
        discount_value = _int(payload.get("discount_value"), "diskon")
        if discount_value > subtotal:
            raise CheckoutError("Diskon lebih besar dari total belanja.")
        discount = discount_value
    elif discount_type == Sale.DISCOUNT_PERCENT:
        discount_value = _int(payload.get("discount_value"), "diskon", high=100)
        discount = subtotal * discount_value // 100
    elif discount_type:
        raise CheckoutError("Jenis diskon tidak dikenal.")
    if discount == 0:
        discount_type, discount_value = "", 0
    total = subtotal - discount

    method = str(payload.get("method") or "")
    if method not in Sale.METHOD_KEYS:
        raise CheckoutError("Pilih cara bayar.")
    if method == Sale.METHOD_CASH:
        paid = _int(payload.get("paid"), "uang diterima")
        if paid < total:
            raise CheckoutError("Uang yang diterima kurang dari total belanja.")
    else:
        paid = total

    try:
        with transaction.atomic():
            outlet = Outlet.objects.select_for_update().get(pk=cashier.outlet_id, store=store)
            outlet.sale_seq += 1
            outlet.save(update_fields=["sale_seq"])
            sale = Sale.objects.create(
                store=store,
                outlet=outlet,
                cashier=cashier,
                cashier_name=cashier.username,
                number=f"{outlet.number}-{outlet.sale_seq:05d}",
                client_key=key,
                subtotal=subtotal,
                discount_type=discount_type,
                discount_value=discount_value,
                discount=discount,
                total=total,
                paid=paid,
                change=paid - total,
                method=method,
            )
            SaleItem.objects.bulk_create(
                [
                    SaleItem(sale=sale, product=product, name=product.name, price=product.price, qty=qty, line_total=line_total)
                    for product, qty, line_total in lines
                ]
            )
    except IntegrityError:
        # Tombol Bayar terkirim dua kali bersamaan: pakai transaksi yang sudah tersimpan.
        existing = Sale.objects.filter(store=store, client_key=key).first()
        if existing is None:
            raise
        return CheckoutResult(existing, duplicate=True)
    return CheckoutResult(sale)


def void_sale(sale: Sale, reason: str) -> None:
    reason = " ".join((reason or "").split())[:200]
    if len(reason) < 3:
        raise CheckoutError("Tulis alasan pembatalan.")
    if sale.is_void:
        return
    sale.status = Sale.STATUS_VOID
    sale.void_reason = reason
    sale.voided_at = timezone.now()
    sale.save(update_fields=["status", "void_reason", "voided_at"])


# ---------------------------------------------------------------------------
# Laporan
# ---------------------------------------------------------------------------
PERIODS = [
    ("hari-ini", "Hari ini"),
    ("kemarin", "Kemarin"),
    ("7-hari", "7 hari terakhir"),
    ("bulan-ini", "Bulan ini"),
    ("bulan-lalu", "Bulan lalu"),
]
MAX_RANGE_DAYS = 366


def period_range(key: str, today: date | None = None) -> tuple[date, date]:
    today = today or timezone.localdate()
    if key == "kemarin":
        day = today - timedelta(days=1)
        return day, day
    if key == "7-hari":
        return today - timedelta(days=6), today
    if key == "bulan-ini":
        return today.replace(day=1), today
    if key == "bulan-lalu":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    return today, today


def parse_range(params, today: date | None = None) -> tuple[str, date, date]:
    """Ambil periode dari ?periode=... atau ?dari=YYYY-MM-DD&sampai=YYYY-MM-DD."""
    today = today or timezone.localdate()
    try:
        start = date.fromisoformat(params.get("dari", ""))
        end = date.fromisoformat(params.get("sampai", ""))
    except ValueError:
        key = params.get("periode", "hari-ini")
        key = key if key in dict(PERIODS) else "hari-ini"
        return (key, *period_range(key, today))
    if end < start:
        start, end = end, start
    end = min(end, today)
    start = max(start, end - timedelta(days=MAX_RANGE_DAYS - 1))
    return "pilih", start, end


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(start, time.min), tz),
        timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz),
    )


def sales_in_range(store: Store, start: date, end: date, outlet: Outlet | None = None):
    lo, hi = _bounds(start, end)
    qs = Sale.objects.filter(store=store, created_at__gte=lo, created_at__lt=hi)
    if outlet is not None:
        qs = qs.filter(outlet=outlet)
    return qs


@dataclass
class Report:
    start: date
    end: date
    count: int = 0
    revenue: int = 0
    discount: int = 0
    void_count: int = 0
    average: int = 0
    by_method: list = field(default_factory=list)
    by_day: list = field(default_factory=list)
    by_outlet: list = field(default_factory=list)
    top_products: list = field(default_factory=list)


def build_report(store: Store, start: date, end: date, outlet: Outlet | None = None) -> Report:
    base = sales_in_range(store, start, end, outlet)
    done = base.filter(status=Sale.STATUS_DONE)
    totals = done.aggregate(count=Count("id"), revenue=Sum("total"), discount=Sum("discount"))
    report = Report(
        start=start,
        end=end,
        count=totals["count"] or 0,
        revenue=totals["revenue"] or 0,
        discount=totals["discount"] or 0,
        void_count=base.filter(status=Sale.STATUS_VOID).count(),
    )
    report.average = report.revenue // report.count if report.count else 0
    labels = dict(Sale.METHODS)
    report.by_method = [
        {"label": labels.get(row["method"], row["method"]), "count": row["count"], "total": row["total"] or 0}
        for row in done.values("method").annotate(count=Count("id"), total=Sum("total")).order_by("-total")
    ]
    names = dict(store.outlets.values_list("pk", "name"))
    report.by_outlet = [
        {"label": names.get(row["outlet"], "–"), "count": row["count"], "total": row["total"] or 0}
        for row in done.values("outlet").annotate(count=Count("id"), total=Sum("total")).order_by("-total")
    ]
    # Per hari dihitung di Python: tidak bergantung pada tabel zona waktu MariaDB.
    days: dict[date, list[int]] = {}
    for created_at, total in done.values_list("created_at", "total"):
        day = timezone.localtime(created_at).date()
        bucket = days.setdefault(day, [0, 0])
        bucket[0] += 1
        bucket[1] += total
    if (end - start).days <= 62:
        report.by_day = [
            {"day": start + timedelta(days=i), "count": days.get(start + timedelta(days=i), [0, 0])[0],
             "total": days.get(start + timedelta(days=i), [0, 0])[1]}
            for i in range((end - start).days + 1)
        ]
    else:
        report.by_day = [{"day": d, "count": v[0], "total": v[1]} for d, v in sorted(days.items())]
    report.top_products = list(
        SaleItem.objects.filter(sale__in=done)
        .values("name")
        .annotate(qty=Sum("qty"), total=Sum("line_total"))
        .order_by("-qty", "name")[:10]
    )
    return report


# ---------------------------------------------------------------------------
# Pembersihan data toko yang tidak diperpanjang
# ---------------------------------------------------------------------------
def stores_due_for_deletion(today: date | None = None):
    """Masa aktif habis lebih dari 30 hari, kecuali sedang ada perpanjangan yang buktinya dicek admin."""
    from apps.members.models import Order

    today = today or timezone.localdate()
    pending = Order.objects.filter(
        store=OuterRef("pk"), status__in=(Order.STATUS_CHECKING, Order.STATUS_PROCESS)
    )
    return (
        Store.objects.filter(active_until__lt=today - timedelta(days=DELETE_AFTER_DAYS))
        .annotate(has_pending=Exists(pending))
        .filter(has_pending=False)
    )


def delete_expired_stores(today: date | None = None) -> list[str]:
    deleted = []
    for store in stores_due_for_deletion(today):
        label = f"#{store.pk} {store.subdomain}"
        with transaction.atomic():
            store.delete()
        log.info("Data toko %s dihapus permanen (masa aktif habis lebih dari %s hari).", label, DELETE_AFTER_DAYS)
        deleted.append(label)
    CashierSession.objects.filter(expires_at__lt=timezone.now()).delete()
    return deleted


# ---------------------------------------------------------------------------
# Dashboard pelanggan: ringkasan SEMUA toko & outlet milik satu pelanggan
# ---------------------------------------------------------------------------
@dataclass
class Overview:
    stores: list = field(default_factory=list)
    today: dict = field(default_factory=dict)
    yesterday: dict = field(default_factory=dict)
    week: dict = field(default_factory=dict)
    month: dict = field(default_factory=dict)
    trend: list = field(default_factory=list)
    trend_peak: int = 0
    outlets: list = field(default_factory=list)
    top_products: list = field(default_factory=list)
    recent: list = field(default_factory=list)
    alerts: list = field(default_factory=list)


def _totals(qs) -> dict:
    agg = qs.aggregate(count=Count("id"), revenue=Sum("total"))
    count, revenue = agg["count"] or 0, agg["revenue"] or 0
    return {"count": count, "revenue": revenue, "average": revenue // count if count else 0}


def overview(stores, today: date | None = None, trend_days: int = 14) -> Overview:
    today = today or timezone.localdate()
    stores = [s for s in stores if s.state(today) != Store.STATE_DELETED]
    data = Overview(stores=stores)
    if not stores:
        return data
    done = Sale.objects.filter(store__in=stores, status=Sale.STATUS_DONE)

    def between(start: date, end: date):
        lo, hi = _bounds(start, end)
        return done.filter(created_at__gte=lo, created_at__lt=hi)

    month_start = today.replace(day=1)
    data.today = _totals(between(today, today))
    data.yesterday = _totals(between(today - timedelta(days=1), today - timedelta(days=1)))
    data.week = _totals(between(today - timedelta(days=6), today))
    data.month = _totals(between(month_start, today))

    # Tren harian (dihitung di Python, tanpa tabel zona waktu MariaDB).
    start = today - timedelta(days=trend_days - 1)
    days: dict[date, int] = {}
    for created_at, total in between(start, today).values_list("created_at", "total"):
        day = timezone.localtime(created_at).date()
        days[day] = days.get(day, 0) + total
    data.trend = [{"day": start + timedelta(days=i), "total": days.get(start + timedelta(days=i), 0)} for i in range(trend_days)]
    data.trend_peak = max((d["total"] for d in data.trend), default=0)

    # Per outlet: hari ini & bulan ini.
    def per_outlet(qs) -> dict[int, tuple[int, int]]:
        return {r["outlet"]: (r["n"], r["t"] or 0) for r in qs.values("outlet").annotate(n=Count("id"), t=Sum("total"))}

    today_map = per_outlet(between(today, today))
    month_map = per_outlet(between(month_start, today))
    for outlet in Outlet.objects.filter(store__in=stores).select_related("store").order_by("store__name", "number"):
        data.outlets.append({
            "store": outlet.store,
            "outlet": outlet,
            "today_count": today_map.get(outlet.pk, (0, 0))[0],
            "today_total": today_map.get(outlet.pk, (0, 0))[1],
            "month_count": month_map.get(outlet.pk, (0, 0))[0],
            "month_total": month_map.get(outlet.pk, (0, 0))[1],
        })

    data.top_products = list(
        SaleItem.objects.filter(sale__in=between(month_start, today))
        .values("name", "sale__store__name")
        .annotate(qty=Sum("qty"), total=Sum("line_total"))
        .order_by("-qty", "name")[:5]
    )
    data.recent = list(done.select_related("store", "outlet").order_by("-created_at")[:6])

    for store in stores:
        state = store.state(today)
        if state == Store.STATE_GRACE:
            data.alerts.append((store, "wait", f"Masa aktif habis. Kasir masih jalan sampai {store.grace_until:%d/%m/%Y}."))
        elif state == Store.STATE_LOCKED:
            data.alerts.append((store, "off", f"Kasir terkunci. Data dihapus setelah {store.delete_on:%d/%m/%Y} bila tidak diperpanjang."))
        elif state == Store.STATE_SUSPENDED:
            data.alerts.append((store, "off", "Toko ditangguhkan admin. Lihat catatan di halaman toko."))
        elif store.days_left <= 7:
            data.alerts.append((store, "wait", f"Masa aktif tinggal {store.days_left} hari."))
        if not store.cashiers.exists():
            data.alerts.append((store, "wait", "Belum ada akun kasir. Buat di menu Outlet & Kasir."))
    return data
