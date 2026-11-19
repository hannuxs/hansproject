"""Mengambil seluruh konten situs dalam satu "snapshot" yang di-cache.

Data jarang berubah, jadi database hanya dibaca sekali lalu disimpan di
memori. Setiap kali pemilik mengubah data di panel, cache otomatis dihapus
(lihat signals.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.core.cache import cache
from django.db.models import Prefetch

from apps.core import formatting

from . import templating
from .models import (
    AddOn,
    BankAccount,
    ComparisonRow,
    Faq,
    IncludedFeature,
    LegalPage,
    Package,
    PackageFeature,
    SiteSettings,
    Testimonial,
)

SNAPSHOT_KEY = "content:snapshot:v1"
PAGE_KEY_PREFIX = "content:page:"

# Tujuan klik yang dicatat (hanya angka per hari, tanpa data pribadi).
GENERAL_TARGETS = {"instagram"}


@dataclass
class OutletTip:
    base: Package
    upgrade: Package
    extra_outlets: int
    total_outlets: int
    base_total: int


@dataclass
class Snapshot:
    settings: SiteSettings
    pos_packages: list[Package]
    service_packages: list[Package]
    included: list[IncludedFeature]
    highlights: list[PackageFeature]
    outlet_addons: list[AddOn]
    storage_addons: list[AddOn]
    comparison_columns: list[Package]
    comparison_rows: list[tuple[str, list[str]]]
    faqs: list[Faq]
    testimonials: list[Testimonial]
    bank_accounts: list[BankAccount]
    start_price: int | None
    outlet_tip: OutletTip | None
    calculator: dict = field(default_factory=dict)

    @property
    def hero_title(self) -> str:
        return templating.fill(self.settings.hero_title, harga_mulai=formatting.rupiah_short(self.start_price))

    @property
    def hero_parts(self) -> tuple[str, str, str]:
        """Judul utama dipecah supaya harga bisa diberi sorotan: (sebelum, harga, sesudah)."""
        price = formatting.rupiah_short(self.start_price)
        title = self.settings.hero_title
        if "{harga_mulai}" in title and price:
            before, _, after = title.partition("{harga_mulai}")
            return before, price, after
        return self.hero_title, "", ""

    @property
    def storage_start_price(self) -> int | None:
        return min((a.price for a in self.storage_addons), default=None)

    @property
    def valid_targets(self) -> set[str]:
        return {p.code for p in self.pos_packages + self.service_packages} | GENERAL_TARGETS


def _outlet_tip(pos: list[Package], outlet_price: int | None) -> OutletTip | None:
    """Contoh: Tunas + 5 toko tambahan = Rp100.000, lebih mahal dari Tumbuh."""
    priced = [p for p in pos if p.outlet_count]
    if len(priced) < 2 or not outlet_price:
        return None
    base, upgrade = priced[0], priced[1]
    if upgrade.price <= base.price:
        return None
    extra = 1
    while base.price + extra * outlet_price < upgrade.price and extra < 1000:
        extra += 1
    total_outlets = base.outlet_count + extra
    if total_outlets > upgrade.outlet_count:
        return None
    return OutletTip(base, upgrade, extra, total_outlets, base.price + extra * outlet_price)


def build_snapshot() -> Snapshot:
    site = SiteSettings.load()
    feature_qs = PackageFeature.objects.order_by("order", "id")
    packages = list(
        Package.objects.filter(is_active=True)
        .select_related("includes_from")
        .prefetch_related(Prefetch("features", queryset=feature_qs), "notes")
        .order_by("order", "id")
    )
    pos = [p for p in packages if p.is_pos]
    service = [p for p in packages if not p.is_pos]

    addons = list(AddOn.objects.filter(is_active=True))
    outlet_addons = [a for a in addons if a.group == AddOn.GROUP_OUTLET]
    storage_addons = [a for a in addons if a.group == AddOn.GROUP_STORAGE]
    outlet_price = outlet_addons[0].price if outlet_addons else None

    rows = []
    for row in ComparisonRow.objects.filter(is_active=True):
        values = row.values if isinstance(row.values, dict) else {}
        rows.append((row.label, [values.get(p.code, "–") or "–" for p in packages]))

    highlights = []
    if pos:
        highlights = [f for f in pos[0].features.all() if f.show_in_highlights and f.icon]

    testimonials = []
    if site.show_testimonials:
        testimonials = list(Testimonial.objects.filter(is_active=True))

    calculator = {
        "outletPrice": outlet_price or 0,
        "packages": [
            {"code": p.code, "name": p.name, "price": p.price, "outlets": p.outlet_count}
            for p in pos
            if p.outlet_count
        ],
    }

    return Snapshot(
        settings=site,
        pos_packages=pos,
        service_packages=service,
        included=list(IncludedFeature.objects.all()),
        highlights=highlights,
        outlet_addons=outlet_addons,
        storage_addons=storage_addons,
        comparison_columns=packages,
        comparison_rows=rows,
        faqs=list(Faq.objects.filter(is_active=True)),
        testimonials=testimonials,
        bank_accounts=list(BankAccount.objects.filter(is_active=True)),
        start_price=min((p.price for p in pos), default=None),
        outlet_tip=_outlet_tip(pos, outlet_price),
        calculator=calculator,
    )


def get_snapshot() -> Snapshot:
    snapshot = cache.get(SNAPSHOT_KEY)
    if snapshot is None:
        snapshot = build_snapshot()
        cache.set(SNAPSHOT_KEY, snapshot)
    return snapshot


def get_legal_page(slug: str) -> LegalPage | None:
    return LegalPage.objects.filter(slug=slug).first()


def invalidate() -> None:
    cache.delete(SNAPSHOT_KEY)
    cache.delete_many([f"{PAGE_KEY_PREFIX}{name}" for name in ("home", *dict(LegalPage.SLUGS))])
