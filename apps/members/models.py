"""Akun pelanggan (login dengan Google), pesanan, dan pertanyaan.

Sengaja TERPISAH dari akun panel pengelola (``accounts.AdminUser``):
pelanggan tidak pernah bisa masuk ke panel, dan sesi keduanya memakai
cookie yang berbeda.
"""
from __future__ import annotations

import secrets

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .storage import private_storage

ORDER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # tanpa O/0, I/1 supaya tidak tertukar


def new_order_code() -> str:
    return "HP-" + "".join(secrets.choice(ORDER_CODE_ALPHABET) for _ in range(6))


def new_verify_token() -> str:
    """Kode acak untuk halaman publik "cek keaslian pesanan" (tidak bisa ditebak dari kode pesanan)."""
    return secrets.token_urlsafe(18)


phone_validator = RegexValidator(r"^62\d{8,13}$", "Nomor HP tidak valid.")


def format_phone(phone: str) -> str:
    """62812xxxx -> 0812-xxxx-xxxx (lebih mudah dibaca)."""
    if not phone:
        return ""
    local = "0" + phone[2:]
    return "-".join([local[:4], local[4:8], local[8:]]).rstrip("-")


class Member(models.Model):
    google_sub = models.CharField("ID akun Google", max_length=255, unique=True, editable=False)
    email = models.EmailField("email", max_length=254)
    name = models.CharField("nama", max_length=120)
    phone = models.CharField("nomor HP", max_length=16, blank=True, validators=[phone_validator])
    business_name = models.CharField("nama usaha", max_length=120, blank=True)
    is_active = models.BooleanField(
        "akun aktif", default=True, help_text="Matikan untuk memblokir pelanggan ini masuk ke akunnya."
    )
    created_at = models.DateTimeField("terdaftar", auto_now_add=True)
    last_login_at = models.DateTimeField("terakhir masuk", null=True, blank=True)
    # Bukti persetujuan Syarat & Ketentuan (dan pernyataan sudah membaca Kebijakan Privasi):
    # versi dokumen yang disetujui + waktunya.
    terms_version = models.DateField("versi S&K yang disetujui", null=True, blank=True, editable=False)
    terms_accepted_at = models.DateTimeField("menyetujui S&K pada", null=True, blank=True, editable=False)

    class Meta:
        db_table = "hp_member"
        ordering = ["-created_at"]
        verbose_name = "pelanggan"
        verbose_name_plural = "pelanggan"

    def __str__(self) -> str:
        return f"{self.display_name} ({self.email})"

    @property
    def display_name(self) -> str:
        return self.name or self.email.split("@")[0]

    @property
    def initial(self) -> str:
        return (self.display_name[:1] or "?").upper()

    @property
    def profile_complete(self) -> bool:
        return bool(self.name and self.phone and self.business_name)

    @property
    def phone_display(self) -> str:
        return format_phone(self.phone)

    def needs_terms(self, version) -> bool:
        """Belum pernah menyetujui, atau versi dokumen sudah diperbarui sejak terakhir disetujui."""
        return self.terms_version is None or (version is not None and self.terms_version < version)


class MemberSession(models.Model):
    """Sesi login pelanggan. Cookie hanya berisi token acak; database menyimpan hash-nya."""

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="sessions")
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "hp_member_session"


