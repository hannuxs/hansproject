"""Aturan bisnis SIM (bidang pemerintahan & kemasyarakatan): aktivasi paket, surat, nomor, jaringan wilayah, statistik.

View hanya memanggil fungsi di sini supaya aturan ada di satu tempat dan mudah diuji.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from apps.content import templating
from apps.pos.models import STATE_DELETED, add_months

from . import defaults
from .models import (
    LEVEL_ORDER,
    LEVEL_RT,
    LEVELS,
    PARENT_LEVEL,
    JenisSurat,
    KartuKeluarga,
    Penduduk,
    Pengumuman,
    Surat,
    Wilayah,
)

log = logging.getLogger("hans")

MAX_KK_PER_WILAYAH = 20000
MAX_SCANS_PER_DAY = 200
MAX_JENIS_SURAT = 60
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
MONTHS = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

# Isian standar di formulir surat (selalu ada). Kunci = nama {isian}.
STANDARD_FIELDS = [
    ("nama", "Nama lengkap"),
    ("nik", "NIK"),
    ("jenis_kelamin", "Jenis kelamin"),
    ("tempat_lahir", "Tempat lahir"),
    ("tanggal_lahir", "Tanggal lahir"),
    ("agama", "Agama"),
    ("status_perkawinan", "Status perkawinan"),
    ("pekerjaan", "Pekerjaan"),
    ("kewarganegaraan", "Kewarganegaraan"),
    ("alamat", "Alamat"),
    ("keperluan", "Keperluan"),
]
STANDARD_KEYS = {key for key, _ in STANDARD_FIELDS}
AUTO_KEYS = {"nama_wilayah", "jabatan", "penanda_tangan", "tanggal_surat", "tempat_surat", "nomor_surat"}
FIELD_TYPES = {"teks", "paragraf", "tanggal"}
FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,29}$")


def format_date(value: date | None) -> str:
    if not value:
        return ""
    return f"{value.day} {MONTHS[value.month]} {value.year}"


# ---------------------------------------------------------------------------
# Aktivasi pesanan paket SIM (dipanggil saat admin mengubah status pesanan menjadi Aktif)
# ---------------------------------------------------------------------------
class ActivationError(Exception):
    pass


ORDER_DETAIL_KEYS = ("tingkat", "nomor", "nama", "rw", "kelurahan", "kecamatan", "kota", "provinsi")


def activation_problem(order) -> str:
    if order.member_id is None:
        return "Akun pemesan sudah dihapus, jadi pesanan ini tidak bisa diaktifkan."
    if order.is_renewal:
        wilayah = order.wilayah
        if wilayah is None or wilayah.state() == STATE_DELETED:
            return "Data wilayah untuk perpanjangan ini sudah dihapus. Minta pelanggan membuat pesanan baru."
        return ""
    details = order.details or {}
    if details.get("tingkat") not in dict(LEVELS):
        return "Pesanan ini belum punya data tingkat wilayah (RT/RW/Kelurahan/Kecamatan)."
    return ""


@transaction.atomic
def activate_order(order) -> Wilayah:
    """Pesanan baru: buat wilayah + format surat bawaan. Perpanjangan: tambah masa aktif 1 bulan."""
    problem = activation_problem(order)
    if problem:
        raise ActivationError(problem)
    today = timezone.localdate()
    if order.is_renewal:
        wilayah = Wilayah.objects.select_for_update().get(pk=order.wilayah_id)
        start = wilayah.active_until if wilayah.active_until >= today else today
        wilayah.active_until = add_months(start)
        if order.package_id:
            wilayah.package = order.package
            wilayah.package_name = order.package_name
        wilayah.save()
        type(order).objects.filter(wilayah=wilayah, status=order.STATUS_ACTIVE).exclude(pk=order.pk).update(
            status=order.STATUS_DONE
        )
    else:
        d = {k: str((order.details or {}).get(k, ""))[:80] for k in ORDER_DETAIL_KEYS}
        wilayah = Wilayah.objects.create(
            owner=order.member,
            level=d["tingkat"],
            nomor=d["nomor"][:5],
            nama=d["nama"],
            rw=d["rw"][:5],
            kelurahan=d["kelurahan"],
            kecamatan=d["kecamatan"],
            kota=d["kota"],
            provinsi=d["provinsi"],
            ketua_nama=(order.member.display_name or "")[:80],
            package=order.package,
            package_name=order.package_name,
            active_until=add_months(today),
        )
        seed_jenis_surat(wilayah)
        order.wilayah = wilayah
    order.activated_at = timezone.now()
    log.info("Pesanan %s diaktifkan: wilayah SIM #%s aktif sampai %s.", order.code, wilayah.pk, wilayah.active_until)
    return wilayah


def seed_jenis_surat(wilayah: Wilayah, *, only_missing: bool = True) -> int:
    existing = set(wilayah.jenis_surat.values_list("kode", flat=True))
    created = 0
    for n, spec in enumerate(defaults.templates_for(wilayah.level)):
        if only_missing and spec["kode"] in existing:
            continue
        JenisSurat.objects.create(
            wilayah=wilayah,
            kode=spec["kode"],
            nama=spec["nama"],
            judul=spec["judul"],
            kode_surat=spec["kode_surat"],
            keterangan=spec["keterangan"],
            isi=spec["isi"],
            kolom=spec["kolom"],
            butuh_mengetahui=spec["butuh_mengetahui"] and wilayah.level in PARENT_LEVEL,
            urutan=(n + 1) * 10,
        )
        created += 1
    return created


def default_spec(kode: str, level: str) -> dict | None:
    return next((s for s in defaults.templates_for(level) if s["kode"] == kode), None)


def renewal_amount(wilayah: Wilayah, package) -> tuple[int, str]:
    return package.price, package.price_text


def delete_expired_wilayah(today: date | None = None) -> list[str]:
    """Hapus permanen wilayah yang tidak diperpanjang lebih dari 30 hari, beserta SEMUA datanya
    (warga, scan, surat). Wilayah dengan perpanjangan yang sedang dicek/diproses dilewati."""
    from datetime import timedelta

    from apps.members.models import Order
    from apps.pos.models import DELETE_AFTER_DAYS

    today = today or timezone.localdate()
    pending = Order.objects.filter(
        wilayah=OuterRef("pk"), status__in=[Order.STATUS_CHECKING, Order.STATUS_PROCESS]
    )
    due = Wilayah.objects.filter(active_until__lt=today - timedelta(days=DELETE_AFTER_DAYS)).exclude(Exists(pending))
    deleted = []
    for wilayah in due:
        label = wilayah.label
        with transaction.atomic():
            Wilayah.objects.filter(parent=wilayah).update(parent=None, joined_at=None)
            wilayah.delete()
        log.info("Wilayah SIM #%s (%s) dihapus permanen (masa aktif habis lebih dari %s hari).", wilayah.pk, label, DELETE_AFTER_DAYS)
        deleted.append(label)
    return deleted


# ---------------------------------------------------------------------------
# Kolom isian format surat
# ---------------------------------------------------------------------------
def parse_fields_text(text: str) -> tuple[list[dict], list[str]]:
    """Satu baris = satu kolom: ``kunci | Label | wajib/opsional | teks/paragraf/tanggal``."""
    fields, errors, seen = [], [], set()
    for number, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        key = parts[0].lower()
        label = parts[1] if len(parts) > 1 and parts[1] else key.replace("_", " ").capitalize()
        required = (parts[2].lower() if len(parts) > 2 and parts[2] else "wajib") != "opsional"
        kind = parts[3].lower() if len(parts) > 3 and parts[3] else "teks"
        if not FIELD_KEY_RE.match(key):
            errors.append(f"Baris {number}: kunci '{parts[0]}' hanya boleh huruf kecil, angka, dan garis bawah (2–30 karakter).")
            continue
        if key in STANDARD_KEYS or key in AUTO_KEYS:
            errors.append(f"Baris {number}: '{key}' sudah otomatis tersedia, tidak perlu ditambahkan.")
            continue
        if key in seen:
            errors.append(f"Baris {number}: kunci '{key}' dipakai dua kali.")
            continue
        if kind not in FIELD_TYPES:
            errors.append(f"Baris {number}: jenis harus teks, paragraf, atau tanggal.")
            continue
        seen.add(key)
        fields.append({"key": key, "label": label[:80], "type": kind, "required": required})
    if len(fields) > 25:
        errors.append("Maksimal 25 kolom tambahan.")
    return fields, errors


def fields_to_text(fields: list[dict]) -> str:
    return "\n".join(
        f"{f['key']} | {f['label']} | {'wajib' if f.get('required', True) else 'opsional'} | {f.get('type', 'teks')}"
        for f in fields or []
    )


# ---------------------------------------------------------------------------
# Isi surat
# ---------------------------------------------------------------------------
def gender_label(value: str) -> str:
    return {"L": "Laki-laki", "P": "Perempuan"}.get(value, value or "")


def context_for(surat: Surat, wilayah: Wilayah) -> dict:
    data = dict(surat.data or {})
    values = {key: str(data.get(key, "") or "") for key in data}
    values["nama"] = surat.nama
    values["nik"] = surat.nik
    values["jenis_kelamin"] = gender_label(values.get("jenis_kelamin", ""))
    if values.get("tanggal_lahir"):
        try:
            values["tanggal_lahir"] = format_date(date.fromisoformat(values["tanggal_lahir"]))
        except ValueError:
            pass
    values.setdefault("kewarganegaraan", "WNI")
    values["nama_wilayah"] = wilayah.label
    values["jabatan"] = surat.jabatan or wilayah.signer_title
    values["penanda_tangan"] = surat.penanda_tangan or wilayah.ketua_nama
    values["tanggal_surat"] = format_date(surat.tanggal or timezone.localdate())
    values["tempat_surat"] = wilayah.place_name
    values["nomor_surat"] = surat.nomor
    return values


def render_text(template: str, surat: Surat, wilayah: Wilayah) -> str:
    values = context_for(surat, wilayah)
    # Isian yang kosong ditampilkan sebagai garis titik agar mudah diisi tangan bila perlu.
    filled = templating.fill(template, **{k: (v if v.strip() else "....................") for k, v in values.items()})
    return re.sub(r"\{\w+\}", "....................", filled)


_ROW_RE = re.compile(r"^\s*([^:\n]{1,48}?)\s*:\s+(.*)$")


@dataclass
class Block:
    kind: str  # "p" (paragraf) atau "table"
    text: str = ""
    rows: list[tuple[str, str]] = field(default_factory=list)


def blocks(text: str) -> list[Block]:
    """Pecah isi surat menjadi paragraf & tabel 'Label : isi' untuk dicetak rapi."""
    out: list[Block] = []
    for chunk in re.split(r"\n\s*\n", text or ""):
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        if all(_ROW_RE.match(ln) for ln in lines):
            out.append(Block("table", rows=[(m.group(1), m.group(2)) for m in map(_ROW_RE.match, lines)]))
        else:
            out.append(Block("p", text="\n".join(lines)))
    return out


def number_for(wilayah: Wilayah, jenis_kode: str, urut: int, when: date) -> str:
    values = {
        "nomor": str(urut).zfill(3),
        "kode_surat": jenis_kode or "S",
        "wilayah": wilayah.number_code,
        "bulan": str(when.month).zfill(2),
        "bulan_romawi": ROMAN[when.month],
        "tahun": str(when.year),
    }
    return templating.fill(wilayah.nomor_format or "{nomor}/{kode_surat}/{wilayah}/{bulan_romawi}/{tahun}", **values)[:80]


class SuratError(Exception):
    pass


@transaction.atomic
def issue(surat: Surat, *, signer: str = "", title: str = "") -> Surat:
    """Terbitkan surat: nomor urut per tahun (dikunci), isi final, dan kirim ke wilayah atas bila perlu diketahui."""
    wilayah = Wilayah.objects.select_for_update().get(pk=surat.wilayah_id)
    surat = Surat.objects.select_for_update().get(pk=surat.pk, wilayah=wilayah)
    if surat.status != Surat.STATUS_SUBMITTED:
        raise SuratError("Surat ini sudah diproses.")
    today = timezone.localdate()
    last = (
        Surat.objects.filter(wilayah=wilayah, tahun=today.year, nomor_urut__isnull=False)
        .order_by("-nomor_urut").values_list("nomor_urut", flat=True).first()
    )
    surat.nomor_urut = (last or 0) + 1
    surat.tahun = today.year
    surat.tanggal = today
    jenis = surat.jenis
    surat.nomor = number_for(wilayah, jenis.kode_surat if jenis else "", surat.nomor_urut, today)
    surat.penanda_tangan = (signer or wilayah.ketua_nama)[:80]
    surat.jabatan = (title or wilayah.signer_title)[:60]
    template = jenis.isi if jenis else surat.isi
    surat.isi = render_text(template, surat, wilayah)[:12000]
    surat.status = Surat.STATUS_ISSUED
    surat.issued_at = timezone.now()
    if jenis and jenis.butuh_mengetahui and wilayah.parent_id:
        surat.mengetahui = Surat.ACK_WAITING
        surat.mengetahui_wilayah_id = wilayah.parent_id
    surat.save()
    log.info("Surat #%s terbit: %s (wilayah #%s).", surat.pk, surat.nomor, wilayah.pk)
    return surat


@transaction.atomic
def reject(surat: Surat, reason: str) -> Surat:
    surat = Surat.objects.select_for_update().get(pk=surat.pk)
    if surat.status != Surat.STATUS_SUBMITTED:
        raise SuratError("Surat ini sudah diproses.")
    surat.status = Surat.STATUS_REJECTED
    surat.catatan_pengurus = reason[:1000]
    surat.save(update_fields=["status", "catatan_pengurus", "updated_at"])
    return surat


@transaction.atomic
def acknowledge(surat: Surat, parent: Wilayah, *, accept: bool, note: str = "") -> Surat:
    """Wilayah atas (mis. RW) menyatakan 'mengetahui' surat dari wilayah di bawahnya."""
    surat = Surat.objects.select_for_update().get(pk=surat.pk, mengetahui_wilayah=parent)
    if surat.mengetahui != Surat.ACK_WAITING:
        raise SuratError("Surat ini sudah ditanggapi.")
    surat.mengetahui = Surat.ACK_DONE if accept else Surat.ACK_REJECTED
    surat.mengetahui_nama = parent.ketua_nama[:80]
    surat.mengetahui_jabatan = parent.signer_title[:60]
    surat.mengetahui_at = timezone.now()
    surat.mengetahui_catatan = note[:300]
    surat.save()
    return surat


# ---------------------------------------------------------------------------
# Pengajuan surat oleh warga (tanpa login)
# ---------------------------------------------------------------------------
def match_penduduk(wilayah: Wilayah, nik: str, tanggal_lahir: str) -> Penduduk | None:
    """Cocokkan NIK (+ tanggal lahir bila ada) dengan data warga. Hasilnya HANYA untuk pengurus."""
    if not nik:
        return None
    qs = Penduduk.objects.filter(wilayah=wilayah, nik=nik, status=Penduduk.STATUS_ACTIVE)
    if tanggal_lahir:
        qs = qs.filter(Q(tanggal_lahir=tanggal_lahir) | Q(tanggal_lahir__isnull=True))
    return qs.first()


def create_request(wilayah: Wilayah, jenis: JenisSurat, cleaned: dict, *, source: str, ip_hash: str = "") -> Surat:
    data = {}
    for key, _label in STANDARD_FIELDS:
        if key in ("nama", "nik"):
            continue
        value = cleaned.get(key)
        data[key] = value.isoformat() if isinstance(value, date) else str(value or "")
    for spec in jenis.kolom or []:
        value = cleaned.get(f"x_{spec['key']}")
        data[spec["key"]] = value.isoformat() if isinstance(value, date) else str(value or "")
    surat = Surat.objects.create(
        wilayah=wilayah,
        jenis=jenis,
        jenis_nama=jenis.nama,
        judul=jenis.judul,
        nama=cleaned["nama"].strip()[:100],
        nik=cleaned.get("nik", "") or "",
        data=data,
        kontak=(cleaned.get("kontak") or "")[:60],
        sumber=source,
        ip_hash=ip_hash,
        penduduk=match_penduduk(wilayah, cleaned.get("nik", ""), data.get("tanggal_lahir", "")),
    )
    return surat


def prefill_from_penduduk(p: Penduduk) -> dict:
    kk = p.kk
    alamat = kk.alamat
    if kk.rt or kk.rw:
        alamat = f"{alamat} RT {kk.rt or '-'} / RW {kk.rw or '-'}".strip()
    return {
        "nama": p.nama,
        "nik": p.nik,
        "jenis_kelamin": p.jenis_kelamin,
        "tempat_lahir": p.tempat_lahir,
        "tanggal_lahir": p.tanggal_lahir,
        "agama": p.agama,
        "status_perkawinan": p.status_perkawinan,
        "pekerjaan": p.pekerjaan,
        "kewarganegaraan": p.kewarganegaraan,
        "alamat": alamat,
    }


# ---------------------------------------------------------------------------
# Jaringan wilayah
# ---------------------------------------------------------------------------
class NetworkError(Exception):
    pass


def request_join(child: Wilayah, code: str) -> Wilayah:
    parent = Wilayah.objects.filter(join_code=(code or "").strip().upper()).first()
    if parent is None or parent.state() == STATE_DELETED:
        raise NetworkError("Kode undangan tidak ditemukan. Periksa lagi kodenya.")
    if parent.pk == child.pk:
        raise NetworkError("Itu kode wilayah Anda sendiri.")
    if PARENT_LEVEL.get(child.level) != parent.level:
        need = dict(LEVELS).get(PARENT_LEVEL.get(child.level, ""), "—")
        raise NetworkError(f"{child.short_label} hanya bisa bergabung ke {need}. Kode ini milik {parent.short_label}.")
    child.join_request = parent
    child.save(update_fields=["join_request", "updated_at"])
    return parent


@transaction.atomic
def decide_join(parent: Wilayah, child_pk: int, *, accept: bool) -> Wilayah:
    child = Wilayah.objects.select_for_update().get(pk=child_pk, join_request=parent)
    child.join_request = None
    if accept:
        child.parent = parent
        child.joined_at = timezone.now()
        # Untuk kop surat: RT yang bergabung ke RW otomatis memakai nomor RW itu bila kosong.
        if child.level == LEVEL_RT and not child.rw and parent.nomor:
            child.rw = parent.nomor
    child.save()
    return child


def leave_parent(child: Wilayah) -> None:
    child.parent = None
    child.joined_at = None
    child.save(update_fields=["parent", "joined_at", "updated_at"])


def remove_child(parent: Wilayah, child_pk: int) -> None:
    Wilayah.objects.filter(pk=child_pk, parent=parent).update(parent=None, joined_at=None)


def descendants(wilayah: Wilayah) -> list[Wilayah]:
    """Semua wilayah di bawahnya (maks. 3 tingkat), tanpa wilayah yang datanya sudah dihapus."""
    out, frontier = [], [wilayah.pk]
    for _ in range(3):
        level = list(Wilayah.objects.not_deleted().filter(parent_id__in=frontier))
        if not level:
            break
        out += level
        frontier = [w.pk for w in level]
    return out


def ancestors(wilayah: Wilayah) -> list[Wilayah]:
    out, current, seen = [], wilayah, {wilayah.pk}
    while current.parent_id and current.parent_id not in seen and len(out) < 3:
        current = Wilayah.objects.filter(pk=current.parent_id).first()
        if current is None:
            break
        seen.add(current.pk)
        out.append(current)
    return out


def public_announcements(wilayah: Wilayah) -> list[Pengumuman]:
    today = timezone.localdate()
    upper_ids = [w.pk for w in ancestors(wilayah)]
    qs = Pengumuman.objects.filter(
        Q(wilayah=wilayah) | Q(wilayah_id__in=upper_ids, teruskan=True), aktif=True
    ).select_related("wilayah")[:30]
    return [p for p in qs if p.is_showing(today)][:10]


# ---------------------------------------------------------------------------
# Statistik
# ---------------------------------------------------------------------------
AGE_GROUPS = [("Balita (0–4)", 0, 4), ("Anak (5–14)", 5, 14), ("Remaja (15–24)", 15, 24), ("Dewasa (25–59)", 25, 59), ("Lansia (60+)", 60, 200)]


@dataclass
class Stats:
    kk: int = 0
    jiwa: int = 0
    laki: int = 0
    perempuan: int = 0
    pindah: int = 0
    meninggal: int = 0
    umur: list[tuple[str, int]] = field(default_factory=list)
    surat_bulan_ini: int = 0
    surat_menunggu: int = 0


def stats_for(wilayah_ids: list[int]) -> Stats:
    today = timezone.localdate()
    people = Penduduk.objects.filter(wilayah_id__in=wilayah_ids)
    active = people.filter(status=Penduduk.STATUS_ACTIVE)
    counts = active.aggregate(
        jiwa=Count("pk"),
        laki=Count("pk", filter=Q(jenis_kelamin="L")),
        perempuan=Count("pk", filter=Q(jenis_kelamin="P")),
    )
    stats = Stats(
        kk=KartuKeluarga.objects.filter(wilayah_id__in=wilayah_ids, status=KartuKeluarga.STATUS_ACTIVE).count(),
        jiwa=counts["jiwa"],
        laki=counts["laki"],
        perempuan=counts["perempuan"],
        pindah=people.filter(status=Penduduk.STATUS_MOVED).count(),
        meninggal=people.filter(status=Penduduk.STATUS_DEAD).count(),
        surat_bulan_ini=Surat.objects.filter(
            wilayah_id__in=wilayah_ids, status=Surat.STATUS_ISSUED,
            issued_at__year=today.year, issued_at__month=today.month,
        ).count(),
        surat_menunggu=Surat.objects.filter(wilayah_id__in=wilayah_ids, status=Surat.STATUS_SUBMITTED).count(),
    )
    for label, low, high in AGE_GROUPS:
        newest = date(today.year - low, today.month, min(today.day, 28))
        oldest = date(today.year - high - 1, today.month, min(today.day, 28))
        stats.umur.append((label, active.filter(tanggal_lahir__lte=newest, tanggal_lahir__gt=oldest).count()))
    stats.umur.append(("Tanggal lahir belum diisi", active.filter(tanggal_lahir__isnull=True).count()))
    return stats


def search_penduduk(wilayah: Wilayah, q: str):
    q = (q or "").strip()[:60]
    qs = Penduduk.objects.filter(wilayah=wilayah).select_related("kk")
    if not q:
        return qs.none()
    if q.isdigit():
        return qs.filter(Q(nik__startswith=q) | Q(kk__no_kk__startswith=q))[:50]
    return qs.filter(Q(nama__icontains=q) | Q(kk__kepala_nama__icontains=q) | Q(kk__alamat__icontains=q))[:50]


def level_index(level: str) -> int:
    return LEVEL_ORDER.index(level)
