"""Sistem Informasi Manajemen (SIM), bidang pemerintahan & kemasyarakatan: RT, RW, Kelurahan/Desa, Kecamatan.

Satu "instansi" di menu pelanggan = satu ``Wilayah`` di kode.

Susunannya:
- ``Wilayah``: satu unit (mis. RT 005). Dimiliki satu pelanggan (akun Google) dan punya
  langganan sendiri (paket, masa aktif). Wilayah terhubung ke wilayah di atasnya
  (RT -> RW -> Kelurahan -> Kecamatan) lewat kode undangan yang DISETUJUI wilayah atasnya.
- ``KartuKeluarga`` + ``Penduduk``: data warga. Hanya bisa dilihat pengurus wilayah itu
  sendiri. Wilayah di atasnya hanya melihat ANGKA rekap, bukan data pribadi.
- ``DokumenScan``: foto KK/KTP/dokumen kertas + teks hasil OCR (Tesseract lokal).
- ``JenisSurat``: format surat yang bisa diubah bebas oleh pengurus (isi, kolom isian).
- ``Surat``: surat yang diajukan warga secara online (tanpa login, memakai kode lacak)
  atau dibuat langsung oleh pengurus. Punya nomor otomatis dan QR keaslian.
- ``Pengumuman``: tampil di halaman warga; bisa diteruskan ke semua wilayah di bawahnya.

Semua data disimpan di tabel berawalan ``hp_sim_`` dan SEMUA query wajib disaring per
wilayah milik pengurus yang login (``Wilayah.objects.owned_by(member)``). Jangan pernah
mengambil Penduduk/Surat dengan ``pk`` saja.

File gambar (scan KK/KTP, tanda tangan, cap) disimpan di penyimpanan PRIBADI
(tanpa alamat publik) dan hanya disajikan lewat view yang memeriksa pemiliknya.
"""
from __future__ import annotations

import secrets
import string
from datetime import date, timedelta

from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.members.storage import private_storage
from apps.pos.models import (
    DELETE_AFTER_DAYS,
    GRACE_DAYS,
    STATE_ACTIVE,
    STATE_DELETED,
    STATE_GRACE,
    STATE_LABELS,
    STATE_LOCKED,
    STATE_SUSPENDED,
    STATE_TONES,
)

# ---------------------------------------------------------------------------
# Tingkat wilayah
# ---------------------------------------------------------------------------
LEVEL_RT = "rt"
LEVEL_RW = "rw"
LEVEL_KELURAHAN = "kelurahan"
LEVEL_KECAMATAN = "kecamatan"
LEVELS = [
    (LEVEL_RT, "RT (Rukun Tetangga)"),
    (LEVEL_RW, "RW (Rukun Warga)"),
    (LEVEL_KELURAHAN, "Kelurahan / Desa"),
    (LEVEL_KECAMATAN, "Kecamatan"),
]
LEVEL_ORDER = [LEVEL_RT, LEVEL_RW, LEVEL_KELURAHAN, LEVEL_KECAMATAN]
# Wilayah hanya bisa bergabung ke SATU tingkat tepat di atasnya.
PARENT_LEVEL = {LEVEL_RT: LEVEL_RW, LEVEL_RW: LEVEL_KELURAHAN, LEVEL_KELURAHAN: LEVEL_KECAMATAN}
DEFAULT_TITLES = {
    LEVEL_RT: "Ketua RT",
    LEVEL_RW: "Ketua RW",
    LEVEL_KELURAHAN: "Lurah",
    LEVEL_KECAMATAN: "Camat",
}

_CODE_ALPHABET = string.ascii_lowercase + string.digits
_JOIN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # tanpa 0/O/1/I agar mudah diketik


