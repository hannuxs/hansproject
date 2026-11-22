"""Model konten yang dikelola pemilik lewat panel (tanpa menyentuh kode).

Semua tabel memakai awalan ``hp_`` supaya tidak bertabrakan dengan tabel lain
di database server.
"""
from __future__ import annotations

import datetime

from django.conf import settings
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from apps.core import formatting

MAX_PRICE = 1_000_000_000
price_validators = [MaxValueValidator(MAX_PRICE)]

# Pilihan ikon (nama simbol di static/img/icons.svg).
ICON_CHOICES = [
    ("", "— tanpa ikon —"),
    ("box", "Kotak barang"),
    ("calculator", "Kalkulator"),
    ("receipt", "Struk"),
    ("tag", "Label diskon"),
    ("chart", "Grafik"),
    ("globe", "Alamat internet"),
    ("layout", "Halaman web"),
    ("database", "Penyimpanan"),
    ("store", "Toko"),
    ("palette", "Tampilan"),
    ("chat", "Chat"),
    ("smartphone", "HP"),
    ("zap", "Kilat"),
    ("headset", "Layanan"),
    ("clock", "Jam"),
    ("cloud", "Awan"),
    ("shield", "Perisai"),
    ("code", "Kode"),
    ("sparkles", "Fitur pintar"),
    ("user-check", "Orang khusus"),
    ("server", "Server"),
    ("users", "Warga / banyak orang"),
    ("file", "Surat / dokumen"),
    ("printer", "Cetak"),
    ("qr", "Kode QR"),
    ("link", "Terhubung"),
    ("megaphone", "Pengumuman"),
    ("scan", "Scan dokumen"),
    ("search", "Cari"),
    ("ticket", "Tiket"),
    ("map-pin", "Lokasi"),
    ("building", "Kantor"),
]


class OrderedModel(models.Model):
    order = models.PositiveIntegerField("urutan", default=0, help_text="Angka kecil tampil lebih dulu.")

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class TwoLevelText(OrderedModel):
    """Satu poin dengan dua versi: bahasa sederhana + istilah teknis."""

    simple = models.CharField("versi sederhana", max_length=255)
    technical = models.CharField("versi teknis", max_length=255, blank=True)
    icon = models.CharField("ikon", max_length=30, blank=True, choices=ICON_CHOICES)

    class Meta(OrderedModel.Meta):
        abstract = True

    def __str__(self) -> str:
        return self.simple


# ---------------------------------------------------------------------------
# Pengaturan umum (satu baris saja)
# ---------------------------------------------------------------------------


LEGAL_VERSION_DEFAULT = datetime.date(2026, 11, 22)


