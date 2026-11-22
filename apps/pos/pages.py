"""Halaman toko (``<toko>.hansproject.app/``) dan panduan "Langkah memulai toko".

Draf & terbit
-------------
Field ``StorePage`` (dan ``StoreHighlight``) adalah DRAF yang diedit pemilik. Saat
pemilik menekan *Terbitkan*, draf disalin ke ``StorePage.live`` (JSON). Pengunjung
selalu melihat ``live``; perubahan berikutnya baru tampil setelah diterbitkan lagi.
Pratinjau memakai draf.

Gambar dipakai bersama oleh draf dan versi terbit, jadi file lama baru dihapus bila
sudah tidak dipakai oleh keduanya (``cleanup``).
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field

from django.core.files.storage import default_storage
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from . import palette
from .models import CashierSession, Store, StorePage

MAX_PRICE_ROWS = 500  # batas wajar daftar harga di halaman publik


def get_page(store: Store) -> StorePage:
    page, _ = StorePage.objects.get_or_create(store=store, defaults={"phone": store.phone})
    return page


def page_or_none(store: Store) -> StorePage | None:
    try:
        return store.page
    except StorePage.DoesNotExist:
        return None


def theme_url(color: str) -> str:
    """CSS variabel palet (sama di domain utama & subdomain toko, boleh di-cache lama)."""
    hex_value = palette.normalize(color) or palette.DEFAULT
    return f"/_tema/v{palette.VERSION}/{hex_value[1:]}.css"


# ---------------------------------------------------------------------------
# Draf, terbit, file
# ---------------------------------------------------------------------------
CONTENT_FIELDS = ("template", "color", "tagline", "about", "hours", "phone", "instagram", "maps_url", "show_prices")


def draft_data(page: StorePage) -> dict:
    data = {name: getattr(page, name) for name in CONTENT_FIELDS}
    data["logo"] = page.logo.name or ""
    data["cover"] = page.cover.name or ""
    data["highlights"] = [
        {"product": h.product_id, "image": h.image.name or "", "title": h.title, "caption": h.caption}
        for h in page.highlights.all()
    ]
    return data


def has_unpublished_changes(page: StorePage) -> bool:
    return page.live is not None and page.live != draft_data(page)


def _files(data: dict | None) -> set[str]:
    if not data:
        return set()
    names = {data.get("logo", ""), data.get("cover", "")}
    names.update(h.get("image", "") for h in data.get("highlights", []))
    return {n for n in names if n}


def cleanup(page: StorePage, candidates: Iterable[str]) -> None:
    """Hapus file yang tidak dipakai lagi oleh draf maupun versi terbit."""
    keep = _files(draft_data(page)) | _files(page.live)
    for name in candidates:
        if name and name not in keep:
            default_storage.delete(name)


def publish(page: StorePage) -> None:
    old = _files(page.live)
    page.live = draft_data(page)
    page.is_published = True
    page.published_at = timezone.now()
    page.save(update_fields=["live", "is_published", "published_at", "updated_at"])
    cleanup(page, old)


def unpublish(page: StorePage) -> None:
    page.is_published = False
    page.save(update_fields=["is_published", "updated_at"])


# ---------------------------------------------------------------------------
# Data untuk template halaman
# ---------------------------------------------------------------------------
@dataclass
class Highlight:
    title: str
    caption: str
    price: int | None
    image_url: str


@dataclass
class Section:
    name: str
    products: list = field(default_factory=list)


@dataclass
class PageView:
    store: Store
    template: str
    theme_url: str
    tagline: str
    about: str
    hours: str
    phone: str
    instagram: str
    maps_url: str
    logo_url: str
    cover_url: str
    highlights: list[Highlight]
    sections: list[Section]
    theme_color: str = ""

    @property
    def phone_href(self) -> str:
        digits = "".join(c for c in self.phone if c.isdigit() or c == "+")
        return f"tel:{digits}" if digits else ""

    @property
    def og_image(self) -> str:
        return self.store.url.rstrip("/") + self.cover_url if self.cover_url else ""

    @property
    def jsonld(self) -> str:
        """Data terstruktur (schema.org) untuk mesin pencari. Blok data, bukan script: aman untuk CSP."""
        data = {"@context": "https://schema.org", "@type": "Store", "name": self.store.name, "url": self.store.url}
        if self.description:
            data["description"] = self.description
        if self.store.address:
            data["address"] = self.store.address
        if self.phone:
            data["telephone"] = self.phone
        if self.og_image:
            data["image"] = self.og_image
        text = json.dumps(data, ensure_ascii=False)
        for char in "<>&":  # supaya teks pemilik tidak bisa menutup tag <script>
            text = text.replace(char, "\\u%04x" % ord(char))
        return mark_safe(text)  # nosec B703 B308 - JSON dengan <, >, & sudah di-escape (< dst.)

    @property
    def description(self) -> str:
        text = self.tagline or self.about or f"{self.store.name}. {self.store.address}".strip(". ")
        return " ".join(text.split())[:160]


def _url(name: str) -> str:
    return default_storage.url(name) if name else ""


def build_view(store: Store, data: dict) -> PageView:
    """Menyusun isi halaman dari draf atau versi terbit. Nama & harga barang selalu yang terbaru."""
    rows = data.get("highlights", [])
    ids = [r["product"] for r in rows if r.get("product")]
    products = {p.pk: p for p in store.products.filter(pk__in=ids, is_active=True)} if ids else {}
    highlights = []
    for row in rows:
        product = products.get(row.get("product"))
        title = row.get("title") or (product.name if product else "")
        if not title or (row.get("product") and not product and not row.get("image")):
            continue  # barangnya sudah dihapus/tidak dijual dan tidak ada gambar pengganti
        highlights.append(Highlight(title, row.get("caption", ""), product.price if product else None, _url(row.get("image", ""))))

    sections: list[Section] = []
    if data.get("show_prices"):
        by_cat: dict = {}
        for product in store.products.filter(is_active=True).select_related("category").order_by(
            "category__order", "category__name", "name"
        )[:MAX_PRICE_ROWS]:
            key = product.category_id or 0
            if key not in by_cat:
                by_cat[key] = Section(product.category.name if product.category_id else "Lainnya")
            by_cat[key].products.append(product)
        sections = [s for k, s in by_cat.items() if k] + ([by_cat[0]] if 0 in by_cat else [])
        if len(sections) == 1 and not sections[0].products[0].category_id:
            sections[0].name = "Daftar harga"

    color = palette.normalize(data.get("color", "")) or palette.DEFAULT
    template = data.get("template") if data.get("template") in dict(StorePage.TEMPLATES) else "sederhana"
    return PageView(
        store=store,
        template=template,
        theme_url=theme_url(color),
        theme_color=palette.build(color)["brand"],
        tagline=data.get("tagline", ""),
        about=data.get("about", ""),
        hours=data.get("hours", ""),
        phone=data.get("phone", ""),
        instagram=data.get("instagram", ""),
        maps_url=data.get("maps_url", ""),
        logo_url=_url(data.get("logo", "")),
        cover_url=_url(data.get("cover", "")),
        highlights=highlights,
        sections=sections,
    )


# ---------------------------------------------------------------------------
# Panduan "Langkah memulai toko" (tampil di semua menu toko sampai semuanya selesai)
# ---------------------------------------------------------------------------
@dataclass
class Step:
    number: int
    title: str
    text: str
    cta: str
    url: str
    done: bool
    external: bool = False
    current: bool = False


def setup_steps(store: Store) -> list[Step] | None:
    """Langkah 1–4. ``None`` bila semuanya sudah selesai (panduan disembunyikan)."""
    cashier = store.cashier_or_none
    page = page_or_none(store)
    has_products = store.products.exists()
    opened = bool(cashier) and (
        store.sales.exists() or CashierSession.objects.filter(cashier=cashier).exists()
    )
    sub = store.subdomain
    steps = [
        Step(1, "Masukkan barang dan harga",
             "Bisa dikelompokkan per kategori, misalnya Makanan dan Minuman.",
             "Tambah barang", reverse("toko:barang-baru", args=[sub]), has_products),
        Step(2, "Buat akun kasir",
             "Anda menentukan nama pengguna dan PIN. Satu akun bisa dipakai di banyak HP/laptop sekaligus.",
             "Buat akun kasir", reverse("toko:kasir", args=[sub]), bool(cashier)),
        Step(3, "Buka kasir di HP atau laptop",
             f"Buka {store.host}/kasir, lalu masuk dengan nama pengguna dan PIN tadi.",
             "Buka kasir", store.kasir_url, opened, external=True),
        Step(4, "Terbitkan halaman toko",
             f"Pilih template dan warna, pilih barang unggulan, lihat pratinjau, lalu terbitkan di {store.host}.",
             "Atur halaman toko", reverse("toko:halaman", args=[sub]), bool(page and page.is_published)),
    ]
    if all(s.done for s in steps):
        return None
    next(s for s in steps if not s.done).current = True
    return steps