def new_public_code() -> str:
    """Alamat halaman warga: hansproject.app/w/<kode>/ (10 karakter acak)."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(10))


def new_join_code() -> str:
    """Kode undangan untuk wilayah di bawahnya (10 karakter, mudah dibacakan)."""
    return "".join(secrets.choice(_JOIN_ALPHABET) for _ in range(10))


def new_token() -> str:
    return secrets.token_urlsafe(18)


class WilayahQuerySet(models.QuerySet):
    def owned_by(self, member):
        return self.filter(owner=member)

    def not_deleted(self, today: date | None = None):
        today = today or timezone.localdate()
        return self.filter(active_until__gte=today - timedelta(days=DELETE_AFTER_DAYS))


class Wilayah(models.Model):
    STATUS_ACTIVE = "aktif"
    STATUS_SUSPENDED = "ditangguhkan"
    STATUSES = [(STATUS_ACTIVE, "Normal"), (STATUS_SUSPENDED, "Ditangguhkan admin")]

    owner = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="wilayah_set", verbose_name="pengurus (pemilik akun)"
    )
    level = models.CharField("tingkat", max_length=10, choices=LEVELS)
    nomor = models.CharField("nomor RT/RW", max_length=5, blank=True, help_text="Untuk RT/RW, mis. 005.")
    nama = models.CharField(
        "nama wilayah", max_length=80, blank=True,
        help_text="Untuk kelurahan/desa/kecamatan: namanya. Untuk RT/RW boleh dikosongkan atau diisi nama lingkungan.",
    )
    # Konteks alamat untuk kop surat (diisi pengurus, teks bebas).
    rw = models.CharField("RW", max_length=5, blank=True)
    kelurahan = models.CharField("kelurahan/desa", max_length=80, blank=True)
    kecamatan = models.CharField("kecamatan", max_length=80, blank=True)
    kota = models.CharField("kabupaten/kota", max_length=80, blank=True)
    provinsi = models.CharField("provinsi", max_length=80, blank=True)
    alamat = models.CharField("alamat sekretariat", max_length=200, blank=True)

    ketua_nama = models.CharField("nama ketua/pejabat", max_length=80, blank=True)
    ketua_jabatan = models.CharField("jabatan penanda tangan", max_length=60, blank=True)
    ketua_nip = models.CharField("NIP (bila ada)", max_length=30, blank=True)
    ttd = models.ImageField("gambar tanda tangan", storage=private_storage, upload_to="sim/ttd/", blank=True)
    cap = models.ImageField("gambar cap/stempel", storage=private_storage, upload_to="sim/cap/", blank=True)
    nomor_format = models.CharField(
        "format nomor surat", max_length=80, default="{nomor}/{kode_surat}/{wilayah}/{bulan_romawi}/{tahun}",
        help_text="Isian: {nomor} {kode_surat} {wilayah} {bulan} {bulan_romawi} {tahun}.",
    )

    kode = models.SlugField("kode halaman warga", max_length=12, unique=True, default=new_public_code, editable=False)
    terima_online = models.BooleanField(
        "terima pengajuan surat online", default=True,
        help_text="Warga bisa mengajukan surat lewat halaman wilayah tanpa login.",
    )
    warga_boleh_cetak = models.BooleanField(
        "warga boleh mencetak surat yang sudah terbit", default=False,
        help_text="Bila aktif, warga bisa membuka & mencetak surat dari halaman lacak (dengan tanda tangan & cap gambar bila ada).",
    )

    # Jaringan wilayah (RT -> RW -> Kelurahan -> Kecamatan)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children", verbose_name="wilayah di atasnya"
    )
    join_request = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="join_requests",
        verbose_name="minta bergabung ke", editable=False,
    )
    join_code = models.CharField("kode undangan", max_length=12, unique=True, default=new_join_code, editable=False)
    joined_at = models.DateTimeField("bergabung", null=True, blank=True, editable=False)

    # Langganan
    package = models.ForeignKey(
        "content.Package", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="paket"
    )
    package_name = models.CharField("nama paket", max_length=60, blank=True)
    status = models.CharField("status", max_length=14, choices=STATUSES, default=STATUS_ACTIVE)
    active_until = models.DateField("aktif sampai")
    admin_note = models.TextField("catatan untuk pengurus", blank=True, max_length=1000)
    created_at = models.DateTimeField("dibuat", auto_now_add=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    objects = WilayahQuerySet.as_manager()

    class Meta:
        db_table = "hp_sim_wilayah"
        ordering = ["created_at", "pk"]
        verbose_name = "wilayah SIM"
        verbose_name_plural = "wilayah SIM"

    def __str__(self) -> str:
        return self.label

    # --- Nama ---
    @property
    def level_label(self) -> str:
        return {LEVEL_RT: "RT", LEVEL_RW: "RW", LEVEL_KELURAHAN: "Kelurahan", LEVEL_KECAMATAN: "Kecamatan"}[self.level]

    @property
    def short_label(self) -> str:
        if self.level in (LEVEL_RT, LEVEL_RW):
            return f"{self.level_label} {self.nomor}".strip()
        return f"{self.level_label} {self.nama}".strip()

    @property
    def label(self) -> str:
        """Nama lengkap, mis. "RT 005 / RW 003, Kel. Sukamaju"."""
        parts = [self.short_label]
        if self.level == LEVEL_RT and self.rw:
            parts[0] += f" / RW {self.rw}"
        if self.level in (LEVEL_RT, LEVEL_RW) and self.kelurahan:
            parts.append(f"Kel. {self.kelurahan}")
        elif self.level == LEVEL_KELURAHAN and self.kecamatan:
            parts.append(f"Kec. {self.kecamatan}")
        return ", ".join(parts)

    @property
    def number_code(self) -> str:
        """Bagian {wilayah} pada nomor surat, mis. RT005/RW003."""
        if self.level == LEVEL_RT:
            return f"RT{self.nomor}" + (f"/RW{self.rw}" if self.rw else "")
        if self.level == LEVEL_RW:
            return f"RW{self.nomor}"
        return (self.nama or self.level_label).upper().replace(" ", "")[:20]

    @property
    def signer_title(self) -> str:
        return self.ketua_jabatan or f"{DEFAULT_TITLES[self.level]} {self.nomor if self.level in (LEVEL_RT, LEVEL_RW) else ''}".strip()

    @property
    def kop_lines(self) -> list[str]:
        """Baris kop surat (huruf besar), dari tingkat ini sampai kota."""
        lines = []
        if self.level == LEVEL_RT:
            first = f"RUKUN TETANGGA {self.nomor}"
            if self.rw:
                first += f" RUKUN WARGA {self.rw}"
            lines.append(first)
        elif self.level == LEVEL_RW:
            lines.append(f"RUKUN WARGA {self.nomor}")
        elif self.level == LEVEL_KELURAHAN:
            lines.append(f"PEMERINTAH {self.kota.upper()}" if self.kota else "PEMERINTAH KABUPATEN/KOTA")
            if self.kecamatan:
                lines.append(f"KECAMATAN {self.kecamatan.upper()}")
            lines.append(f"KELURAHAN {self.nama.upper()}")
            return lines
        else:
            lines.append(f"PEMERINTAH {self.kota.upper()}" if self.kota else "PEMERINTAH KABUPATEN/KOTA")
            lines.append(f"KECAMATAN {self.nama.upper()}")
            return lines
        place = []
        if self.kelurahan:
            place.append(f"KELURAHAN {self.kelurahan.upper()}")
        if self.kecamatan:
            place.append(f"KECAMATAN {self.kecamatan.upper()}")
        if place:
            lines.append(" ".join(place))
        if self.kota:
            lines.append(self.kota.upper())
        return lines

    @property
    def place_name(self) -> str:
        """Tempat penandatanganan surat (kota/kelurahan)."""
        return self.kelurahan or self.nama or self.kota or ""

    @property
    def public_path(self) -> str:
        return reverse("warga:wilayah", args=[self.kode])

    # --- Masa aktif (sama seperti aplikasi kasir) ---
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
        return self.active_until + timedelta(days=DELETE_AFTER_DAYS)

    @property
    def days_left(self) -> int:
        return (self.active_until - timezone.localdate()).days

    @property
    def can_edit(self) -> bool:
        """Data boleh diubah saat aktif atau masa tenggang."""
        return self.state() in (STATE_ACTIVE, STATE_GRACE)

    @property
    def serves_public(self) -> bool:
        """Halaman warga & pengajuan online hanya buka saat langganan aktif/tenggang."""
        return self.can_edit

    @property
    def parent_level(self) -> str | None:
        return PARENT_LEVEL.get(self.level)


class KartuKeluarga(models.Model):
    STATUS_ACTIVE = "aktif"
    STATUS_MOVED = "pindah"
    STATUSES = [(STATUS_ACTIVE, "Aktif"), (STATUS_MOVED, "Sudah pindah")]

    wilayah = models.ForeignKey(Wilayah, on_delete=models.CASCADE, related_name="kk_set")
    no_kk = models.CharField("nomor KK", max_length=16, blank=True, db_index=True)
    kepala_nama = models.CharField("nama kepala keluarga", max_length=100)
    alamat = models.CharField("alamat", max_length=200, blank=True)
    rt = models.CharField("RT", max_length=5, blank=True)
    rw = models.CharField("RW", max_length=5, blank=True)
    kode_pos = models.CharField("kode pos", max_length=5, blank=True)
    status = models.CharField("status", max_length=10, choices=STATUSES, default=STATUS_ACTIVE)
    catatan = models.TextField("catatan", blank=True, max_length=1000)
    created_at = models.DateTimeField("dibuat", auto_now_add=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    class Meta:
        db_table = "hp_sim_kk"
        ordering = ["kepala_nama", "pk"]
        verbose_name = "kartu keluarga"
        verbose_name_plural = "kartu keluarga"

    def __str__(self) -> str:
        return f"KK {self.no_kk or '-'} ({self.kepala_nama})"


GENDERS = [("L", "Laki-laki"), ("P", "Perempuan")]
RELIGIONS = [(x, x) for x in ("Islam", "Kristen", "Katolik", "Hindu", "Buddha", "Konghucu", "Kepercayaan")]
MARITAL = [(x, x) for x in ("Belum Kawin", "Kawin", "Cerai Hidup", "Cerai Mati")]
RELATIONS = [
    (x, x)
    for x in ("Kepala Keluarga", "Suami", "Istri", "Anak", "Menantu", "Cucu", "Orang Tua", "Mertua", "Famili Lain", "Pembantu", "Lainnya")
]


class Penduduk(models.Model):
    STATUS_ACTIVE = "aktif"
    STATUS_MOVED = "pindah"
    STATUS_DEAD = "meninggal"
    STATUSES = [(STATUS_ACTIVE, "Aktif"), (STATUS_MOVED, "Pindah"), (STATUS_DEAD, "Meninggal")]

    wilayah = models.ForeignKey(Wilayah, on_delete=models.CASCADE, related_name="penduduk_set")
    kk = models.ForeignKey(KartuKeluarga, on_delete=models.CASCADE, related_name="anggota", verbose_name="KK")
    nik = models.CharField("NIK", max_length=16, blank=True, db_index=True)
    nama = models.CharField("nama lengkap", max_length=100)
    jenis_kelamin = models.CharField("jenis kelamin", max_length=1, choices=GENDERS, blank=True)
    tempat_lahir = models.CharField("tempat lahir", max_length=60, blank=True)
    tanggal_lahir = models.DateField("tanggal lahir", null=True, blank=True)
    agama = models.CharField("agama", max_length=20, choices=RELIGIONS, blank=True)
    pendidikan = models.CharField("pendidikan", max_length=60, blank=True)
    pekerjaan = models.CharField("pekerjaan", max_length=60, blank=True)
    status_perkawinan = models.CharField("status perkawinan", max_length=20, choices=MARITAL, blank=True)
    hubungan = models.CharField("hubungan dalam keluarga", max_length=20, choices=RELATIONS, blank=True)
    kewarganegaraan = models.CharField("kewarganegaraan", max_length=10, default="WNI")
    nama_ayah = models.CharField("nama ayah", max_length=100, blank=True)
    nama_ibu = models.CharField("nama ibu", max_length=100, blank=True)
    golongan_darah = models.CharField("golongan darah", max_length=3, blank=True)
    status = models.CharField("status", max_length=10, choices=STATUSES, default=STATUS_ACTIVE)
    status_tanggal = models.DateField("tanggal pindah/meninggal", null=True, blank=True)
    status_keterangan = models.CharField("keterangan status", max_length=200, blank=True)
    urutan = models.PositiveSmallIntegerField("urutan di KK", default=0)
    created_at = models.DateTimeField("dibuat", auto_now_add=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    class Meta:
        db_table = "hp_sim_penduduk"
        ordering = ["urutan", "pk"]
        verbose_name = "penduduk"
        verbose_name_plural = "penduduk"

    def __str__(self) -> str:
        return self.nama

    @property
    def umur(self) -> int | None:
        if not self.tanggal_lahir:
            return None
        today = timezone.localdate()
        born = self.tanggal_lahir
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    @property
    def nik_masked(self) -> str:
        return mask_nik(self.nik)


def mask_nik(nik: str) -> str:
    """3273xxxxxxxx0001: yang tampil hanya 4 digit awal & akhir."""
    nik = nik or ""
    if len(nik) <= 8:
        return "•" * len(nik)
    return nik[:4] + "•" * (len(nik) - 8) + nik[-4:]


def mask_name(name: str) -> str:
    """Budi Santoso -> B*** S******."""
    return " ".join(w[0] + "*" * (len(w) - 1) for w in (name or "").split() if w)


class DokumenScan(models.Model):
    TYPE_KK = "kk"
    TYPE_KTP = "ktp"
    TYPE_OTHER = "lain"
    TYPES = [(TYPE_KK, "Kartu Keluarga"), (TYPE_KTP, "KTP"), (TYPE_OTHER, "Dokumen lain")]

    OCR_PENDING = "menunggu"
    OCR_DONE = "selesai"
    OCR_FAILED = "gagal"
    OCR_UNAVAILABLE = "tidak-tersedia"
    OCR_STATUSES = [
        (OCR_PENDING, "Belum dibaca"),
        (OCR_DONE, "Teks terbaca"),
        (OCR_FAILED, "Gagal dibaca"),
        (OCR_UNAVAILABLE, "Mesin OCR belum terpasang"),
    ]

    wilayah = models.ForeignKey(Wilayah, on_delete=models.CASCADE, related_name="scan_set")
    jenis = models.CharField("jenis dokumen", max_length=6, choices=TYPES, default=TYPE_KK)
    judul = models.CharField("judul/keterangan", max_length=120, blank=True)
    gambar = models.ImageField("gambar", storage=private_storage, upload_to="sim/scan/%Y/%m/")
    teks = models.TextField("teks hasil baca (OCR)", blank=True)
    hasil = models.JSONField("data terstruktur", default=dict, blank=True)
    ocr_status = models.CharField("status baca", max_length=16, choices=OCR_STATUSES, default=OCR_PENDING)
    ocr_pesan = models.CharField("pesan", max_length=200, blank=True)
    kk = models.ForeignKey(
        KartuKeluarga, null=True, blank=True, on_delete=models.SET_NULL, related_name="scan_set", verbose_name="KK terkait"
    )
    penduduk = models.ForeignKey(
        Penduduk, null=True, blank=True, on_delete=models.SET_NULL, related_name="scan_set", verbose_name="penduduk terkait"
    )
    created_at = models.DateTimeField("diunggah", auto_now_add=True)

    class Meta:
        db_table = "hp_sim_scan"
        ordering = ["-created_at", "-pk"]
        verbose_name = "dokumen scan"
        verbose_name_plural = "dokumen scan"

    def __str__(self) -> str:
        return self.judul or f"{self.get_jenis_display()} #{self.pk}"


class JenisSurat(models.Model):
    """Format surat milik satu wilayah. Isi & kolom isian bebas diubah pengurus."""

    wilayah = models.ForeignKey(Wilayah, on_delete=models.CASCADE, related_name="jenis_surat")
    kode = models.SlugField("kode", max_length=30)
    nama = models.CharField("nama surat", max_length=80)
    judul = models.CharField("judul di surat", max_length=120, help_text="Mis. SURAT KETERANGAN DOMISILI")
    kode_surat = models.CharField("kode di nomor surat", max_length=12, blank=True, help_text="Mis. DOM, SKTM")
    keterangan = models.CharField("penjelasan untuk warga", max_length=200, blank=True)
    isi = models.TextField(
        "isi surat", max_length=8000,
        help_text="Gunakan {isian}, mis. {nama}, {nik}, {keperluan}. Baris 'Label : {isian}' otomatis dirapikan menjadi tabel.",
    )
    kolom = models.JSONField("kolom isian tambahan", default=list, blank=True)
    butuh_mengetahui = models.BooleanField(
        "perlu diketahui wilayah di atasnya", default=False,
        help_text="Mis. surat pengantar RT yang perlu diketahui Ketua RW. Muncul di kotak masuk wilayah atasnya.",
    )
    online = models.BooleanField("bisa diajukan warga online", default=True)
    aktif = models.BooleanField("aktif", default=True)
    urutan = models.PositiveSmallIntegerField("urutan", default=0)
    created_at = models.DateTimeField("dibuat", auto_now_add=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)

    class Meta:
        db_table = "hp_sim_jenis_surat"
        ordering = ["urutan", "nama", "pk"]
        constraints = [models.UniqueConstraint(fields=["wilayah", "kode"], name="hp_sim_jenis_surat_kode_unik")]
        verbose_name = "jenis surat"
        verbose_name_plural = "jenis surat"

    def __str__(self) -> str:
        return self.nama


class Surat(models.Model):
    STATUS_SUBMITTED = "diajukan"
    STATUS_ISSUED = "terbit"
    STATUS_REJECTED = "ditolak"
    STATUS_CANCELLED = "dibatalkan"
    STATUSES = [
        (STATUS_SUBMITTED, "Menunggu diproses"),
        (STATUS_ISSUED, "Sudah terbit"),
        (STATUS_REJECTED, "Ditolak"),
        (STATUS_CANCELLED, "Dibatalkan"),
    ]
    SOURCE_ONLINE = "online"
    SOURCE_DIRECT = "langsung"
    SOURCES = [(SOURCE_ONLINE, "Diajukan warga online"), (SOURCE_DIRECT, "Dibuat pengurus")]

    ACK_NONE = ""
    ACK_WAITING = "menunggu"
    ACK_DONE = "diketahui"
    ACK_REJECTED = "ditolak"
    ACK_STATUSES = [
        (ACK_NONE, "Tidak perlu"),
        (ACK_WAITING, "Menunggu diketahui"),
        (ACK_DONE, "Sudah diketahui"),
        (ACK_REJECTED, "Ditolak wilayah atas"),
    ]

    wilayah = models.ForeignKey(Wilayah, on_delete=models.CASCADE, related_name="surat_set")
    jenis = models.ForeignKey(JenisSurat, null=True, blank=True, on_delete=models.SET_NULL, related_name="surat_set")
    jenis_nama = models.CharField("jenis surat", max_length=80)
    judul = models.CharField("judul surat", max_length=120)
    penduduk = models.ForeignKey(
        Penduduk, null=True, blank=True, on_delete=models.SET_NULL, related_name="surat_set", verbose_name="penduduk terkait"
    )
    nama = models.CharField("nama pemohon", max_length=100)
    nik = models.CharField("NIK pemohon", max_length=16, blank=True)
    data = models.JSONField("isian", default=dict, blank=True)
    isi = models.TextField("isi surat (setelah terbit)", blank=True, max_length=12000)
    kontak = models.CharField("kontak pemohon", max_length=60, blank=True)
    status = models.CharField("status", max_length=12, choices=STATUSES, default=STATUS_SUBMITTED, db_index=True)
    sumber = models.CharField("sumber", max_length=10, choices=SOURCES, default=SOURCE_ONLINE)
    nomor = models.CharField("nomor surat", max_length=80, blank=True)
    nomor_urut = models.PositiveIntegerField("nomor urut", null=True, blank=True)
    tahun = models.PositiveSmallIntegerField("tahun", null=True, blank=True)
    tanggal = models.DateField("tanggal surat", null=True, blank=True)
    penanda_tangan = models.CharField("penanda tangan", max_length=80, blank=True)
    jabatan = models.CharField("jabatan penanda tangan", max_length=60, blank=True)
    catatan_pengurus = models.TextField("catatan untuk pemohon", blank=True, max_length=1000)
    # Mengetahui (wilayah di atasnya)
    mengetahui = models.CharField("mengetahui", max_length=10, choices=ACK_STATUSES, default=ACK_NONE, blank=True)
    mengetahui_wilayah = models.ForeignKey(
        Wilayah, null=True, blank=True, on_delete=models.SET_NULL, related_name="surat_diketahui", verbose_name="diketahui oleh"
    )
    mengetahui_nama = models.CharField("nama yang mengetahui", max_length=80, blank=True)
    mengetahui_jabatan = models.CharField("jabatan yang mengetahui", max_length=60, blank=True)
    mengetahui_at = models.DateTimeField("diketahui pada", null=True, blank=True)
    mengetahui_catatan = models.CharField("catatan wilayah atas", max_length=300, blank=True)

    lacak_token = models.CharField("kode lacak", max_length=32, unique=True, default=new_token, editable=False)
    verify_token = models.CharField("kode keaslian", max_length=32, unique=True, default=new_token, editable=False)
    ip_hash = models.CharField(max_length=32, blank=True, editable=False)
    created_at = models.DateTimeField("diajukan", auto_now_add=True)
    updated_at = models.DateTimeField("diperbarui", auto_now=True)
    issued_at = models.DateTimeField("terbit", null=True, blank=True)

    class Meta:
        db_table = "hp_sim_surat"
        ordering = ["-created_at", "-pk"]
        verbose_name = "surat"
        verbose_name_plural = "surat"

    def __str__(self) -> str:
        return f"{self.jenis_nama} — {self.nama}"

    @property
    def is_issued(self) -> bool:
        return self.status == self.STATUS_ISSUED

    @property
    def status_tone(self) -> str:
        return {self.STATUS_ISSUED: "ok", self.STATUS_SUBMITTED: "wait"}.get(self.status, "off")

    @property
    def lacak_path(self) -> str:
        return reverse("warga:lacak", args=[self.lacak_token])

    @property
    def verify_path(self) -> str:
        return reverse("warga:cek", args=[self.verify_token])

    @property
    def nama_masked(self) -> str:
        return mask_name(self.nama)

    @property
    def nik_masked(self) -> str:
        return mask_nik(self.nik)


class Pengumuman(models.Model):
    wilayah = models.ForeignKey(Wilayah, on_delete=models.CASCADE, related_name="pengumuman_set")
    judul = models.CharField("judul", max_length=120)
    isi = models.TextField("isi", max_length=2000)
    teruskan = models.BooleanField(
        "tampilkan juga di semua wilayah di bawah", default=False,
        help_text="Mis. pengumuman kelurahan tampil di halaman warga semua RW & RT yang tergabung.",
    )
    mulai = models.DateField("tampil mulai", null=True, blank=True)
    selesai = models.DateField("tampil sampai", null=True, blank=True)
    aktif = models.BooleanField("aktif", default=True)
    created_at = models.DateTimeField("dibuat", auto_now_add=True)

    class Meta:
        db_table = "hp_sim_pengumuman"
        ordering = ["-created_at", "-pk"]
        verbose_name = "pengumuman wilayah"
        verbose_name_plural = "pengumuman wilayah"

    def __str__(self) -> str:
        return self.judul

    def is_showing(self, today: date | None = None) -> bool:
        today = today or timezone.localdate()
        return self.aktif and (not self.mulai or self.mulai <= today) and (not self.selesai or today <= self.selesai)