class SiteSettings(models.Model):
    # Kontak: semua keperluan lewat DM Instagram (dan menu Tanya Kami di akun).
    instagram_username = models.CharField(
        "username Instagram (untuk DM)", max_length=30, blank=True, default="hansproject.app",
        validators=[RegexValidator(r"^[A-Za-z0-9._]{1,30}$", "Hanya huruf, angka, titik, dan garis bawah (tanpa @).")],
        help_text="Tanpa @. Dipakai untuk tombol 'DM Instagram'. Kosongkan untuk menyembunyikan.",
    )
    email = models.EmailField("email", blank=True)
    support_hours = models.CharField(
        "jam kerja layanan", max_length=120, blank=True, help_text="Contoh: Senin–Sabtu, 08.00–17.00 WITA."
    )
    # instagram_url: TIDAK dipakai lagi; link Instagram selalu dari instagram_username.
    instagram_url = models.URLField("link Instagram", blank=True)
    facebook_url = models.URLField("link Facebook", blank=True)
    tiktok_url = models.URLField("link TikTok", blank=True)
    youtube_url = models.URLField("link YouTube", blank=True)

    # Pembayaran
    show_payment_info = models.BooleanField(
        "tampilkan info rekening & QRIS di website", default=False,
        help_text="Bila mati, info pembayaran tidak ditampilkan di website.",
    )
    qris_image = models.FileField("gambar QRIS", upload_to="uploads/qris/", blank=True)

    # Tampilan utama
    hero_title = models.CharField(
        "judul utama", max_length=120, default="Aplikasi kasir mulai {harga_mulai} sebulan",
        help_text="{harga_mulai} otomatis diganti harga paket kasir termurah, misalnya Rp25 ribu.",
    )
    hero_subtitle = models.CharField(
        "kalimat pendukung", max_length=200, default="Catat jualan, hitung uang, cetak struk. Cukup pakai HP."
    )
    announcement_active = models.BooleanField("tampilkan pengumuman", default=False)
    announcement_text = models.CharField(
        "teks pengumuman", max_length=200, blank=True, help_text="Misalnya info promo sementara."
    )
    show_testimonials = models.BooleanField(
        "tampilkan bagian testimoni", default=False,
        help_text="Hanya tampil bila ada testimoni yang diaktifkan.",
    )

    # SEO
    seo_title = models.CharField(
        "judul di Google", max_length=70,
        default="HANS Project: Aplikasi Kasir, SIM & Jasa Website/Aplikasi",
    )
    seo_description = models.CharField(
        "deskripsi di Google", max_length=170,
        default=(
            "Solusi digital siap pakai: aplikasi kasir untuk usaha, Sistem Informasi Manajemen (SIM) untuk RT, RW, "
            "kelurahan & instansi, serta jasa pembuatan website & aplikasi."
        ),
    )

    # Persetujuan Syarat & Ketentuan / Kebijakan Privasi
    legal_version = models.DateField(
        "versi Syarat & Ketentuan dan Kebijakan Privasi", default=LEGAL_VERSION_DEFAULT,
        help_text=(
            "Tanggal versi yang berlaku. Ubah tanggal ini HANYA bila isi Syarat & Ketentuan atau Kebijakan Privasi "
            "berubah penting: setiap pelanggan akan diminta menyetujui ulang saat masuk berikutnya."
        ),
    )

    seeded_at = models.DateTimeField(null=True, blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hp_site_settings"
        verbose_name = "pengaturan umum"
        verbose_name_plural = "pengaturan umum"

    def __str__(self) -> str:
        return "Pengaturan umum"

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def instagram_profile_url(self) -> str:
        """Satu-satunya alamat Instagram di website, contoh: https://www.instagram.com/hansproject.app

        Selalu dibentuk dari ``instagram_username`` (kolom ``instagram_url`` lama tidak dipakai).
        """
        return f"https://www.instagram.com/{self.instagram_username}" if self.instagram_username else ""

    @property
    def instagram_dm_url(self) -> str:
        """Tombol 'DM Instagram' memakai alamat profil yang sama."""
        return self.instagram_profile_url

    @property
    def social_links(self) -> list[tuple[str, str, str]]:
        links = [
            ("instagram", "Instagram", self.instagram_profile_url),
            ("facebook", "Facebook", self.facebook_url),
            ("tiktok", "TikTok", self.tiktok_url),
            ("youtube", "YouTube", self.youtube_url),
        ]
        return [link for link in links if link[2]]


class BankAccount(OrderedModel):
    PLACEHOLDER_NUMBER = "0000000000"

    bank_name = models.CharField("nama bank", max_length=60)
    account_number = models.CharField(
        "nomor rekening", max_length=30, validators=[RegexValidator(r"^[0-9 .-]{4,30}$", "Hanya angka.")]
    )
    account_holder = models.CharField("atas nama", max_length=80)
    is_active = models.BooleanField("aktif", default=True)

    class Meta(OrderedModel.Meta):
        db_table = "hp_bank_account"
        verbose_name = "rekening bank"
        verbose_name_plural = "rekening bank"

    def __str__(self) -> str:
        return f"{self.bank_name} {self.account_number}"

    @property
    def is_placeholder(self) -> bool:
        return set(self.account_number.replace(" ", "")) <= {"0"}


# ---------------------------------------------------------------------------
# Paket & harga
# ---------------------------------------------------------------------------
class Package(OrderedModel):
    CATEGORY_POS = "kasir"
    CATEGORY_SERVICE = "jasa"
    CATEGORY_SIM = "sim"
    CATEGORIES = [
        (CATEGORY_POS, "Aplikasi Kasir (langganan)"),
        (CATEGORY_SIM, "Sistem Informasi Manajemen / SIM (langganan)"),
        (CATEGORY_SERVICE, "Jasa Website & Aplikasi"),
    ]
    # Nama solusi yang tampil ke pelanggan (judul pesanan, menu, dashboard).
    PRODUCT_LABELS = {
        CATEGORY_POS: "Aplikasi Kasir",
        CATEGORY_SIM: "Sistem Informasi Manajemen (SIM)",
        CATEGORY_SERVICE: "Website & Aplikasi",
    }
    PRODUCT_SHORT = {CATEGORY_POS: "Kasir", CATEGORY_SIM: "SIM", CATEGORY_SERVICE: "Website & Aplikasi"}

    code = models.SlugField(
        "kode", max_length=30, unique=True,
        help_text="Huruf kecil tanpa spasi, misalnya: tunas. Dipakai untuk statistik klik.",
    )
    category = models.CharField("jenis layanan", max_length=10, choices=CATEGORIES, default=CATEGORY_POS)
    name = models.CharField("nama paket", max_length=40)
    icon = models.CharField("emoji", max_length=8, blank=True, help_text="Contoh: 🌱")
    tagline = models.CharField("cocok untuk", max_length=200, blank=True)
    description = models.TextField("keterangan tambahan", max_length=600, blank=True)

    price = models.PositiveIntegerField("harga (Rp)", validators=price_validators)
    price_prefix = models.CharField("kata sebelum harga", max_length=20, blank=True, help_text="Contoh: Mulai")
    price_suffix = models.CharField("keterangan harga", max_length=40, default="/bulan", help_text="Contoh: /bulan")
    monthly_price = models.PositiveIntegerField(
        "biaya bulanan lanjutan (Rp)", null=True, blank=True, validators=price_validators,
        help_text="Isi bila ada biaya bulanan setelah biaya pembuatan (seperti Paket Rimba).",
    )
    outlet_count = models.PositiveSmallIntegerField(
        "jumlah toko/outlet termasuk", null=True, blank=True, help_text="Aplikasi Kasir. Dipakai kalkulator hemat."
    )
    scan_limit = models.PositiveIntegerField(
        "batas scan dokumen per bulan", null=True, blank=True,
        help_text="SIM: jumlah foto KK/KTP/dokumen yang bisa dibaca otomatis (OCR) per bulan. Kosongkan = tanpa batas.",
    )

    badge = models.CharField("label sorotan", max_length=40, blank=True, help_text="Contoh: Paling Direkomendasikan")
    is_highlighted = models.BooleanField("tonjolkan paket ini", default=False)
    includes_from = models.ForeignKey(
        "self", verbose_name="sudah termasuk semua isi paket", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text="Misalnya Paket Tumbuh berisi semua yang ada di Paket Tunas.",
    )
    is_active = models.BooleanField("tampilkan", default=True)

    class Meta(OrderedModel.Meta):
        db_table = "hp_package"
        verbose_name = "paket"
        verbose_name_plural = "paket & harga"

    def __str__(self) -> str:
        # Kasir & SIM sama-sama punya Paket Tunas/Tumbuh: sebut solusinya agar tidak tertukar.
        return f"{self.product_short} · Paket {self.name}" if self.product_short else f"Paket {self.name}"

    @property
    def is_pos(self) -> bool:
        return self.category == self.CATEGORY_POS

    @property
    def is_sim(self) -> bool:
        return self.category == self.CATEGORY_SIM

    @property
    def is_service(self) -> bool:
        return self.category == self.CATEGORY_SERVICE

    @property
    def product_label(self) -> str:
        return self.PRODUCT_LABELS.get(self.category, "")

    @property
    def product_short(self) -> str:
        return self.PRODUCT_SHORT.get(self.category, "")

    @property
    def is_priced(self) -> bool:
        """Langganan berharga Rp0 = harga belum ditentukan pemilik: tampil "segera diumumkan", belum bisa dipesan."""
        return self.is_service or self.price > 0

    @property
    def price_text(self) -> str:
        """Teks harga lengkap (disalin ke pesanan). Contoh: Rp25.000/bulan."""
        parts = []
        if self.price_prefix:
            parts.append(self.price_prefix.lower() + " ")
        parts.append(formatting.rupiah(self.price))
        suffix = self.price_suffix.strip()
        if suffix:
            parts.append(suffix if suffix.startswith("/") else f" {suffix}")
        if self.monthly_price:
            parts.append(f", lalu {formatting.rupiah(self.monthly_price)}/bulan")
        return "".join(parts)

    @property
    def price_compact(self) -> str:
        """Teks harga ringkas untuk tabel teknis. Contoh: Rp25.000/bln."""
        text = f"{self.price_prefix} " if self.price_prefix else ""
        text += formatting.rupiah(self.price)
        suffix = self.price_suffix.strip()
        if suffix.startswith("/"):
            text += suffix.replace("/bulan", "/bln")
        if self.monthly_price:
            text += f" + {formatting.rupiah(self.monthly_price)}/bln"
        return text



class PackageFeature(TwoLevelText):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="features")
    show_in_highlights = models.BooleanField(
        "tampilkan di bagian 'Yang bisa dilakukan'", default=False,
        help_text="Butuh ikon. Dipakai untuk kotak-kotak fitur di halaman utama.",
    )

    class Meta(TwoLevelText.Meta):
        db_table = "hp_package_feature"
        verbose_name = "isi paket"
        verbose_name_plural = "isi paket"


