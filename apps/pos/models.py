"""Aplikasi kasir (POS) untuk pelanggan Paket Tunas / Tumbuh.

Semua toko berbagi tabel yang sama (awalan ``hp_pos_``). Setiap baris punya
kolom ``store`` dan SEMUA query wajib disaring per toko: pemilik lewat
``Store.objects.owned_by(member)``, kasir lewat sesi kasir yang terikat ke satu
toko. Jangan pernah mengambil Product/Sale/Outlet dengan ``pk`` saja.

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


class StoreQuerySet(models.QuerySet):
    def owned_by(self, member):
        return self.filter(owner=member)

    def not_deleted(self, today: date | None = None):
        """Toko yang datanya belum lewat batas hapus (masa aktif + 30 hari)."""
        today = today or timezone.localdate()
        return self.filter(active_until__gte=today - timedelta(days=DELETE_AFTER_DAYS))


class Store(models.Model):
    STATUS_ACTIVE = "aktif"
    STATUS_SUSPENDED = "ditangguhkan"
    STATUSES = [(STATUS_ACTIVE, "Normal"), (STATUS_SUSPENDED, "Ditangguhkan admin")]

    # Keadaan toko yang dihitung dari masa aktif (lihat ``state``).
    STATE_ACTIVE = "aktif"
    STATE_GRACE = "tenggang"
    STATE_LOCKED = "terkunci"
    STATE_DELETED = "dihapus"
    STATE_SUSPENDED = "ditangguhkan"
    STATE_LABELS = {
        STATE_ACTIVE: "Aktif",
        STATE_GRACE: "Masa tenggang",
        STATE_LOCKED: "Terkunci (belum diperpanjang)",
        STATE_DELETED: "Data sudah dihapus",
        STATE_SUSPENDED: "Ditangguhkan",
    }

    RECEIPT_WIDTHS = [(58, "58 mm (printer kecil)"), (80, "80 mm (printer besar)")]

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

    package = models.ForeignKey(
        "content.Package", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="paket"
    )
    package_name = models.CharField("nama paket", max_length=60)
    base_outlets = models.PositiveSmallIntegerField(
        "outlet termasuk paket", default=2, validators=[MaxValueValidator(500)]
    )
    extra_outlets = models.PositiveSmallIntegerField(
        "outlet tambahan (dibeli)", default=0, validators=[MaxValueValidator(500)],
        help_text="Diisi admin bila pelanggan membeli tambahan toko/cabang.",
    )
    status = models.CharField("status", max_length=14, choices=STATUSES, default=STATUS_ACTIVE)
    active_until = models.DateField("aktif sampai")
    admin_note = models.TextField(
        "catatan untuk pemilik toko", blank=True, max_length=1000,
        help_text="Tampil di halaman toko milik pelanggan, misalnya alasan ditangguhkan.",
    )
    created_at = models.DateTimeField("dibuat", auto_now_add=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        db_table = "hp_pos_store"
        ordering = ["name"]
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

    # --- Masa aktif ---
    def state(self, today: date | None = None) -> str:
        today = today or timezone.localdate()
        if today > self.delete_on:
            return self.STATE_DELETED
        if self.status == self.STATUS_SUSPENDED:
            return self.STATE_SUSPENDED
        if today <= self.active_until:
            return self.STATE_ACTIVE
        if today <= self.active_until + timedelta(days=GRACE_DAYS):
            return self.STATE_GRACE
        return self.STATE_LOCKED

    @property
    def state_now(self) -> str:
        return self.state()

    @property
    def state_label(self) -> str:
        return self.STATE_LABELS[self.state()]

    @property
    def state_tone(self) -> str:
        return {self.STATE_ACTIVE: "ok", self.STATE_GRACE: "wait"}.get(self.state(), "off")

    @property
    def grace_until(self) -> date:
        return self.active_until + timedelta(days=GRACE_DAYS)

    @property
    def delete_on(self) -> date:
        """Hari terakhir data masih ada. Setelah tanggal ini data dihapus permanen."""
        return self.active_until + timedelta(days=DELETE_AFTER_DAYS)

    @property
    def can_sell(self) -> bool:
        """Kasir boleh transaksi: aktif atau masa tenggang."""
        return self.state() in (self.STATE_ACTIVE, self.STATE_GRACE)

    @property
    def can_edit(self) -> bool:
        """Pemilik boleh mengubah barang, outlet, dan pengaturan."""
        return self.can_sell

    @property
    def days_left(self) -> int:
        return (self.active_until - timezone.localdate()).days

    # --- Outlet ---
    @property
    def outlet_limit(self) -> int:
        return self.base_outlets + self.extra_outlets

    @property
    def outlets_used(self) -> int:
        """Toko/cabang (outlet) aktif yang sudah dibuat."""
        return self.outlets.filter(is_active=True).count()

    @property
    def outlets_free(self) -> int:
        return max(0, self.outlet_limit - self.outlets_used)

    @property
    def outlet_quota_text(self) -> str:
        """Contoh: 'Paket Tunas 2 + tambahan 1'."""
        text = f"Paket {self.package_name} {self.base_outlets}"
        return f"{text} + tambahan {self.extra_outlets}" if self.extra_outlets else text


class Outlet(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="outlets")
    number = models.PositiveSmallIntegerField("nomor outlet", editable=False)
    name = models.CharField("nama outlet", max_length=60)
    address = models.CharField("alamat outlet", max_length=200, blank=True, help_text="Dicetak di struk bila diisi.")
    is_active = models.BooleanField("aktif", default=True)
    sale_seq = models.PositiveIntegerField(default=0, editable=False)  # nomor transaksi terakhir
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hp_pos_outlet"
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["store", "number"], name="hp_pos_outlet_number_uniq")]

    def __str__(self) -> str:
        return self.name


username_validator = RegexValidator(
    r"^[a-z0-9][a-z0-9._-]{2,29}$",
    "3–30 karakter: huruf kecil, angka, titik, minus, atau garis bawah. Tanpa spasi.",
)


class Cashier(models.Model):
    """Akun kasir. Satu outlet = satu akun (sesuai paket). Dibuat oleh pemilik toko."""

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="cashiers")
    outlet = models.OneToOneField(Outlet, on_delete=models.CASCADE, related_name="cashier")
    username = models.CharField("nama pengguna", max_length=30, validators=[username_validator])
    pin_hash = models.CharField(max_length=128)
    is_active = models.BooleanField("aktif", default=True)
    failed_count = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField("terakhir masuk", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hp_pos_cashier"
        constraints = [models.UniqueConstraint(fields=["store", "username"], name="hp_pos_cashier_username_uniq")]

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
    # RESTRICT: outlet yang punya transaksi tidak bisa dihapus sendiri (cukup dinonaktifkan),
    # tapi tetap ikut terhapus bila seluruh toko dihapus.
    outlet = models.ForeignKey(Outlet, on_delete=models.RESTRICT, related_name="sales")
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
