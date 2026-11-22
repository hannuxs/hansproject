"""Daftar menu & jenis data yang bisa dikelola di panel.

Untuk menambah jenis data baru: buat model + form, lalu tambahkan satu
``Section`` di bawah. Halaman daftar/tambah/ubah/hapus otomatis tersedia.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from apps.content.models import (
    AddOn,
    Announcement,
    BankAccount,
    ComparisonRow,
    Faq,
    IncludedFeature,
    LegalPage,
    Package,
    SiteSettings,
    Testimonial,
)

from apps.members.models import Member, Order, Refund
from apps.pos.forms import StoreAdminForm
from apps.pos.models import Store
from apps.sim.forms import WilayahAdminForm
from apps.sim.models import Wilayah

from . import forms
from .crud import Column, InlineSpec, Section

PACKAGES = Section(
    key="paket",
    model=Package,
    form_class=forms.PackageForm,
    title="Paket & Harga",
    singular="paket",
    icon="tag",
    description=(
        "Harga, label, dan isi setiap paket. Aplikasi Kasir dan SIM masing-masing punya Paket Tunas & Tumbuh; "
        "Paket Rimba untuk jasa website & aplikasi. Harga langganan Rp0 = tampil \"Segera diumumkan\" dan belum bisa "
        "dipesan. Perubahan langsung tampil di website."
    ),
    columns=[
        Column("product_short", "Solusi"),
        Column("name", "Paket"),
        Column("price", "Harga", "money"),
        Column("price_suffix", "Keterangan", "muted"),
        Column("is_highlighted", "Ditonjolkan", "bool"),
        Column("is_active", "Tampil", "bool"),
    ],
    fieldsets=[
        ("Identitas paket", ["name", "code", "category", "icon", "tagline", "description"]),
        ("Harga & batas", ["price_prefix", "price", "price_suffix", "monthly_price", "outlet_count", "scan_limit"]),
        ("Tampilan", ["badge", "is_highlighted", "includes_from", "order", "is_active"]),
    ],
    inlines=[
        InlineSpec(
            "fitur", "Isi paket", forms.PackageFeatureFormSet,
            help="Setiap poin punya versi sederhana (untuk orang awam) dan versi teknis (pelengkap).",
        ),
        InlineSpec(
            "catatan", "Catatan penting", forms.PackageNoteFormSet,
            help="Catatan yang wajib dibaca calon pelanggan (misalnya biaya Play Store ditanggung klien).",
        ),
    ],
    queryset=lambda: Package.objects.select_related("includes_from").order_by("category", "order", "pk"),
)

ADDONS = Section(
    key="tambahan",
    model=AddOn,
    form_class=forms.AddOnForm,
    title="Biaya Tambahan",
    singular="biaya tambahan",
    icon="plus",
    description="Aplikasi Kasir: tambah toko/cabang dan tambah tempat simpan.",
    columns=[
        Column("get_group_display", "Kelompok", "muted"),
        Column("name", "Nama"),
        Column("price", "Harga", "money"),
        Column("unit", "Satuan", "muted"),
        Column("is_active", "Tampil", "bool"),
    ],
)

INCLUDED = Section(
    key="termasuk",
    model=IncludedFeature,
    form_class=forms.IncludedFeatureForm,
    title="Termasuk di Semua Paket",
    singular="poin",
    icon="check",
    description="Keunggulan yang dimiliki semua paket Aplikasi Kasir (tampil di halaman Aplikasi Kasir).",
    columns=[Column("simple", "Versi sederhana"), Column("technical", "Versi teknis", "muted")],
)

COMPARISON = Section(
    key="tabel-teknis",
    model=ComparisonRow,
    form_class=forms.ComparisonRowForm,
    title="Tabel Detail Teknis",
    singular="baris tabel",
    icon="list",
    description="Tabel perbandingan untuk pembaca yang paham teknologi. Baris 'Harga' dibuat otomatis dari data paket.",
    columns=[Column("label", "Baris"), Column("is_active", "Tampil", "bool")],
)

FAQ = Section(
    key="faq",
    model=Faq,
    form_class=forms.FaqForm,
    title="Pertanyaan (FAQ)",
    singular="pertanyaan",
    icon="help",
    description="Umum = halaman utama. Pertanyaan khusus satu solusi tampil di halaman solusinya (Kasir, SIM, Website & Aplikasi).",
    columns=[Column("question", "Pertanyaan"), Column("get_topic_display", "Tampil di", "muted"), Column("is_active", "Tampil", "bool")],
)

TESTIMONIALS = Section(
    key="testimoni",
    model=Testimonial,
    form_class=forms.TestimonialForm,
    title="Testimoni",
    singular="testimoni",
    icon="star",
    description=(
        "Hanya isi dengan testimoni asli dari pelanggan sungguhan. Bagian ini baru tampil di website bila "
        "'Tampilkan bagian testimoni' dinyalakan di Pengaturan Umum."
    ),
    columns=[Column("name", "Nama"), Column("business", "Usaha", "muted"), Column("is_active", "Tampil", "bool")],
)

LEGAL = Section(
    key="legal",
    model=LegalPage,
    form_class=forms.LegalPageForm,
    title="Halaman Legal",
    singular="halaman",
    icon="file",
    description="Syarat & Ketentuan dan Kebijakan Privasi. Masih draf: tinjau sebelum dipakai resmi.",
    columns=[Column("title", "Judul"), Column("is_draft", "Masih draf", "bool"), Column("updated_at", "Diperbarui", "muted")],
    can_create=False,
    can_delete=False,
    orderable=False,
)

SETTINGS = Section(
    key="pengaturan",
    model=SiteSettings,
    form_class=forms.SiteSettingsForm,
    title="Pengaturan Umum",
    singular="pengaturan",
    icon="settings",
    description="Kontak (DM Instagram, email), jam layanan, pembayaran, teks utama, dan SEO.",
    columns=[],
    singleton=True,
    nav_group="Pengaturan",
    fieldsets=[
        ("Kontak & media sosial", ["instagram_username", "email", "support_hours", "facebook_url", "tiktok_url", "youtube_url"]),
        ("Pembayaran", ["show_payment_info", "qris_image"]),
        ("Halaman utama", ["hero_title", "hero_subtitle", "announcement_active", "announcement_text", "show_testimonials"]),
        ("Pencarian Google (SEO)", ["seo_title", "seo_description"]),
        ("Syarat & Ketentuan / Kebijakan Privasi", ["legal_version"]),
    ],
    inlines=[
        InlineSpec(
            "rekening", "Rekening bank", forms.BankAccountFormSet, inline=False,
            queryset=lambda: BankAccount.objects.all(),
            help="Rekening tujuan transfer. Ditampilkan di website hanya bila 'tampilkan info rekening' aktif.",
        )
    ],
)

ORDERS = Section(
    key="pesanan",
    model=Order,
    form_class=forms.OrderAdminForm,
    title="Pesanan",
    singular="pesanan",
    icon="cart",
    description=(
        "Pesanan dari tombol Pesan Sekarang. Cek bukti bayar, lalu ubah statusnya. "
        "Status & catatan langsung terlihat oleh pelanggan di halaman akunnya."
    ),
    columns=[
        Column("code", "Kode"),
        Column("customer_name", "Pelanggan"),
        Column("title", "Pesanan"),
        Column("subject_label", "Untuk", "muted"),
        Column("get_status_display", "Status"),
        Column("created_at", "Dipesan", "muted"),
    ],
    inlines=[
        InlineSpec(
            "rincian", "Rincian harga", forms.OrderItemFormSet,
            help=(
                "Opsional, terutama untuk Paket Rimba. Bila diisi, rincian ini menggantikan teks harga paket di halaman "
                "pesanan, dan Total Semua (yang dibayar pelanggan) = jumlah semua rincian. Periode diketik bebas, "
                "kosongkan bila sekali bayar. Contoh: Pembuatan website Rp349.000 (periode kosong), "
                "Domain .com Rp250.000 (1 tahun), Database Rp150.000 (3 bulan). Baris tampil sesuai urutan diisi."
            ),
        )
    ],
    can_create=False,
    can_delete=False,
    orderable=False,
    nav_group="Pelanggan",
    detail_template="panel/members/order_detail.html",
    queryset=lambda: Order.objects.select_related("member", "store", "wilayah"),
)

REFUNDS = Section(
    key="refund",
    model=Refund,
    form_class=forms.RefundAdminForm,
    title="Refund",
    singular="refund",
    icon="wallet",
    description=(
        "Pengajuan pengembalian dana dari pesanan yang sudah dibayar lalu dibatalkan. Transfer ke rekening "
        "pelanggan, unggah bukti transfernya, lalu ubah status menjadi Sudah ditransfer."
    ),
    columns=[
        Column("order.code", "Pesanan"),
        Column("order.customer_name", "Pelanggan"),
        Column("amount", "Nominal", "money"),
        Column("get_status_display", "Status"),
        Column("created_at", "Diajukan", "muted"),
    ],
    can_create=False,
    can_delete=False,
    orderable=False,
    nav_group="Pelanggan",
    detail_template="panel/members/refund_detail.html",
    queryset=lambda: Refund.objects.select_related("order", "order__member"),
)


@dataclass
class CustomPage:
    """Halaman panel khusus (bukan CRUD generik) yang tetap tampil di menu samping."""

    key: str
    title: str
    icon: str
    url_name: str
    nav_group: str

    def urls(self) -> list:
        return []

    @property
    def nav_url(self) -> str:
        return reverse(self.url_name)


CHATS = CustomPage("chat", "Chat Pelanggan", "chat", "panel:chat-list", "Pelanggan")

ANNOUNCEMENTS = Section(
    key="pengumuman",
    model=Announcement,
    form_class=forms.AnnouncementForm,
    title="Pengumuman Pelanggan",
    singular="pengumuman",
    icon="info",
    description=(
        "Tampil di Dashboard akun pelanggan sesuai jadwal. Pelanggan tidak bisa menutupnya. "
        "Matikan 'aktif' untuk menyembunyikan seketika."
    ),
    columns=[
        Column("title", "Judul"),
        Column("get_tone_display", "Jenis", "muted"),
        Column("schedule_text", "Jadwal", "muted"),
        Column("is_active", "Aktif", "bool"),
    ],
    orderable=False,
    nav_group="Pelanggan",
)

MEMBERS = Section(
    key="pelanggan",
    model=Member,
    form_class=forms.MemberAdminForm,
    title="Daftar Pelanggan",
    singular="pelanggan",
    icon="user",
    description=(
        "Akun yang masuk dengan Google. Menghapus pelanggan (misalnya atas permintaannya) juga menghapus "
        "pertanyaan, pesanan yang belum dibayar, dan TOKO beserta seluruh transaksinya. Pesanan yang sudah dibayar "
        "beserta bukti bayarnya tetap disimpan 10 tahun untuk catatan pajak, lalu dihapus otomatis."
    ),
    columns=[
        Column("display_name", "Nama"),
        Column("business_name", "Usaha", "muted"),
        Column("email", "Email", "muted"),
        Column("is_active", "Aktif", "bool"),
        Column("created_at", "Terdaftar", "muted"),
    ],
    can_create=False,
    orderable=False,
    nav_group="Pelanggan",
    detail_template="panel/members/member_detail.html",
)

STORES = Section(
    key="toko",
    model=Store,
    form_class=StoreAdminForm,
    title="Toko · Aplikasi Kasir",
    singular="toko",
    icon="store",
    description=(
        "Satu toko = satu subdomain = satu akun kasir. Toko pertama dibuat otomatis saat pesanan kasir diubah menjadi Aktif; "
        "toko berikutnya dibuat pelanggan sendiri dari sisa kuota paketnya. Paket, kuota, dan masa aktif disimpan per "
        "langganan (berlaku untuk semua toko di langganan itu)."
    ),
    columns=[
        Column("name", "Toko"),
        Column("host", "Alamat", "muted"),
        Column("owner.display_name", "Pemilik", "muted"),
        Column("package_name", "Paket"),
        Column("active_until", "Aktif sampai"),
        Column("state_label", "Keadaan"),
    ],
    can_create=False,
    orderable=False,
    nav_group="Layanan",
    detail_template="panel/pos/store_detail.html",
    queryset=lambda: Store.objects.select_related("owner", "subscription").order_by("subscription__active_until", "pk"),
)

WILAYAH = Section(
    key="wilayah",
    model=Wilayah,
    form_class=WilayahAdminForm,
    title="Instansi · SIM",
    singular="instansi",
    icon="database",
    description=(
        "Sistem Informasi Manajemen (SIM). Satu instansi = satu RT/RW/kelurahan/kecamatan dengan data warga, format surat, "
        "dan halaman warga sendiri. Dibuat otomatis saat pesanan paket SIM diubah menjadi Aktif. Data warga TIDAK "
        "ditampilkan di panel; di sini hanya status langganan dan masa aktif."
    ),
    columns=[
        Column("label", "Instansi"),
        Column("owner.display_name", "Pengurus", "muted"),
        Column("package_name", "Paket"),
        Column("active_until", "Aktif sampai"),
        Column("state_label", "Keadaan"),
    ],
    can_create=False,
    orderable=False,
    nav_group="Layanan",
    queryset=lambda: Wilayah.objects.select_related("owner").order_by("active_until", "pk"),
)

SECTIONS = [
    PACKAGES, ADDONS, INCLUDED, COMPARISON, FAQ, TESTIMONIALS, LEGAL,
    ORDERS, REFUNDS, STORES, WILAYAH, CHATS, ANNOUNCEMENTS, MEMBERS, SETTINGS,
]


@dataclass
class NavItem:
    key: str
    label: str
    icon: str
    url: str


def nav_groups() -> list[tuple[str, list[NavItem]]]:
    groups: dict[str, list[NavItem]] = {
        "Ringkasan": [NavItem("dashboard", "Beranda Panel", "home", reverse("panel:dashboard"))]
    }
    for s in SECTIONS:
        groups.setdefault(s.nav_group, []).append(NavItem(s.key, s.title, s.icon, s.nav_url))
    groups.setdefault("Pengaturan", []).extend(
        [
            NavItem("akun", "Keamanan Akun", "lock", reverse("panel:account")),
            NavItem("riwayat", "Riwayat Perubahan", "history", reverse("panel:audit")),
        ]
    )
    return list(groups.items())