class PackageNote(TwoLevelText):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="notes")

    class Meta(TwoLevelText.Meta):
        db_table = "hp_package_note"
        verbose_name = "catatan paket"
        verbose_name_plural = "catatan paket"


class IncludedFeature(TwoLevelText):
    """'Termasuk di semua paket kasir'."""

    class Meta(TwoLevelText.Meta):
        db_table = "hp_included_feature"
        verbose_name = "keunggulan semua paket kasir"
        verbose_name_plural = "termasuk di semua paket kasir"


class AddOn(OrderedModel):
    GROUP_OUTLET = "outlet"
    GROUP_STORAGE = "storage"
    GROUPS = [(GROUP_OUTLET, "Tambah toko/cabang"), (GROUP_STORAGE, "Tambah tempat simpan")]

    group = models.CharField("kelompok", max_length=10, choices=GROUPS)
    name = models.CharField("nama", max_length=60, help_text="Contoh: +1 GB")
    price = models.PositiveIntegerField("harga (Rp)", validators=price_validators)
    unit = models.CharField("satuan", max_length=40, default="/bulan", help_text="Contoh: /toko/bulan")
    description = models.CharField("keterangan", max_length=200, blank=True)
    is_active = models.BooleanField("tampilkan", default=True)

    class Meta(OrderedModel.Meta):
        db_table = "hp_addon"
        verbose_name = "biaya tambahan"
        verbose_name_plural = "biaya tambahan"

    def __str__(self) -> str:
        return f"{self.get_group_display()}: {self.name}"


