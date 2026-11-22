from __future__ import annotations

import re

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

from apps.content.models import Package
from apps.core.images import ImageRule, process_image

from . import services
from .models import (
    GENDERS,
    LEVEL_KECAMATAN,
    LEVEL_KELURAHAN,
    LEVEL_RT,
    LEVEL_RW,
    LEVELS,
    MARITAL,
    RELIGIONS,
    DokumenScan,
    JenisSurat,
    KartuKeluarga,
    Penduduk,
    Pengumuman,
    Wilayah,
)

SCAN = ImageRule(max_side=2600, output="WEBP", quality=90)  # KK/KTP: huruf kecil harus tetap terbaca
SIGNATURE = ImageRule(max_side=900, output="PNG")  # tanda tangan/cap: transparan & tajam
NIK_RE = re.compile(r"^\d{16}$")
NUMBER_RE = re.compile(r"^\d{1,3}$")


def scan_max_bytes() -> int:
    return getattr(settings, "SIM_SCAN_MAX_BYTES", 8 * 1024 * 1024)


def clean_upload(upload, rule: ImageRule, *, max_bytes: int | None = None):
    """Cek ukuran piksel SEBELUM gambar dibuka penuh, lalu proses ulang (aman) seperti upload lain."""
    limit = max_bytes or settings.UPLOAD_MAX_BYTES
    if upload.size > limit:
        raise ValidationError(f"Ukuran file maksimal {limit // (1024 * 1024)} MB.")
    upload.seek(0)
    try:
        with Image.open(upload) as probe:
            width, height = probe.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("File bukan gambar yang valid. Gunakan JPG, PNG, atau WebP.") from exc
    if width * height > 30_000_000:
        raise ValidationError("Resolusi gambar terlalu besar. Kecilkan foto lalu unggah lagi.")
    upload.seek(0)
    return process_image(upload, rule, max_bytes=limit)


def normalize_nik(value: str, *, required: bool) -> str:
    value = re.sub(r"\D", "", value or "")
    if not value:
        if required:
            raise ValidationError("NIK wajib diisi (16 angka).")
        return ""
    if not NIK_RE.match(value):
        raise ValidationError("NIK harus 16 angka.")
    return value


# ---------------------------------------------------------------------------
# Pesanan paket SIM (di /akun/pesan/<paket>/)
# ---------------------------------------------------------------------------
class SimOrderForm(forms.Form):
    tingkat = forms.ChoiceField(
        label="Jenis instansi", choices=LEVELS,
        help_text="Saat ini SIM tersedia untuk bidang pemerintahan & kemasyarakatan. Bidang lain (klinik, sekolah, organisasi) segera hadir.",
    )
    nomor = forms.CharField(label="Nomor RT/RW", max_length=3, required=False, help_text="Untuk RT/RW, mis. 5 atau 005.")
    nama = forms.CharField(label="Nama kelurahan/desa/kecamatan", max_length=80, required=False,
                           help_text="Untuk RT/RW boleh dikosongkan.")
    rw = forms.CharField(label="Nomor RW (untuk RT)", max_length=3, required=False)
    kelurahan = forms.CharField(label="Kelurahan/desa", max_length=80, required=False)
    kecamatan = forms.CharField(label="Kecamatan", max_length=80, required=False)
    kota = forms.CharField(label="Kabupaten/kota", max_length=80)
    provinsi = forms.CharField(label="Provinsi", max_length=80)

    def clean(self):
        cleaned = super().clean()
        level = cleaned.get("tingkat")
        for key in ("nomor", "rw"):
            value = (cleaned.get(key) or "").strip()
            if value and not NUMBER_RE.match(value):
                self.add_error(key, "Isi dengan angka (1–3 digit).")
            elif value:
                cleaned[key] = value.zfill(3)
        if level in (LEVEL_RT, LEVEL_RW) and not cleaned.get("nomor"):
            self.add_error("nomor", "Nomor RT/RW wajib diisi.")
        if level in (LEVEL_RT, LEVEL_RW) and not cleaned.get("kelurahan"):
            self.add_error("kelurahan", "Kelurahan/desa wajib diisi untuk RT/RW.")
        if level in (LEVEL_KELURAHAN, LEVEL_KECAMATAN) and not cleaned.get("nama"):
            self.add_error("nama", "Nama kelurahan/desa/kecamatan wajib diisi.")
        if level == LEVEL_KELURAHAN and not cleaned.get("kecamatan"):
            self.add_error("kecamatan", "Kecamatan wajib diisi.")
        return cleaned

    def details(self) -> dict:
        return {key: (self.cleaned_data.get(key) or "").strip() for key in services.ORDER_DETAIL_KEYS}


