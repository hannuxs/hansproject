"""Aplikasi kasir (POS) untuk pelanggan Paket Tunas / Tumbuh.

Susunannya:
- ``Subscription`` (langganan): satu pesanan paket. Menyimpan paket, kuota toko
  (Tunas 2, Tumbuh 10, + toko tambahan yang dibeli) dan masa aktif.
- ``Store`` (toko): SATU toko = SATU subdomain = SATU akun kasir, dengan barang,
  kategori, transaksi, dan laporan sendiri. Toko-toko dalam satu langganan
  tidak berbagi data. Akun kasir boleh masuk di banyak perangkat sekaligus.

Semua toko berbagi tabel yang sama (awalan ``hp_pos_``). Setiap baris punya
kolom ``store`` dan SEMUA query wajib disaring per toko: pemilik lewat
``Store.objects.owned_by(member)``, kasir lewat sesi kasir yang terikat ke satu
toko. Jangan pernah mengambil Product/Sale dengan ``pk`` saja.

Uang disimpan sebagai bilangan bulat rupiah (tanpa sen).
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from . import subdomains

GRACE_DAYS = 7  # setelah masa aktif habis, kasir masih bisa dipakai (dengan peringatan)
DELETE_AFTER_DAYS = 30  # setelah masa aktif habis, data dihapus permanen
MAX_PRICE = 999_999_999
MAX_QTY = 9999


def add_months(start: date, months: int = 1) -> date:
    """31 Jan + 1 bulan = 28/29 Feb (tanggal dipotong ke akhir bulan)."""
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


STATE_ACTIVE = "aktif"
STATE_GRACE = "tenggang"
STATE_LOCKED = "terkunci"
STATE_DELETED = "dihapus"
STATE_SUSPENDED = "ditangguhkan"
STATE_INACTIVE = "nonaktif"
STATE_LABELS = {
    STATE_ACTIVE: "Aktif",
    STATE_GRACE: "Masa tenggang",
    STATE_LOCKED: "Terkunci (belum diperpanjang)",
    STATE_DELETED: "Data sudah dihapus",
    STATE_SUSPENDED: "Ditangguhkan",
    STATE_INACTIVE: "Nonaktif",
}
STATE_TONES = {STATE_ACTIVE: "ok", STATE_GRACE: "wait"}


class SubscriptionQuerySet(models.QuerySet):
    def owned_by(self, member):
        return self.filter(owner=member)

    def not_deleted(self, today: date | None = None):
        today = today or timezone.localdate()
        return self.filter(active_until__gte=today - timedelta(days=DELETE_AFTER_DAYS))


class Subscription(models.Model):
    """Langganan aplikasi kasir: paket, kuota toko, dan masa aktif. Berlaku untuk semua tokonya."""

    STATUS_ACTIVE = "aktif"
    STATUS_SUSPENDED = "ditangguhkan"
    STATUSES = [(STATUS_ACTIVE, "Normal"), (STATUS_SUSPENDED, "Ditangguhkan admin")]

    owner = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="subscriptions", verbose_name="pemilik"
    )
    package = models.ForeignKey(
        "content.Package", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="paket"
    )
    package_name = models.CharField("nama paket", max_length=60)
    base_stores = models.PositiveSmallIntegerField(
        "toko termasuk paket", default=2, validators=[MaxValueValidator(500)]
    )
    extra_stores = models.PositiveSmallIntegerField(
        "toko tambahan (dibeli)", default=0, validators=[MaxValueValidator(500)],
        help_text="Bertambah otomatis saat pesanan tambahan toko diaktifkan.",
    )
    status = models.CharField("status", max_length=14, choices=STATUSES, default=STATUS_ACTIVE)
    active_until = models.DateField("aktif sampai")
    admin_note = models.TextField(
        "catatan untuk pemilik toko", blank=True, max_length=1000,
        help_text="Tampil di halaman semua toko dalam langganan ini, misalnya alasan ditangguhkan.",
    )
    created_at = models.DateTimeField("dibuat", auto_now_add=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    objects = SubscriptionQuerySet.as_manager()

    class Meta:
        db_table = "hp_pos_subscription"
        ordering = ["created_at", "pk"]
        verbose_name = "langganan kasir"
        verbose_name_plural = "langganan kasir"

    def __str__(self) -> str:
        return f"Paket {self.package_name} #{self.pk}"

    # --- Masa aktif ---
    def state(self, today: date | None = None) -> str:
        today = today or timezone.localdate()
        if today > self.delete_on:
            return STATE_DELETED
        if self.status == self.STATUS_SUSPENDED:
            return STATE_SUSPENDED
        if today <= self.active_until:
            return STATE_ACTIVE
        if today <= self.active_until + timedelta(days=GRACE_DAYS):
            return STATE_GRACE
        return STATE_LOCKED

    @property
    def state_now(self) -> str:
        return self.state()

    @property
    def state_label(self) -> str:
        return STATE_LABELS[self.state()]

    @property
    def state_tone(self) -> str:
        return STATE_TONES.get(self.state(), "off")

    @property
    def grace_until(self) -> date:
        return self.active_until + timedelta(days=GRACE_DAYS)

    @property
    def delete_on(self) -> date:
        """Hari terakhir data masih ada. Setelah tanggal ini data dihapus permanen."""
        return self.active_until + timedelta(days=DELETE_AFTER_DAYS)

    @property
    def can_sell(self) -> bool:
        return self.state() in (STATE_ACTIVE, STATE_GRACE)

    @property
    def can_edit(self) -> bool:
        """Pemilik boleh mengubah barang, akun kasir, pengaturan, dan menambah toko."""
        return self.can_sell

    @property
    def days_left(self) -> int:
        return (self.active_until - timezone.localdate()).days

    # --- Kuota toko ---
    @property
    def store_limit(self) -> int:
        return self.base_stores + self.extra_stores

    @property
    def stores_used(self) -> int:
        """Toko aktif yang sudah dibuat (toko nonaktif tidak memakai kuota)."""
        return self.stores.filter(is_active=True).count()

    @property
    def stores_free(self) -> int:
        return max(0, self.store_limit - self.stores_used)

    @property
    def quota_text(self) -> str:
        """Contoh: 'Paket Tunas 2 + tambahan 1'."""
        text = f"Paket {self.package_name} {self.base_stores}"
        return f"{text} + tambahan {self.extra_stores}" if self.extra_stores else text


class StoreQuerySet(models.QuerySet):
    def owned_by(self, member):
        return self.filter(owner=member)

    def not_deleted(self, today: date | None = None):
        """Toko yang datanya belum lewat batas hapus (masa aktif langganan + 30 hari)."""
        today = today or timezone.localdate()
        return self.filter(subscription__active_until__gte=today - timedelta(days=DELETE_AFTER_DAYS))


class Store(models.Model):
    """Satu toko: satu subdomain, satu akun kasir, barang & transaksi sendiri."""

    STATE_ACTIVE, STATE_GRACE, STATE_LOCKED = STATE_ACTIVE, STATE_GRACE, STATE_LOCKED
    STATE_DELETED, STATE_SUSPENDED, STATE_INACTIVE = STATE_DELETED, STATE_SUSPENDED, STATE_INACTIVE
    STATE_LABELS = STATE_LABELS

    RECEIPT_WIDTHS = [(58, "58 mm (printer kecil)"), (80, "80 mm (printer besar)")]

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="stores", verbose_name="langganan"
    )
    owner = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="stores", verbose_name="pemilik"
    )
    subdomain = models.CharField("alamat toko", max_length=30, unique=True)
    name = models.CharField("nama toko", max_length=60)
    address = models.CharField("alamat", max_length=200, blank=True)
    phone = models.CharField("nomor telepon di struk", max_length=20, blank=True)
    receipt_footer = models.CharField(
        "tulisan di bawah struk", max_length=160, blank=True, default="Terima kasih sudah berbelanja!"
    )
    receipt_width = models.PositiveSmallIntegerField("ukuran kertas struk", choices=RECEIPT_WIDTHS, default=58)
    is_active = models.BooleanField(
        "toko aktif", default=True,
        help_text="Toko nonaktif tidak memakai kuota paket dan kasirnya tidak bisa masuk. Datanya tetap ada.",
    )
    sale_seq = models.PositiveIntegerField(default=0, editable=False)  # nomor struk terakhir
    created_at = models.DateTimeField("dibuat", auto_now_add=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        db_table = "hp_pos_store"
        ordering = ["created_at", "pk"]
        verbose_name = "toko"
        verbose_name_plural = "toko"

    def __str__(self) -> str:
        return f"{self.name} ({self.subdomain})"

    # --- Alamat ---
    @property
    def host(self) -> str:
        return subdomains.store_host(self.subdomain)

    @property
    def url(self) -> str:
        return subdomains.store_url(self.subdomain)

    @property
    def kasir_url(self) -> str:
        return subdomains.store_url(self.subdomain, "/kasir/")

    # --- Diambil dari langganan ---
    @property
    def package(self):
        return self.subscription.package

    @property
    def package_name(self) -> str:
        return self.subscription.package_name

    @property
    def active_until(self) -> date:
        return self.subscription.active_until

    @property
    def admin_note(self) -> str:
        return self.subscription.admin_note

    @property
    def grace_until(self) -> date:
        return self.subscription.grace_until

    @property
    def delete_on(self) -> date:
        return self.subscription.delete_on

    @property
    def days_left(self) -> int:
        return self.subscription.days_left

    # --- Keadaan ---
    def state(self, today: date | None = None) -> str:
        state = self.subscription.state(today)
        if state in (STATE_ACTIVE, STATE_GRACE) and not self.is_active:
            return STATE_INACTIVE
        return state

    @property
    def state_now(self) -> str:
        return self.state()

    @property
    def state_label(self) -> str:
        return STATE_LABELS[self.state()]

    @property
    def state_tone(self) -> str:
        return STATE_TONES.get(self.state(), "off")

    @property
    def can_sell(self) -> bool:
        """Kasir boleh transaksi: langganan aktif/masa tenggang dan toko aktif."""
        return self.state() in (STATE_ACTIVE, STATE_GRACE)

    @property
    def can_edit(self) -> bool:
        """Pemilik boleh mengubah barang, akun kasir, dan pengaturan (juga saat toko nonaktif)."""
        return self.subscription.can_edit

    @property
    def cashier_or_none(self):
        try:
            return self.cashier
        except Cashier.DoesNotExist:
            return None


username_validator = RegexValidator(
    r"^[a-z0-9][a-z0-9._-]{2,29}$",
    "3–30 karakter: huruf kecil, angka, titik, minus, atau garis bawah. Tanpa spasi.",
)


class Cashier(models.Model):
    """Akun kasir toko: satu toko = satu akun (nama pengguna + PIN), dibuat pemilik toko.

    Akun yang sama boleh masuk di banyak perangkat sekaligus (HP, tablet, laptop).
    """

    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name="cashier")
    username = models.CharField("nama pengguna", max_length=30, validators=[username_validator])
    pin_hash = models.CharField(max_length=128)
    is_active = models.BooleanField("aktif", default=True)
    failed_count = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField("terakhir masuk", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hp_pos_cashier"

    def __str__(self) -> str:
        return self.username

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())


class CashierSession(models.Model):
    """Sesi login kasir di subdomain toko. Cookie berisi token acak; database menyimpan hash-nya."""

    cashier = models.ForeignKey(Cashier, on_delete=models.CASCADE, related_name="sessions")
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "hp_pos_cashier_session"


class Category(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField("nama kategori", max_length=40)
    order = models.PositiveIntegerField("urutan", default=0)

    class Meta:
        db_table = "hp_pos_category"
        ordering = ["order", "name"]
        constraints = [models.UniqueConstraint(fields=["store", "name"], name="hp_pos_category_name_uniq")]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="products", verbose_name="kategori"
    )
    name = models.CharField("nama barang", max_length=80)
    code = models.CharField(
        "kode barang", max_length=40, blank=True, help_text="Opsional. Misalnya kode di kemasan (barcode)."
    )
    price = models.PositiveIntegerField(
        "harga jual (Rp)", validators=[MinValueValidator(0), MaxValueValidator(MAX_PRICE)]
    )
    is_active = models.BooleanField("dijual", default=True, help_text="Matikan bila barang sedang tidak dijual.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hp_pos_product"
        ordering = ["name"]
        indexes = [models.Index(fields=["store", "is_active"], name="hp_pos_product_store_active")]

    def __str__(self) -> str:
        return self.name


class Sale(models.Model):
    METHOD_CASH = "tunai"
    METHOD_QRIS = "qris"
    METHOD_TRANSFER = "transfer"
    METHODS = [(METHOD_CASH, "Tunai"), (METHOD_QRIS, "QRIS"), (METHOD_TRANSFER, "Transfer")]
    METHOD_KEYS = {key for key, _ in METHODS}

    STATUS_DONE = "selesai"
    STATUS_VOID = "batal"
    STATUSES = [(STATUS_DONE, "Selesai"), (STATUS_VOID, "Dibatalkan")]

    DISCOUNT_NONE = ""
    DISCOUNT_AMOUNT = "rp"
    DISCOUNT_PERCENT = "persen"

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="sales")
    cashier = models.ForeignKey(Cashier, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales")
    cashier_name = models.CharField("kasir", max_length=30)
    number = models.CharField("nomor struk", max_length=20)
    # Kode unik dari layar kasir: bila tombol Bayar terkirim dua kali (internet lambat),
    # transaksi tetap tercatat satu kali.
    client_key = models.CharField(max_length=40)
    created_at = models.DateTimeField("waktu", default=timezone.now, db_index=True)
    subtotal = models.PositiveIntegerField("subtotal")
    discount_type = models.CharField(max_length=6, blank=True)
    discount_value = models.PositiveIntegerField(default=0)
    discount = models.PositiveIntegerField("diskon", default=0)
    total = models.PositiveIntegerField("total")
    paid = models.PositiveIntegerField("dibayar")
    change = models.PositiveIntegerField("kembalian", default=0)
    method = models.CharField("cara bayar", max_length=10, choices=METHODS, default=METHOD_CASH)
    status = models.CharField("status", max_length=8, choices=STATUSES, default=STATUS_DONE)
    void_reason = models.CharField("alasan batal", max_length=200, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hp_pos_sale"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["store", "client_key"], name="hp_pos_sale_client_key_uniq"),
            models.UniqueConstraint(fields=["store", "number"], name="hp_pos_sale_number_uniq"),
        ]
        indexes = [models.Index(fields=["store", "created_at"], name="hp_pos_sale_store_time")]

    def __str__(self) -> str:
        return self.number

    @property
    def is_void(self) -> bool:
        return self.status == self.STATUS_VOID

    @property
    def discount_label(self) -> str:
        if self.discount_type == self.DISCOUNT_PERCENT:
            return f"Diskon {self.discount_value}%"
        return "Diskon"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # Salinan nama & harga saat dijual: struk lama tetap benar walau barang diubah/dihapus.
    name = models.CharField(max_length=80)
    price = models.PositiveIntegerField()
    qty = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(MAX_QTY)])
    line_total = models.PositiveIntegerField()

    class Meta:
        db_table = "hp_pos_sale_item"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.qty} x {self.name}"


# ---------------------------------------------------------------------------
# Halaman toko (<toko>.hansproject.app/): template + satu warna + isi dari pemilik
# ---------------------------------------------------------------------------
def page_upload_to(instance, filename: str) -> str:
    """Semua gambar halaman toko di satu folder per toko (mudah dihapus bersama tokonya)."""
    store_id = instance.store_id if isinstance(instance, StorePage) else instance.page.store_id
    return f"uploads/toko/{store_id}/{filename}"


instagram_validator = RegexValidator(
    r"^[A-Za-z0-9._]{1,30}$", "Isi nama pengguna Instagram saja (tanpa @ dan tanpa link), misalnya warungbusari."
)


class StorePage(models.Model):
    """Pengaturan halaman toko. Field di sini adalah DRAF yang sedang diedit pemilik;
    pengunjung melihat salinan yang diterbitkan (``live``) sampai pemilik menerbitkan lagi."""

    TEMPLATES = [
        ("sederhana", "Sederhana"),
        ("etalase", "Etalase"),
        ("menu", "Menu Kafe"),
        ("berani", "Berani"),
    ]
    TEMPLATE_HINTS = {
        "sederhana": "Rapi dan ramah. Cocok untuk warung, toko kelontong, dan usaha rumahan.",
        "etalase": "Foto besar di depan dan barang unggulan berjejer. Cocok untuk toko yang punya foto barang.",
        "menu": "Daftar harga bergaya papan menu. Cocok untuk kafe, kedai, dan rumah makan.",
        "berani": "Warna penuh dan huruf besar. Cocok untuk toko yang ingin tampil mencolok.",
    }
    MAX_HIGHLIGHTS = 6

    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name="page")
    template = models.CharField("template", max_length=12, choices=TEMPLATES, default="sederhana")
    color = models.CharField("warna utama", max_length=7, default="#c2410c")
    tagline = models.CharField(
        "kalimat singkat", max_length=100, blank=True, help_text="Tampil di bawah nama toko. Contoh: Sembako lengkap, harga bersahabat."
    )
    about = models.TextField("tentang toko", max_length=500, blank=True)
    hours = models.CharField("jam buka", max_length=100, blank=True, help_text="Contoh: Setiap hari 07.00–21.00")
    phone = models.CharField("nomor telepon", max_length=20, blank=True, help_text="Pengunjung bisa langsung menelepon.")
    instagram = models.CharField("Instagram", max_length=30, blank=True, validators=[instagram_validator])
    maps_url = models.URLField(
        "link Google Maps", max_length=300, blank=True,
        help_text="Buka lokasi toko di Google Maps, tekan Bagikan, lalu salin link-nya ke sini.",
    )
    show_prices = models.BooleanField("tampilkan daftar harga", default=True, help_text="Semua barang yang sedang dijual, per kategori.")
    logo = models.ImageField("logo", upload_to=page_upload_to, blank=True)
    cover = models.ImageField("foto sampul", upload_to=page_upload_to, blank=True)

    is_published = models.BooleanField("terbit", default=False)
    live = models.JSONField("versi terbit", null=True, blank=True, editable=False)
    published_at = models.DateTimeField("terakhir diterbitkan", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hp_pos_page"
        verbose_name = "halaman toko"
        verbose_name_plural = "halaman toko"

    def __str__(self) -> str:
        return f"Halaman {self.store_id}"


class StoreHighlight(models.Model):
    """Barang unggulan: dipilih dari data barang (boleh diberi foto) atau gambar lain (promo, suasana toko)."""

    page = models.ForeignKey(StorePage, on_delete=models.CASCADE, related_name="highlights")
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="barang"
    )
    image = models.ImageField("foto", upload_to=page_upload_to, blank=True)
    title = models.CharField("judul", max_length=60, blank=True)
    caption = models.CharField("keterangan singkat", max_length=120, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "hp_pos_page_highlight"
        ordering = ["order", "pk"]
        verbose_name = "barang unggulan"
        verbose_name_plural = "barang unggulan"

    def __str__(self) -> str:
        return self.display_title or "Gambar"

    @property
    def display_title(self) -> str:
        return self.title or (self.product.name if self.product else "")