class ComparisonRow(OrderedModel):
    """Satu baris tabel detail teknis. Nilainya per kode paket (JSON)."""

    label = models.CharField("baris", max_length=60)
    values = models.JSONField("nilai per paket", default=dict, blank=True)
    is_active = models.BooleanField("tampilkan", default=True)

    class Meta(OrderedModel.Meta):
        db_table = "hp_comparison_row"
        verbose_name = "baris tabel teknis"
        verbose_name_plural = "tabel detail teknis"

    def __str__(self) -> str:
        return self.label


class Faq(OrderedModel):
    TOPIC_GENERAL = "umum"
    TOPICS = [
        (TOPIC_GENERAL, "Umum (halaman utama)"),
        ("kasir", "Aplikasi Kasir"),
        ("sim", "Sistem Informasi Manajemen (SIM)"),
        ("jasa", "Website & Aplikasi"),
    ]
    topic = models.CharField(
        "tampil di", max_length=10, choices=TOPICS, default=TOPIC_GENERAL,
        help_text="Umum = halaman utama. Lainnya = halaman solusi masing-masing.",
    )
    question = models.CharField("pertanyaan", max_length=200)
    answer = models.TextField(
        "jawaban", max_length=3000,
        help_text="Format sederhana: **tebal**, baris diawali '- ' untuk daftar, baris kosong untuk paragraf baru.",
    )
    is_active = models.BooleanField("tampilkan", default=True)

    class Meta(OrderedModel.Meta):
        db_table = "hp_faq"
        verbose_name = "FAQ"
        verbose_name_plural = "FAQ"

    def __str__(self) -> str:
        return self.question


class Testimonial(OrderedModel):
    name = models.CharField("nama", max_length=80)
    business = models.CharField("nama usaha", max_length=100, blank=True)
    location = models.CharField("kota/daerah", max_length=80, blank=True)
    quote = models.TextField("isi testimoni", max_length=600)
    photo = models.FileField("foto (opsional)", upload_to="uploads/testimoni/", blank=True)
    is_active = models.BooleanField(
        "tampilkan", default=False, help_text="Hanya testimoni asli dari pelanggan sungguhan."
    )

    class Meta(OrderedModel.Meta):
        db_table = "hp_testimonial"
        verbose_name = "testimoni"
        verbose_name_plural = "testimoni"

    def __str__(self) -> str:
        return f"{self.name} — {self.business}" if self.business else self.name