class RenewForm(forms.Form):
    package = forms.ModelChoiceField(label="Paket", queryset=Package.objects.none(), empty_label=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["package"].queryset = Package.objects.filter(category=Package.CATEGORY_SIM, is_active=True, price__gt=0)


# ---------------------------------------------------------------------------
# Pengaturan wilayah (kop surat, penanda tangan)
# ---------------------------------------------------------------------------
class WilayahSettingsForm(forms.ModelForm):
    ttd_upload = forms.FileField(label="Gambar tanda tangan (opsional)", required=False,
                                 help_text="Foto tanda tangan di kertas putih. Dipakai bila warga boleh mencetak sendiri.")
    cap_upload = forms.FileField(label="Gambar cap/stempel (opsional)", required=False)
    hapus_ttd = forms.BooleanField(label="Hapus gambar tanda tangan", required=False)
    hapus_cap = forms.BooleanField(label="Hapus gambar cap", required=False)

    class Meta:
        model = Wilayah
        fields = [
            "nomor", "nama", "rw", "kelurahan", "kecamatan", "kota", "provinsi", "alamat",
            "ketua_nama", "ketua_jabatan", "ketua_nip", "nomor_format", "terima_online", "warga_boleh_cetak",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        level = self.instance.level
        if level not in (LEVEL_RT, LEVEL_RW):
            del self.fields["nomor"]
        if level != LEVEL_RT:
            del self.fields["rw"]
        if level in (LEVEL_KELURAHAN,):
            del self.fields["kelurahan"]
        if level == LEVEL_KECAMATAN:
            del self.fields["kelurahan"]
            del self.fields["kecamatan"]
        self.fields["ketua_jabatan"].help_text = f"Kosongkan untuk memakai '{self.instance.signer_title}'."

    def clean_nomor(self):
        value = (self.cleaned_data.get("nomor") or "").strip()
        if not NUMBER_RE.match(value):
            raise ValidationError("Isi dengan angka (1–3 digit).")
        return value.zfill(3)

    def clean_rw(self):
        value = (self.cleaned_data.get("rw") or "").strip()
        if value and not NUMBER_RE.match(value):
            raise ValidationError("Isi dengan angka (1–3 digit).")
        return value.zfill(3) if value else ""

    def clean_ttd_upload(self):
        upload = self.cleaned_data.get("ttd_upload")
        return clean_upload(upload, SIGNATURE) if upload else None

    def clean_cap_upload(self):
        upload = self.cleaned_data.get("cap_upload")
        return clean_upload(upload, SIGNATURE) if upload else None

    def save(self, commit=True):
        wilayah = super().save(commit=False)
        old = {"ttd": wilayah.ttd.name if wilayah.ttd else "", "cap": wilayah.cap.name if wilayah.cap else ""}
        for field in ("ttd", "cap"):
            upload = self.cleaned_data.get(f"{field}_upload")
            if upload:
                getattr(wilayah, field).save(upload.name, upload, save=False)
            elif self.cleaned_data.get(f"hapus_{field}"):
                setattr(wilayah, field, "")
        wilayah.save()
        for field, name in old.items():
            current = getattr(wilayah, field)
            if name and name != (current.name if current else ""):
                Wilayah._meta.get_field(field).storage.delete(name)
        return wilayah


# ---------------------------------------------------------------------------
# Data warga
# ---------------------------------------------------------------------------
class KKForm(forms.ModelForm):
    class Meta:
        model = KartuKeluarga
        fields = ["no_kk", "kepala_nama", "alamat", "rt", "rw", "kode_pos", "status", "catatan"]
        widgets = {"catatan": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, wilayah: Wilayah, **kwargs):
        super().__init__(*args, **kwargs)
        self.wilayah = wilayah

    def clean_no_kk(self):
        value = re.sub(r"\D", "", self.cleaned_data.get("no_kk") or "")
        if value and not NIK_RE.match(value):
            raise ValidationError("Nomor KK harus 16 angka.")
        if value:
            dupe = KartuKeluarga.objects.filter(wilayah=self.wilayah, no_kk=value).exclude(pk=self.instance.pk)
            if dupe.exists():
                raise ValidationError("Nomor KK ini sudah ada di data wilayah Anda.")
        return value

    def clean_kepala_nama(self):
        return (self.cleaned_data.get("kepala_nama") or "").strip().upper()

    def save(self, commit=True):
        kk = super().save(commit=False)
        kk.wilayah = self.wilayah
        if commit:
            kk.save()
        return kk


class PendudukForm(forms.ModelForm):
    class Meta:
        model = Penduduk
        fields = [
            "nama", "nik", "jenis_kelamin", "tempat_lahir", "tanggal_lahir", "agama", "pendidikan", "pekerjaan",
            "status_perkawinan", "hubungan", "kewarganegaraan", "nama_ayah", "nama_ibu", "golongan_darah",
            "status", "status_tanggal", "status_keterangan", "urutan",
        ]
        widgets = {
            "tanggal_lahir": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "status_tanggal": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, kk: KartuKeluarga, **kwargs):
        super().__init__(*args, **kwargs)
        self.kk = kk

    def clean_nik(self):
        value = normalize_nik(self.cleaned_data.get("nik"), required=False)
        if value:
            dupe = Penduduk.objects.filter(wilayah=self.kk.wilayah, nik=value).exclude(pk=self.instance.pk)
            if dupe.exists():
                raise ValidationError("NIK ini sudah terdaftar di data wilayah Anda.")
        return value

    def clean_nama(self):
        return (self.cleaned_data.get("nama") or "").strip().upper()

    def save(self, commit=True):
        p = super().save(commit=False)
        p.kk = self.kk
        p.wilayah = self.kk.wilayah
        if commit:
            p.save()
        return p


class ScanUploadForm(forms.Form):
    jenis = forms.ChoiceField(label="Jenis dokumen", choices=DokumenScan.TYPES)
    judul = forms.CharField(label="Keterangan (opsional)", max_length=120, required=False,
                            help_text="Mis. KK Pak Budi, Blok C-12.")
    gambar = forms.FileField(label="Foto dokumen", help_text="Foto lurus dari atas, terang, tidak buram. JPG/PNG/WebP.")

    def clean_gambar(self):
        return clean_upload(self.cleaned_data["gambar"], SCAN, max_bytes=scan_max_bytes())


# ---------------------------------------------------------------------------
# Format surat
# ---------------------------------------------------------------------------
class JenisSuratForm(forms.ModelForm):
    kolom_text = forms.CharField(
        label="Kolom isian tambahan", required=False, widget=forms.Textarea(attrs={"rows": 5, "spellcheck": "false"}),
        help_text="Satu baris satu kolom: kunci | Label | wajib/opsional | teks/paragraf/tanggal. "
                  "Contoh: nama_usaha | Nama usaha | wajib | teks. Pakai {nama_usaha} di isi surat.",
    )

    class Meta:
        model = JenisSurat
        fields = ["nama", "judul", "kode_surat", "keterangan", "isi", "butuh_mengetahui", "online", "aktif", "urutan"]
        widgets = {"isi": forms.Textarea(attrs={"rows": 16, "spellcheck": "false"})}

    def __init__(self, *args, wilayah: Wilayah, **kwargs):
        super().__init__(*args, **kwargs)
        self.wilayah = wilayah
        self.fields["kolom_text"].initial = services.fields_to_text(self.instance.kolom if self.instance.pk else [])
        if not wilayah.parent_level:
            del self.fields["butuh_mengetahui"]

    def clean_kode_surat(self):
        value = (self.cleaned_data.get("kode_surat") or "").strip().upper()
        if value and not re.match(r"^[A-Z0-9.-]{1,12}$", value):
            raise ValidationError("Hanya huruf besar, angka, titik, atau tanda minus.")
        return value

    def clean_kolom_text(self):
        fields, errors = services.parse_fields_text(self.cleaned_data.get("kolom_text"))
        if errors:
            raise ValidationError(errors)
        return fields

    def save(self, commit=True):
        jenis = super().save(commit=False)
        jenis.wilayah = self.wilayah
        jenis.kolom = self.cleaned_data["kolom_text"]
        if not jenis.kode:
            base = re.sub(r"[^a-z0-9]+", "-", jenis.nama.lower()).strip("-")[:24] or "surat"
            kode, n = base, 1
            while JenisSurat.objects.filter(wilayah=self.wilayah, kode=kode).exists():
                n += 1
                kode = f"{base}-{n}"
            jenis.kode = kode
        if commit:
            jenis.save()
        return jenis


def surat_form_class(jenis: JenisSurat, *, public: bool):
    """Formulir surat sesuai format: isian standar + kolom tambahan milik jenis surat itu."""
    attrs: dict = {}
    attrs["nama"] = forms.CharField(label="Nama lengkap (sesuai KTP)", max_length=100)
    attrs["nik"] = forms.CharField(label="NIK", max_length=20, required=public, help_text="16 angka sesuai KTP/KK.")
    attrs["jenis_kelamin"] = forms.ChoiceField(label="Jenis kelamin", choices=[("", "—")] + GENDERS, required=public)
    attrs["tempat_lahir"] = forms.CharField(label="Tempat lahir", max_length=60, required=public)
    attrs["tanggal_lahir"] = forms.DateField(label="Tanggal lahir", required=public, widget=forms.DateInput(attrs={"type": "date"}))
    attrs["agama"] = forms.ChoiceField(label="Agama", choices=[("", "—")] + RELIGIONS, required=False)
    attrs["status_perkawinan"] = forms.ChoiceField(label="Status perkawinan", choices=[("", "—")] + MARITAL, required=False)
    attrs["pekerjaan"] = forms.CharField(label="Pekerjaan", max_length=60, required=False)
    attrs["kewarganegaraan"] = forms.CharField(label="Kewarganegaraan", max_length=10, initial="WNI", required=False)
    attrs["alamat"] = forms.CharField(label="Alamat lengkap", max_length=200, required=public,
                                      widget=forms.Textarea(attrs={"rows": 2}))
    attrs["keperluan"] = forms.CharField(label="Keperluan surat", max_length=200, required=public,
                                         help_text="Mis. melamar kerja, mendaftar sekolah, membuka rekening.")
    for spec in jenis.kolom or []:
        kind = spec.get("type", "teks")
        required = bool(spec.get("required", True))
        label = spec.get("label") or spec["key"]
        if kind == "tanggal":
            field = forms.DateField(label=label, required=required, widget=forms.DateInput(attrs={"type": "date"}))
        elif kind == "paragraf":
            field = forms.CharField(label=label, required=required, max_length=1500, widget=forms.Textarea(attrs={"rows": 3}))
        else:
            field = forms.CharField(label=label, required=required, max_length=200)
        attrs[f"x_{spec['key']}"] = field
    if public:
        attrs["kontak"] = forms.CharField(
            label="Nomor HP/email yang bisa dihubungi pengurus (opsional)", max_length=60, required=False,
        )
        attrs["setuju"] = forms.BooleanField(
            label="Saya menyatakan data di atas benar dan setuju data ini disimpan & diproses pengurus wilayah untuk membuat surat.",
        )
        # Umpan untuk robot: kolom tersembunyi yang harus tetap kosong.
        attrs["website"] = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def clean_nik(self):
        return normalize_nik(self.cleaned_data.get("nik"), required=public)

    def clean_nama(self):
        return (self.cleaned_data.get("nama") or "").strip().upper()

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError("Pengajuan ditolak.")
        return ""

    attrs["clean_nik"] = clean_nik
    attrs["clean_nama"] = clean_nama
    if public:
        attrs["clean_website"] = clean_website
    return type("SuratForm", (forms.Form,), attrs)


def surat_initial(surat) -> dict:
    data = dict(surat.data or {})
    initial = {"nama": surat.nama, "nik": surat.nik, "kontak": surat.kontak}
    for key, _ in services.STANDARD_FIELDS:
        if key not in ("nama", "nik"):
            initial[key] = data.get(key, "")
    for spec in (surat.jenis.kolom if surat.jenis else []) or []:
        initial[f"x_{spec['key']}"] = data.get(spec["key"], "")
    return initial


class RejectForm(forms.Form):
    alasan = forms.CharField(label="Alasan ditolak (dibaca pemohon)", max_length=500, widget=forms.Textarea(attrs={"rows": 2}))


class AckForm(forms.Form):
    catatan = forms.CharField(label="Catatan (opsional)", max_length=300, required=False)


class PengumumanForm(forms.ModelForm):
    class Meta:
        model = Pengumuman
        fields = ["judul", "isi", "teruskan", "mulai", "selesai", "aktif"]
        widgets = {
            "isi": forms.Textarea(attrs={"rows": 4}),
            "mulai": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "selesai": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, wilayah: Wilayah, **kwargs):
        super().__init__(*args, **kwargs)
        self.wilayah = wilayah
        if wilayah.level == LEVEL_RT:
            del self.fields["teruskan"]

    def save(self, commit=True):
        item = super().save(commit=False)
        item.wilayah = self.wilayah
        if commit:
            item.save()
        return item


class JoinForm(forms.Form):
    kode = forms.CharField(label="Kode undangan dari wilayah di atas Anda", max_length=12,
                           widget=forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false"}))


class LacakForm(forms.Form):
    kode = forms.CharField(label="Kode lacak surat", max_length=40)


class WilayahAdminForm(forms.ModelForm):
    """Panel: status langganan, masa aktif, paket, dan catatan untuk pengurus wilayah."""

    class Meta:
        model = Wilayah
        fields = ["status", "active_until", "package", "package_name", "admin_note", "terima_online"]
        widgets = {
            "active_until": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "admin_note": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "active_until": "Setelah tanggal ini: 7 hari masa tenggang, lalu terkunci (pengajuan online ditutup). "
                            "30 hari setelah tanggal ini data warga & surat dihapus permanen.",
            "admin_note": "Tampil di dashboard pengurus wilayah, mis. alasan ditangguhkan.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["package"].queryset = Package.objects.filter(category=Package.CATEGORY_SIM)