class Order(models.Model):
    STATUS_PAYMENT = "bayar"
    STATUS_CHECKING = "dicek"
    STATUS_CONSULT = "konsultasi"
    STATUS_PROCESS = "diproses"
    STATUS_ACTIVE = "aktif"
    STATUS_DONE = "selesai"
    STATUS_CANCELLED = "batal"
    STATUSES = [
        (STATUS_PAYMENT, "Menunggu pembayaran"),
        (STATUS_CHECKING, "Bukti bayar sedang dicek"),
        (STATUS_CONSULT, "Menunggu konsultasi"),
        (STATUS_PROCESS, "Sedang diproses"),
        (STATUS_ACTIVE, "Aktif"),
        (STATUS_DONE, "Selesai"),
        (STATUS_CANCELLED, "Dibatalkan"),
    ]
    OPEN_STATUSES = (STATUS_PAYMENT, STATUS_CHECKING, STATUS_CONSULT, STATUS_PROCESS)
    # Pelanggan boleh mengirim / mengganti bukti bayar & membatalkan hanya di status ini.
    PROOF_STATUSES = (STATUS_PAYMENT, STATUS_CHECKING)
    # Pelanggan boleh membatalkan sebelum diaktifkan (termasuk yang sudah bayar -> bisa minta refund).
    CANCELLABLE_STATUSES = (STATUS_PAYMENT, STATUS_CHECKING, STATUS_CONSULT)
    # Pembayaran sudah dicek & diterima admin: bukti pesanan + QR keaslian baru tersedia di sini.
    VERIFIED_STATUSES = (STATUS_PROCESS, STATUS_ACTIVE, STATUS_DONE)

    TYPE_NEW = "baru"
    TYPE_RENEWAL = "perpanjang"
    TYPE_ADDON = "tambahan"
    TYPES = [(TYPE_NEW, "Pesanan baru"), (TYPE_RENEWAL, "Perpanjangan"), (TYPE_ADDON, "Tambahan toko")]

    # Pesanan yang sudah dibayar disimpan 10 tahun (kewajiban pencatatan pajak, UU KUP Pasal 28 ayat 11),
    # walau akun pelanggan dihapus. Saat akun dihapus, identitas pemesan disalin ke kolom buyer_*.
    RETENTION_YEARS = 10
    PAID_STATUSES = ("dicek", "diproses", "aktif", "selesai")

    code = models.CharField("kode pesanan", max_length=12, unique=True, default=new_order_code, editable=False)
    member = models.ForeignKey(
        Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders", verbose_name="pelanggan"
    )
    buyer_name = models.CharField("nama pemesan (akun sudah dihapus)", max_length=120, blank=True, editable=False)
    buyer_email = models.EmailField("email pemesan (akun sudah dihapus)", max_length=254, blank=True, editable=False)
    buyer_phone = models.CharField("HP pemesan (akun sudah dihapus)", max_length=16, blank=True, editable=False)
    buyer_business = models.CharField("usaha pemesan (akun sudah dihapus)", max_length=120, blank=True, editable=False)
    order_type = models.CharField("jenis pesanan", max_length=10, choices=TYPES, default=TYPE_NEW)
    # Aplikasi kasir: alamat toko yang dipilih pelanggan (pesanan baru), atau
    # permintaan ganti alamat (perpanjangan; kosong = tidak ganti, perlu persetujuan admin).
    subdomain = models.CharField("alamat toko", max_length=30, blank=True, db_index=True)
    store = models.ForeignKey(
        "pos.Store", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders", verbose_name="toko"
    )
    # SIM: data instansi yang dipesan (tingkat, nomor, nama, kelurahan, ...) untuk pesanan baru,
    # dan wilayah yang diperpanjang / dibuat saat aktivasi.
    details = models.JSONField("rincian layanan", default=dict, blank=True)
    wilayah = models.ForeignKey(
        "sim.Wilayah", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders", verbose_name="wilayah SIM"
    )
    activated_at = models.DateTimeField("diaktifkan", null=True, blank=True, editable=False)
    verify_token = models.CharField(
        "kode keaslian", max_length=32, unique=True, null=True, editable=False, default=new_verify_token
    )
    quantity = models.PositiveSmallIntegerField(
        "jumlah", default=1, help_text="Untuk pesanan tambahan toko: berapa toko/cabang yang ditambah."
    )
    package = models.ForeignKey(
        "content.Package", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="paket"
    )
    # Salinan data paket saat dipesan: tetap benar walau harga paket diubah kemudian.
    package_name = models.CharField("nama paket", max_length=60)
    package_category = models.CharField("jenis", max_length=10)
    price_text = models.CharField("harga saat dipesan", max_length=80)
    amount = models.PositiveIntegerField(
        "nominal yang harus dibayar (Rp)", null=True, blank=True,
        help_text="Disalin dari harga paket saat dipesan. Dipakai sebagai nilai awal refund.",
    )
    status = models.CharField("status", max_length=12, choices=STATUSES, default=STATUS_PAYMENT, db_index=True)
    admin_note = models.TextField(
        "catatan untuk pelanggan", blank=True, max_length=2000,
        help_text="Tampil di halaman pesanan pelanggan. Misalnya: link aplikasi, jadwal konsultasi, atau alasan bukti bayar ditolak.",
    )
    payment_proof = models.ImageField("bukti bayar", storage=private_storage, upload_to="bukti-bayar/%Y/%m/", blank=True)
    proof_uploaded_at = models.DateTimeField("bukti dikirim", null=True, blank=True)
    created_at = models.DateTimeField("dipesan", auto_now_add=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    class Meta:
        db_table = "hp_member_order"
        ordering = ["-created_at"]
        verbose_name = "pesanan"
        verbose_name_plural = "pesanan"

    def __str__(self) -> str:
        return f"{self.code} — {self.title}"

    @property
    def title(self) -> str:
        """Contoh: "Kasir · Paket Tunas", "Perpanjang SIM · Paket Tumbuh", "Website & Aplikasi · Paket Rimba"."""
        product = self.product_short
        if self.is_renewal:
            return f"Perpanjang {product} · Paket {self.package_name}".replace("  ", " ")
        if self.is_addon:
            return f"Kasir · Tambah {self.quantity} toko"
        return f"{product} · Paket {self.package_name}" if product else f"Paket {self.package_name}"

    @property
    def product_short(self) -> str:
        from apps.content.models import Package

        return Package.PRODUCT_SHORT.get(self.package_category, "")

    @property
    def product_label(self) -> str:
        from apps.content.models import Package

        return Package.PRODUCT_LABELS.get(self.package_category, "")

    # --- Rincian harga (diisi admin per pesanan, mis. Paket Rimba) ---
    @property
    def item_list(self) -> list:
        if not hasattr(self, "_item_list"):
            self._item_list = list(self.items.all()) if self.pk else []
        return self._item_list

    @property
    def item_sum(self) -> int:
        """Total semua rincian = nominal yang dibayar pelanggan."""
        return sum(item.amount for item in self.item_list)

    @property
    def verify_path(self) -> str:
        from django.urls import reverse

        return reverse("web:cek-pesanan", args=[self.verify_token]) if self.verify_token else ""

    @property
    def has_verified_proof(self) -> bool:
        """Bukti pesanan + QR boleh dicetak: pembayaran sudah dicek admin (Sedang diproses / Aktif / Selesai)."""
        return bool(self.verify_token) and self.status in self.VERIFIED_STATUSES

    @property
    def is_addon(self) -> bool:
        return self.order_type == self.TYPE_ADDON

    # Identitas pemesan: dari akun, atau salinan bila akun sudah dihapus.
    @property
    def customer_name(self) -> str:
        return self.member.display_name if self.member_id else (self.buyer_name or "(akun dihapus)")

    @property
    def customer_email(self) -> str:
        return self.member.email if self.member_id else self.buyer_email

    @property
    def customer_phone(self) -> str:
        return self.member.phone_display if self.member_id else format_phone(self.buyer_phone)

    @property
    def customer_business(self) -> str:
        return self.member.business_name if self.member_id else self.buyer_business

    @property
    def is_renewal(self) -> bool:
        return self.order_type == self.TYPE_RENEWAL

    @property
    def is_pos(self) -> bool:
        return self.package_category == "kasir"

    @property
    def is_sim(self) -> bool:
        return self.package_category == "sim"

    @property
    def is_subscription(self) -> bool:
        """Layanan langganan (kasir/SIM): bayar dulu, diaktifkan admin. Selain itu jasa (konsultasi dulu)."""
        return self.is_pos or self.is_sim

    @property
    def subject_label(self) -> str:
        """Untuk apa pesanan ini (panel): alamat toko, nama instansi SIM, atau kosong untuk jasa."""
        if self.package_category == "sim":
            return self.sim_label
        if self.store_id:
            return self.store.host
        return self.subdomain_host

    @property
    def sim_label(self) -> str:
        """Nama wilayah yang dipesan, mis. 'RT 005 / RW 003, Kel. Sukamaju'."""
        if self.wilayah_id:
            return self.wilayah.label
        d = self.details or {}
        level = d.get("tingkat", "")
        if level in ("rt", "rw"):
            text = f"{level.upper()} {d.get('nomor', '')}"
            if level == "rt" and d.get("rw"):
                text += f" / RW {d['rw']}"
            return text + (f", Kel. {d['kelurahan']}" if d.get("kelurahan") else "")
        if level:
            return f"{level.capitalize()} {d.get('nama', '')}".strip()
        return ""

    @property
    def subdomain_host(self) -> str:
        from apps.pos.subdomains import store_host

        return store_host(self.subdomain) if self.subdomain else ""

    @property
    def wants_new_subdomain(self) -> bool:
        """Perpanjangan dengan permintaan ganti alamat toko."""
        return bool(self.is_renewal and self.subdomain and self.store_id and self.subdomain != self.store.subdomain)

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES

    @property
    def can_send_proof(self) -> bool:
        return self.status in self.PROOF_STATUSES

    @property
    def can_cancel(self) -> bool:
        return self.status in self.CANCELLABLE_STATUSES

    @property
    def is_paid(self) -> bool:
        """Sudah ada pembayaran yang masuk (bukti bayar dikirim)."""
        return bool(self.payment_proof)

    @property
    def refund_or_none(self):
        try:
            return self.refund
        except Refund.DoesNotExist:
            return None

    @property
    def needs_consultation(self) -> bool:
        """Pesanan jasa (mis. Paket Rimba) yang dibahas lewat obrolan konsultasi."""
        return not self.is_subscription and self.status in (self.STATUS_CONSULT, self.STATUS_PROCESS)

    @property
    def consultation_chat(self):
        return self.chats.order_by("-pk").first() if self.pk else None

    @property
    def can_request_refund(self) -> bool:
        """Pesanan yang sudah dibayar lalu dibatalkan (oleh pelanggan atau admin) bisa diajukan refund."""
        return self.status == self.STATUS_CANCELLED and self.is_paid and self.refund_or_none is None

    @property
    def status_tone(self) -> str:
        """Warna label status: wait (kuning), ok (hijau), off (abu-abu)."""
        if self.status in (self.STATUS_ACTIVE, self.STATUS_DONE):
            return "ok"
        if self.status == self.STATUS_CANCELLED:
            return "off"
        return "wait"


class OrderItem(models.Model):
    """Satu baris rincian harga pesanan, diketik admin (mis. Domain Rp250.000/tahun)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    name = models.CharField("rincian", max_length=120, help_text="Contoh: Domain .com, Database, Konsultasi.")
    amount = models.PositiveIntegerField("harga (Rp)")
    period = models.CharField(
        "periode", max_length=40, blank=True, default="",
        help_text="Diketik bebas, mis. 1 tahun, 3 bulan, 14 hari. Kosongkan bila sekali bayar.",
    )
    note = models.CharField("keterangan", max_length=200, blank=True)
    sort = models.PositiveSmallIntegerField("urutan", default=0)

    class Meta:
        db_table = "hp_member_order_item"
        ordering = ["sort", "id"]
        verbose_name = "rincian harga"
        verbose_name_plural = "rincian harga"

    def __str__(self) -> str:
        return self.name

    @property
    def suffix(self) -> str:
        """' / 3 bulan' (kosong bila sekali bayar)."""
        return f" / {self.period}" if self.period else ""


TOPICS = [
    ("umum", "Pertanyaan umum"),
    ("konsultasi", "Konsultasi pesanan"),
    ("kasir", "Aplikasi kasir"),
    ("sim", "Sistem Informasi Manajemen (SIM)"),
    ("jasa", "Website & aplikasi"),
    ("tiket", "Tiket online"),
    ("pesanan", "Pesanan saya"),
    ("refund", "Refund / pengembalian dana"),
    ("tambah-toko", "Tambah toko / cabang"),
    ("tambah-simpan", "Tambah tempat simpan"),
    ("paket", "Paket & harga"),
]
TOPIC_KEYS = {key for key, _ in TOPICS}


class Refund(models.Model):
    """Pengembalian dana untuk pesanan yang sudah dibayar lalu dibatalkan."""

    STATUS_REQUESTED = "diajukan"
    STATUS_PROCESSING = "diproses"
    STATUS_DONE = "selesai"
    STATUS_REJECTED = "ditolak"
    STATUSES = [
        (STATUS_REQUESTED, "Diajukan"),
        (STATUS_PROCESSING, "Sedang diproses"),
        (STATUS_DONE, "Sudah ditransfer"),
        (STATUS_REJECTED, "Ditolak"),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="refund", verbose_name="pesanan")
    amount = models.PositiveIntegerField(
        "nominal refund (Rp)", null=True, blank=True,
        help_text="Biasanya sama dengan nominal pesanan. Untuk pengembalian sebagian (dihitung per hari), ubah di sini.",
    )
    bank_name = models.CharField("bank / dompet digital", max_length=60)
    account_number = models.CharField("nomor rekening", max_length=30)
    account_holder = models.CharField("nama pemilik rekening", max_length=120)
    note = models.TextField("catatan pelanggan", blank=True, max_length=1000)
    status = models.CharField("status", max_length=10, choices=STATUSES, default=STATUS_REQUESTED, db_index=True)
    admin_note = models.TextField(
        "catatan untuk pelanggan", blank=True, max_length=2000,
        help_text="Tampil di halaman pesanan pelanggan, misalnya alasan bila ditolak.",
    )
    transfer_proof = models.ImageField(
        "bukti transfer refund", storage=private_storage, upload_to="refund/%Y/%m/", blank=True
    )
    created_at = models.DateTimeField("diajukan", auto_now_add=True)
    processed_at = models.DateTimeField("selesai diproses", null=True, blank=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    class Meta:
        db_table = "hp_member_refund"
        ordering = ["-created_at"]
        verbose_name = "refund"
        verbose_name_plural = "refund"

    def __str__(self) -> str:
        return f"Refund {self.order.code}"

    @property
    def status_tone(self) -> str:
        return {self.STATUS_DONE: "ok", self.STATUS_REJECTED: "off"}.get(self.status, "wait")


class Conversation(models.Model):
    """Ruang obrolan pelanggan dengan HANS Project. Admin bisa menutupnya (Selesai)."""

    STATUS_OPEN = "terbuka"
    STATUS_CLOSED = "selesai"
    STATUSES = [(STATUS_OPEN, "Terbuka"), (STATUS_CLOSED, "Selesai")]
    MAX_OPEN = 3  # ruang obrolan terbuka per pelanggan

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="chats", verbose_name="pelanggan")
    topic = models.CharField("topik", max_length=20, choices=TOPICS, default="umum")
    # Obrolan konsultasi yang terikat ke satu pesanan (mis. Paket Rimba). Tidak dihitung batas obrolan aktif.
    order = models.ForeignKey(
        Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="chats", verbose_name="pesanan"
    )
    status = models.CharField("status", max_length=8, choices=STATUSES, default=STATUS_OPEN, db_index=True)
    created_at = models.DateTimeField("dibuat", default=timezone.now)
    closed_at = models.DateTimeField("ditutup", null=True, blank=True)
    last_message_at = models.DateTimeField("pesan terakhir", null=True, blank=True, db_index=True)
    last_sender = models.CharField(max_length=10, blank=True)
    member_read_at = models.DateTimeField(null=True, blank=True)
    admin_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hp_member_chat"
        ordering = ["-last_message_at", "-created_at"]
        verbose_name = "obrolan"
        verbose_name_plural = "obrolan"

    def __str__(self) -> str:
        return f"Obrolan #{self.pk} — {self.title}"

    @property
    def title(self) -> str:
        if self.order_id:
            return f"Konsultasi {self.order.code} · {self.order.title}"
        return self.get_topic_display()

    @property
    def is_open(self) -> bool:
        return self.status == self.STATUS_OPEN

    @property
    def unread_for_member(self) -> bool:
        return self.last_sender == ChatMessage.SENDER_ADMIN and (
            self.member_read_at is None or self.member_read_at < self.last_message_at
        )

    @property
    def unread_for_admin(self) -> bool:
        return self.last_sender == ChatMessage.SENDER_MEMBER and (
            self.admin_read_at is None or self.admin_read_at < self.last_message_at
        )


class ChatMessage(models.Model):
    SENDER_MEMBER = "pelanggan"
    SENDER_ADMIN = "admin"
    SENDERS = [(SENDER_MEMBER, "Pelanggan"), (SENDER_ADMIN, "HANS Project")]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=10, choices=SENDERS)
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    text = models.TextField("pesan", blank=True, max_length=2000)
    image = models.ImageField("gambar", storage=private_storage, upload_to="chat/%Y/%m/", blank=True)
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="membalas"
    )
    created_at = models.DateTimeField("dikirim", default=timezone.now, db_index=True)

    class Meta:
        db_table = "hp_member_chat_message"
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return self.preview

    @property
    def preview(self) -> str:
        text = " ".join(self.text.split())
        if not text:
            return "Gambar"
        return text[:80] + ("…" if len(text) > 80 else "")

    @property
    def from_admin(self) -> bool:
        return self.sender == self.SENDER_ADMIN