class LegalPage(models.Model):
    SLUG_TERMS = "syarat-ketentuan"
    SLUG_PRIVACY = "kebijakan-privasi"
    SLUGS = [(SLUG_TERMS, "Syarat & Ketentuan"), (SLUG_PRIVACY, "Kebijakan Privasi")]

    slug = models.SlugField("alamat", max_length=40, unique=True, choices=SLUGS)
    title = models.CharField("judul", max_length=100)
    body = models.TextField(
        "isi", max_length=30000,
        help_text="Format sederhana: '## Judul', '- poin', '**tebal**', [teks](https://...).",
    )
    is_draft = models.BooleanField(
        "masih draf", default=True, help_text="Bila aktif, halaman diberi tanda 'Draf — sedang ditinjau'."
    )
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    class Meta:
        db_table = "hp_legal_page"
        ordering = ["slug"]
        verbose_name = "halaman legal"
        verbose_name_plural = "halaman legal"

    def __str__(self) -> str:
        return self.title


class Announcement(models.Model):
    """Pengumuman untuk pelanggan, tampil di Dashboard akun (tidak bisa ditutup pelanggan)."""

    TONE_INFO = "info"
    TONE_IMPORTANT = "penting"
    TONE_PROMO = "promo"
    TONES = [(TONE_INFO, "Informasi"), (TONE_IMPORTANT, "Penting"), (TONE_PROMO, "Promo")]

    title = models.CharField("judul", max_length=100)
    body = models.TextField(
        "isi", max_length=2000, blank=True,
        help_text="Format sederhana: '**tebal**', '- poin', [teks](https://...).",
    )
    tone = models.CharField("jenis", max_length=10, choices=TONES, default=TONE_INFO)
    starts_at = models.DateTimeField("mulai tampil", default=timezone.now)
    ends_at = models.DateTimeField(
        "berhenti tampil", null=True, blank=True, help_text="Kosongkan bila tampil terus sampai dimatikan."
    )
    is_active = models.BooleanField(
        "aktif", default=True, help_text="Matikan untuk langsung menyembunyikan pengumuman ini."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hp_announcement"
        ordering = ["-starts_at"]
        verbose_name = "pengumuman"
        verbose_name_plural = "pengumuman pelanggan"

    def __str__(self) -> str:
        return self.title

    @classmethod
    def visible(cls, now=None):
        now = now or timezone.now()
        return cls.objects.filter(is_active=True, starts_at__lte=now).filter(
            models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)
        ).annotate(
            _rank=models.Case(
                models.When(tone="penting", then=0), models.When(tone="promo", then=1),
                default=2, output_field=models.IntegerField(),
            )
        ).order_by("_rank", "-starts_at")

    @property
    def schedule_text(self) -> str:
        from django.utils.formats import date_format

        start = date_format(timezone.localtime(self.starts_at), "j M Y H:i")
        end = date_format(timezone.localtime(self.ends_at), "j M Y H:i") if self.ends_at else "sampai dimatikan"
        return f"{start} – {end}"


# ---------------------------------------------------------------------------
# Data pendukung (tanpa data pribadi pengunjung)
# ---------------------------------------------------------------------------
class ContactClick(models.Model):
    """Jumlah klik tombol kontak (DM Instagram) per hari per tujuan. Tanpa IP, tanpa cookie."""

    date = models.DateField("tanggal", db_index=True)
    target = models.CharField("tujuan", max_length=40)
    count = models.PositiveIntegerField("jumlah", default=0)

    class Meta:
        db_table = "hp_contact_click"
        constraints = [models.UniqueConstraint(fields=["date", "target"], name="hp_contact_click_day_target")]
        ordering = ["-date", "target"]


class AuditLog(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_SECURITY = "security"
    ACTIONS = [
        (ACTION_CREATE, "Tambah"),
        (ACTION_UPDATE, "Ubah"),
        (ACTION_DELETE, "Hapus"),
        (ACTION_SECURITY, "Keamanan"),
    ]

    created_at = models.DateTimeField("waktu", auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    username = models.CharField("akun", max_length=150, blank=True)
    action = models.CharField("aksi", max_length=10, choices=ACTIONS)
    target_type = models.CharField("jenis data", max_length=60)
    target_repr = models.CharField("data", max_length=200)
    detail = models.CharField("rincian", max_length=500, blank=True)

    class Meta:
        db_table = "hp_audit_log"
        ordering = ["-created_at"]
        verbose_name = "riwayat perubahan"
        verbose_name_plural = "riwayat perubahan"

    def __str__(self) -> str:
        return f"{self.get_action_display()} {self.target_type}: {self.target_repr}"
