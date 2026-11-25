"""Dashboard pengurus wilayah di hansproject.app/akun/sim/<kode>/...

Setiap view mengambil wilayah lewat ``wilayah_view`` (milik pelanggan yang login), lalu
SEMUA data diambil lewat relasi wilayah itu (``wilayah.kk_set``, ``wilayah.surat_set``, dst.),
jadi pengurus tidak bisa membuka data wilayah lain dengan menebak nomor.

Wilayah di atasnya (mis. RW untuk RT) hanya melihat angka rekap dan surat yang memang
dikirim untuk "diketahui", tidak pernah daftar warga wilayah di bawahnya.
"""
from __future__ import annotations

import csv
import logging
from datetime import date
from functools import wraps
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.content import services as content_services
from apps.content.models import Package
from apps.core import ratelimit
from apps.members import auth
from apps.members.files import serve_private
from apps.members.models import Order
from apps.members.navigation import akun_tabs
from apps.pos.models import STATE_DELETED

from . import ocr, printing, services
from .forms import (
    AckForm,
    JenisSuratForm,
    JoinForm,
    KKForm,
    PendudukFields,
    PendudukForm,
    PengumumanForm,
    RejectForm,
    RenewForm,
    ScanUploadForm,
    WilayahSettingsForm,
    anggota_formset,
    kk_initial_from_wilayah,
    surat_form_class,
    surat_initial,
)
from .models import (
    KEPALA,
    DokumenScan,
    KartuKeluarga,
    Penduduk,
    Pengumuman,
    Surat,
    Wilayah,
    new_join_code,
)

log = logging.getLogger("hans")

NOTICES = {
    "kk": "Data KK tersimpan.",
    "kk-hapus": "KK beserta anggotanya dihapus.",
    "anggota": "Data anggota keluarga tersimpan.",
    "anggota-hapus": "Anggota keluarga dihapus.",
    "scan": "Dokumen tersimpan.",
    "scan-hapus": "Dokumen scan dihapus.",
    "scan-kk": "KK tersimpan dari hasil scan.",
    "scan-ktp": "Data warga tersimpan dari hasil scan KTP.",
    "surat-hapus": "Surat dihapus. QR keaslian dan kode lacaknya tidak berlaku lagi; nomornya tidak dipakai ulang.",
    "surat": "Surat tersimpan.",
    "terbit": "Surat terbit dan sudah bernomor. Silakan cetak.",
    "tolak": "Pengajuan ditolak. Pemohon bisa melihat alasannya lewat kode lacak.",
    "format": "Format surat tersimpan.",
    "format-hapus": "Format surat dihapus.",
    "format-reset": "Format surat dikembalikan ke bawaan.",
    "format-bawaan": "Format surat bawaan yang belum ada sudah ditambahkan.",
    "pengumuman": "Pengumuman tersimpan.",
    "pengumuman-hapus": "Pengumuman dihapus.",
    "gabung": "Permintaan bergabung terkirim. Tunggu persetujuan pengurus wilayah di atas.",
    "gabung-batal": "Permintaan bergabung dibatalkan.",
    "keluar": "Wilayah Anda tidak lagi terhubung ke wilayah di atasnya.",
    "terima": "Wilayah bergabung ke jaringan Anda.",
    "tolak-gabung": "Permintaan bergabung ditolak.",
    "lepas": "Wilayah dilepas dari jaringan Anda.",
    "diketahui": "Surat sudah dinyatakan diketahui.",
    "kode-baru": "Kode undangan baru dibuat. Kode lama tidak berlaku lagi.",
    "pengaturan": "Pengaturan tersimpan.",
    "terkunci": "Langganan sedang terkunci atau ditangguhkan, jadi data belum bisa diubah. Perpanjang dulu.",
}

TABS = [
    ("ringkasan", "Ringkasan", "home", "sim:ringkasan"),
    ("warga", "Data warga", "users", "sim:warga"),
    ("surat", "Surat", "file", "sim:surat"),
    ("format", "Format surat", "edit", "sim:format"),
    ("pengumuman", "Pengumuman", "megaphone", "sim:pengumuman"),
    ("jaringan", "Jaringan", "link", "sim:jaringan"),
    ("pengaturan", "Pengaturan", "settings", "sim:pengaturan"),
]


def _with_query(url: str, **params) -> str:
    params = {k: v for k, v in params.items() if v not in (None, "")}
    return f"{url}?{urlencode(params)}" if params else url


def _url(name: str, w: Wilayah, *args, **query) -> str:
    return _with_query(reverse(name, args=[w.kode, *args]), **query)


def wilayah_view(tab: str, *, edit: bool = False):
    """Wajib login & pemilik wilayah. ``edit``: tolak perubahan saat langganan terkunci."""

    def decorator(func):
        @auth.member_required
        @wraps(func)
        def wrapper(request, kode: str, *args, **kwargs):
            w = get_object_or_404(Wilayah.objects.owned_by(request.member).select_related("parent", "package"), kode=kode)
            if w.state() == STATE_DELETED:
                raise Http404
            if edit and not w.can_edit and request.method == "POST":
                return redirect(_url("sim:ringkasan", w, ok="terkunci"))
            request.wilayah = w
            request.sim_tab = tab
            return func(request, w, *args, **kwargs)

        return wrapper

    return decorator


def _render(request, template: str, context: dict | None = None, status: int = 200):
    snap = content_services.get_snapshot()
    w = getattr(request, "wilayah", None)
    ctx = {
        "snap": snap,
        "site": snap.settings,
        "member": getattr(request, "_member", None),
        "w": w,
        "tabs": [
            {"key": k, "label": label, "icon": icon, "url": reverse(name, args=[w.kode]), "active": k == request.sim_tab}
            for k, label, icon, name in TABS
        ] if w else [],
        "notice": NOTICES.get(request.GET.get("ok", "")),
        "renewal": _open_renewal(w) if w else None,
        "inbox": _inbox_counts(w) if w else None,
        "akun_tabs": akun_tabs("sim", request.member),
        "datalists": {"pendidikan": ocr.EDUCATION_WORDS, "pekerjaan": ocr.JOB_WORDS},
    }
    ctx.update(context or {})
    return render(request, template, ctx, status=status)


def _open_renewal(w: Wilayah) -> Order | None:
    return Order.objects.filter(wilayah=w, order_type=Order.TYPE_RENEWAL, status__in=Order.OPEN_STATUSES).first()


def _inbox_counts(w: Wilayah) -> dict:
    return {
        "surat": w.surat_set.filter(status=Surat.STATUS_SUBMITTED).count(),
        "ketahui": Surat.objects.filter(mengetahui_wilayah=w, mengetahui=Surat.ACK_WAITING).count(),
        "gabung": w.join_requests.count(),
    }


# ---------------------------------------------------------------------------
# Daftar wilayah milik pengurus
# ---------------------------------------------------------------------------
@require_safe
@auth.member_required
def daftar(request):
    request.sim_tab = ""
    wilayah = list(Wilayah.objects.owned_by(request.member).not_deleted().select_related("parent"))
    for w in wilayah:
        w.counts = _inbox_counts(w)
        w.jiwa = w.penduduk_set.filter(status=Penduduk.STATUS_ACTIVE).count()
    snap = content_services.get_snapshot()
    pending = request.member.orders.filter(package_category=Package.CATEGORY_SIM, order_type=Order.TYPE_NEW,
                                           status__in=Order.OPEN_STATUSES)
    return _render(request, "sim/daftar.html", {
        "wilayah_list": wilayah, "packages": snap.sim_packages, "pending_orders": pending, "page_title": "Instansi saya",
    })


# ---------------------------------------------------------------------------
# Ringkasan
# ---------------------------------------------------------------------------
@require_safe
@wilayah_view("ringkasan")
def ringkasan(request, w: Wilayah):
    q = request.GET.get("q", "")
    results = services.search_penduduk(w, q) if q else None
    children = list(w.children.not_deleted())
    network_stats = services.stats_for([c.pk for c in services.descendants(w)]) if children else None
    latest = w.surat_set.select_related("jenis")[:6]
    return _render(request, "sim/ringkasan.html", {
        "stats": services.stats_for([w.pk]),
        "network_stats": network_stats,
        "children": children,
        "q": q,
        "results": results,
        "latest": latest,
        "public_url": request.build_absolute_uri(w.public_path),
        "page_title": w.short_label,
    })


# ---------------------------------------------------------------------------
# Data warga: KK & anggota
# ---------------------------------------------------------------------------
@require_safe
@wilayah_view("warga")
def warga(request, w: Wilayah):
    q = (request.GET.get("q") or "").strip()[:60]
    status = request.GET.get("status", "aktif")
    kk_list = w.kk_set.annotate(jumlah=Count("anggota", filter=Q(anggota__status=Penduduk.STATUS_ACTIVE)))
    if status in (KartuKeluarga.STATUS_ACTIVE, KartuKeluarga.STATUS_MOVED):
        kk_list = kk_list.filter(status=status)
    if q:
        if q.isdigit():
            kk_list = kk_list.filter(Q(no_kk__startswith=q) | Q(anggota__nik__startswith=q)).distinct()
        else:
            kk_list = kk_list.filter(Q(kepala_nama__icontains=q) | Q(alamat__icontains=q) | Q(anggota__nama__icontains=q)).distinct()
    page = Paginator(kk_list.order_by("kepala_nama", "pk"), 30).get_page(request.GET.get("hal"))
    return _render(request, "sim/warga.html", {
        "page": page, "q": q, "status": status, "pager_query": urlencode({"q": q, "status": status}),
        "page_title": "Data warga",
    })


def _kk_editor(w: Wilayah, kk: KartuKeluarga | None, data, *, initial: dict | None = None,
               members: list[dict] | None = None) -> KartuKeluarga | dict:
    """Formulir KK + semua anggotanya (KK baru, ubah KK, atau hasil scan). Berhasil -> KK tersimpan."""
    existing = kk.anggota.count() if kk else 0
    members = members or []
    if kk:
        extra = 2
    else:
        extra = max(len(members) + 2, 6)
    extra = max(0, min(extra, 15 - existing))
    FormSet = anggota_formset(extra=extra)
    if kk is None:
        base = kk_initial_from_wilayah(w)
        base.update({k: v for k, v in (initial or {}).items() if v})
        initial_rows = members or [{"hubungan": KEPALA, "kewarganegaraan": "WNI"}]
    else:
        base, initial_rows = None, []
    form = KKForm(data, instance=kk, initial=base, wilayah=w)
    formset = FormSet(data, instance=kk or KartuKeluarga(wilayah=w), initial=initial_rows, prefix="anggota", wilayah=w)
    if data is not None:
        ok = form.is_valid()
        ok = formset.is_valid() and ok
        if ok:
            with transaction.atomic():
                saved = form.save()
                formset.instance = saved
                formset.save()
                services.sync_kepala(saved)
            return saved
    return {"form": form, "formset": formset, "relations_kepala": KEPALA}


@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("warga", edit=True)
def kk_form(request, w: Wilayah, pk: int | None = None):
    kk = get_object_or_404(w.kk_set, pk=pk) if pk else None
    if kk is None and request.method == "POST" and w.kk_set.count() >= services.MAX_KK_PER_WILAYAH:
        raise Http404
    result = _kk_editor(w, kk, request.POST if request.method == "POST" else None)
    if isinstance(result, KartuKeluarga):
        log.info("KK #%s disimpan (wilayah #%s).", result.pk, w.pk)
        return redirect(_url("sim:kk", w, result.pk, ok="kk"))
    return _render(request, "sim/kk_form.html", result | {
        "kk": kk, "page_title": f"Ubah KK {kk.kepala_label}" if kk else "KK baru",
    }, status=400 if request.method == "POST" else 200)


@require_safe
@wilayah_view("warga")
def kk_detail(request, w: Wilayah, pk: int):
    kk = get_object_or_404(w.kk_set, pk=pk)
    return _render(request, "sim/kk_detail.html", {
        "kk": kk,
        "anggota": kk.anggota.all(),
        "scans": kk.scan_set.all()[:10],
        "page_title": f"KK {kk.kepala_label}",
    })


@require_POST
@wilayah_view("warga", edit=True)
def kk_hapus(request, w: Wilayah, pk: int):
    kk = get_object_or_404(w.kk_set, pk=pk)
    kk.delete()
    return redirect(_url("sim:warga", w, ok="kk-hapus"))


@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("warga", edit=True)
def penduduk_form(request, w: Wilayah, kk: int | None = None, pk: int | None = None):
    person = get_object_or_404(w.penduduk_set.select_related("kk"), pk=pk) if pk else None
    family = person.kk if person else get_object_or_404(w.kk_set, pk=kk)
    initial = None if person else {"kewarganegaraan": "WNI", "urutan": family.anggota.count() + 1,
                                   **({} if family.kepala_nama else {"hubungan": KEPALA})}
    form = PendudukForm(request.POST or None, instance=person, kk=family, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_url("sim:kk", w, family.pk, ok="anggota"))
    return _render(request, "sim/penduduk_form.html", {
        "form": form, "kk": family, "person": person, "page_title": "Ubah anggota" if person else "Tambah anggota",
    }, status=400 if form.errors else 200)


@require_POST
@wilayah_view("warga", edit=True)
def penduduk_hapus(request, w: Wilayah, pk: int):
    person = get_object_or_404(w.penduduk_set.select_related("kk"), pk=pk)
    family = person.kk
    person.delete()
    services.sync_kepala(family)
    return redirect(_url("sim:kk", w, family.pk, ok="anggota-hapus"))


def _csv_safe(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@require_safe
@wilayah_view("warga")
def warga_unduh(request, w: Wilayah):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="data-warga-{w.kode}-{timezone.localdate():%Y%m%d}.csv"'
    response.write("﻿")  # BOM agar Excel membaca UTF-8
    writer = csv.writer(response)
    writer.writerow([
        "No KK", "Kepala keluarga", "Alamat", "RT", "RW", "Desa/Kelurahan", "Kecamatan", "Kabupaten/Kota", "Provinsi",
        "Kode pos", "NIK", "Nama", "Jenis kelamin", "Tempat lahir", "Tanggal lahir", "Agama", "Pendidikan", "Pekerjaan",
        "Golongan darah", "Status perkawinan", "Tanggal perkawinan", "Hubungan", "Kewarganegaraan", "No paspor",
        "No KITAS/KITAP", "Ayah", "Ibu", "Status",
    ])
    people = w.penduduk_set.select_related("kk").order_by("kk__kepala_nama", "kk_id", "urutan", "pk")
    for p in people.iterator(chunk_size=500):
        k = p.kk
        writer.writerow([_csv_safe(x) for x in (
            k.no_kk, k.kepala_nama, k.alamat, k.rt, k.rw, k.kelurahan, k.kecamatan, k.kota, k.provinsi, k.kode_pos,
            p.nik, p.nama, p.get_jenis_kelamin_display(), p.tempat_lahir,
            p.tanggal_lahir.isoformat() if p.tanggal_lahir else "", p.agama, p.pendidikan, p.pekerjaan, p.golongan_darah,
            p.status_perkawinan, p.tanggal_perkawinan.isoformat() if p.tanggal_perkawinan else "", p.hubungan,
            p.kewarganegaraan, p.no_paspor, p.no_kitap, p.nama_ayah, p.nama_ibu, p.get_status_display(),
        )])
    log.info("Data warga wilayah #%s diunduh oleh pengurus #%s.", w.pk, request.member.pk)
    return response


# ---------------------------------------------------------------------------
# Scan KK/KTP (OCR) — bagian dari menu Data warga
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("warga", edit=True)
def scan(request, w: Wilayah):
    form = ScanUploadForm(request.POST or None, request.FILES or None)
    error = ""
    if request.method == "POST":
        limit, used = _scan_quota(w)
        reads = request.POST.get("jenis") != DokumenScan.TYPE_OTHER
        if reads and limit is not None and used >= limit:
            error = (f"Kuota baca otomatis paket Anda ({limit} dokumen per bulan) sudah habis bulan ini. "
                     "Coba lagi bulan depan, atau naik ke Paket Tumbuh saat perpanjang.")
        elif not ratelimit.allow(f"sim-scan:{w.pk}", limit=services.MAX_SCANS_PER_DAY, window=86400):
            error = "Batas unggah hari ini tercapai. Coba lagi besok."
        elif form.is_valid():
            doc = DokumenScan(wilayah=w, jenis=form.cleaned_data["jenis"], judul=form.cleaned_data["judul"])
            doc.gambar.save(form.cleaned_data["gambar"].name, form.cleaned_data["gambar"], save=False)
            doc.save()
            _run_ocr(doc)
            return redirect(_url("sim:scan-detail", w, doc.pk))
    page = Paginator(w.scan_set.select_related("kk"), 24).get_page(request.GET.get("hal"))
    limit, used = _scan_quota(w)
    return _render(request, "sim/scan.html", {
        "form": form, "error": error, "page": page, "ocr_ready": ocr.is_available(), "page_title": "Scan KK/KTP",
        "scan_limit": limit, "scan_used": used,
    }, status=400 if (error or form.errors) else 200)


def _scan_quota(w: Wilayah) -> tuple[int | None, int]:
    """(batas per bulan dari paket, jumlah KK/KTP yang dibaca otomatis bulan ini). Batas None = tanpa batas."""
    limit = w.package.scan_limit if w.package_id and w.package else None
    # Rentang waktu (bukan __date): MariaDB tanpa tabel zona waktu tidak bisa memakai __date.
    start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = (w.scan_set.filter(created_at__gte=start).exclude(jenis=DokumenScan.TYPE_OTHER).count()
            if limit is not None else 0)
    return limit, used


def _run_ocr(doc: DokumenScan) -> None:
    if doc.jenis == DokumenScan.TYPE_OTHER:  # dokumen lain hanya disimpan sebagai gambar
        return
    result = ocr.read_text(doc.gambar, kind=doc.jenis)
    if result.ok:
        doc.teks, doc.hasil, doc.ocr_status, doc.ocr_pesan = result.text, result.data, DokumenScan.OCR_DONE, ""
    else:
        doc.ocr_status = DokumenScan.OCR_FAILED if result.available else DokumenScan.OCR_UNAVAILABLE
        doc.ocr_pesan = result.message[:200]
    doc.save(update_fields=["teks", "hasil", "ocr_status", "ocr_pesan"])


KK_SCAN_KEYS = ("no_kk", "alamat", "rt", "rw", "kode_pos", "kelurahan", "kecamatan", "kota", "provinsi", "tanggal_dikeluarkan")
MEMBER_KEYS = tuple(PendudukFields.Meta.fields)


def _scan_members(hasil: dict) -> list[dict]:
    rows = [r for r in hasil.get("anggota", []) if isinstance(r, dict)][:15]
    out = []
    for row in rows:
        clean = {k: str(row.get(k) or "") for k in MEMBER_KEYS if row.get(k)}
        clean.setdefault("kewarganegaraan", "WNI")
        out.append(clean)
    return out


@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("warga", edit=True)
def scan_detail(request, w: Wilayah, pk: int):
    doc = get_object_or_404(w.scan_set.select_related("kk", "penduduk"), pk=pk)
    hasil = doc.hasil if isinstance(doc.hasil, dict) else {}
    action = request.POST.get("aksi") if request.method == "POST" else ""
    if action == "baca":
        if ratelimit.allow(f"sim-ocr:{w.pk}", limit=60, window=3600):
            _run_ocr(doc)
        return redirect(_url("sim:scan-detail", w, doc.pk))
    if action == "hubungkan":
        kk_pk = request.POST.get("kk", "")
        doc.kk = get_object_or_404(w.kk_set, pk=int(kk_pk)) if kk_pk.isdigit() else None
        doc.save(update_fields=["kk"])
        return redirect(_url("sim:scan-detail", w, doc.pk, ok="scan"))
    if action == "hapus":
        doc.delete()
        return redirect(_url("sim:scan", w, ok="scan-hapus"))
    if action and action not in ("simpan-kk", "simpan-ktp"):
        raise Http404

    ctx: dict = {"doc": doc, "hasil": hasil, "page_title": str(doc),
                 "kk_choices": w.kk_set.order_by("kepala_nama")[:500]}
    status = 200
    if doc.jenis == DokumenScan.TYPE_KK and not doc.kk_id:
        data = request.POST if action == "simpan-kk" else None
        if data is not None and w.kk_set.count() >= services.MAX_KK_PER_WILAYAH:
            raise Http404
        initial = {k: hasil.get(k, "") for k in KK_SCAN_KEYS}
        members = _scan_members(hasil)
        result = _kk_editor(w, None, data, initial=initial, members=members)
        if isinstance(result, KartuKeluarga):
            doc.kk = result
            doc.save(update_fields=["kk"])
            log.info("KK #%s dibuat dari scan #%s.", result.pk, doc.pk)
            return redirect(_url("sim:kk", w, result.pk, ok="scan-kk"))
        ctx.update(result, found=len(members))
        status = 400 if data is not None else 200
    elif doc.jenis == DokumenScan.TYPE_KTP and not doc.penduduk_id:
        data = request.POST if action == "simpan-ktp" else None
        values = {k: hasil.get(k) for k in MEMBER_KEYS if hasil.get(k)}
        person = w.penduduk_set.select_related("kk").filter(nik=hasil.get("nik")).first() if hasil.get("nik") else None
        if person:
            form = PendudukForm(data, instance=person, kk=person.kk, initial=values, ringkas=True)
        else:
            values.setdefault("kewarganegaraan", "WNI")
            if doc.kk_id:
                values["kk"] = doc.kk_id
            form = PendudukForm(data, wilayah=w, pilih_kk=True, initial=values, ringkas=True)
        if data is not None and form.is_valid():
            saved = form.save()
            doc.penduduk, doc.kk = saved, saved.kk
            doc.save(update_fields=["penduduk", "kk"])
            return redirect(_url("sim:kk", w, saved.kk_id, ok="scan-ktp"))
        ctx.update(person_form=form, existing_person=person)
        status = 400 if data is not None else 200
    return _render(request, "sim/scan_detail.html", ctx, status=status)


@require_safe
@wilayah_view("warga")
def scan_gambar(request, w: Wilayah, pk: int):
    doc = get_object_or_404(w.scan_set, pk=pk)
    return serve_private(doc.gambar)


# ---------------------------------------------------------------------------
# Surat
# ---------------------------------------------------------------------------
SURAT_FILTERS = {
    "masuk": ("Perlu diproses", Q(status=Surat.STATUS_SUBMITTED)),
    "terbit": ("Sudah terbit", Q(status=Surat.STATUS_ISSUED)),
    "ditolak": ("Ditolak", Q(status__in=[Surat.STATUS_REJECTED, Surat.STATUS_CANCELLED])),
    "semua": ("Semua", Q()),
}


@require_safe
@wilayah_view("surat")
def surat(request, w: Wilayah):
    key = request.GET.get("filter", "masuk")
    if key not in SURAT_FILTERS:
        key = "masuk"
    qs = w.surat_set.filter(SURAT_FILTERS[key][1]).select_related("jenis", "penduduk")
    q = (request.GET.get("q") or "").strip()[:60]
    if q:
        qs = qs.filter(Q(nama__icontains=q) | Q(nik__startswith=q) | Q(nomor__icontains=q))
    page = Paginator(qs, 30).get_page(request.GET.get("hal"))
    pager_query = urlencode({"filter": key, "q": q})
    filters = [{"key": k, "label": label, "active": k == key, "url": _url("sim:surat", w, filter=k)} for k, (label, _) in SURAT_FILTERS.items()]
    return _render(request, "sim/surat.html", {
        "page": page, "filters": filters, "q": q, "filter": key, "pager_query": pager_query, "page_title": "Surat",
    })


@require_safe
@wilayah_view("surat")
def surat_pilih(request, w: Wilayah):
    person = None
    pid = request.GET.get("penduduk", "")
    if pid.isdigit():
        person = w.penduduk_set.filter(pk=int(pid)).first()
    return _render(request, "sim/surat_pilih.html", {
        "jenis_list": w.jenis_surat.filter(aktif=True), "person": person, "page_title": "Buat surat",
    })


@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("surat", edit=True)
def surat_baru(request, w: Wilayah, jenis: str):
    jenis_obj = get_object_or_404(w.jenis_surat, kode=jenis, aktif=True)
    form_class = surat_form_class(jenis_obj, public=False)
    initial = {}
    person = None
    pid = request.GET.get("penduduk", "") or request.POST.get("penduduk", "")
    if pid.isdigit():
        person = w.penduduk_set.select_related("kk").filter(pk=int(pid)).first()
        if person:
            initial = services.prefill_from_penduduk(person)
    form = form_class(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        s = services.create_request(w, jenis_obj, form.cleaned_data, source=Surat.SOURCE_DIRECT)
        if person and not s.penduduk_id:
            s.penduduk = person
            s.save(update_fields=["penduduk"])
        if request.POST.get("terbitkan"):
            services.issue(s)
            return redirect(_url("sim:surat-detail", w, s.pk, ok="terbit"))
        return redirect(_url("sim:surat-detail", w, s.pk, ok="surat"))
    return _render(request, "sim/surat_form.html", {
        "form": form, "jenis": jenis_obj, "person": person, "page_title": jenis_obj.nama,
    }, status=400 if form.errors else 200)


@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("surat", edit=True)
def surat_detail(request, w: Wilayah, pk: int):
    s = get_object_or_404(w.surat_set.select_related("jenis", "penduduk__kk"), pk=pk)
    editable = s.status == Surat.STATUS_SUBMITTED
    form = surat_form_class(s.jenis, public=False)(initial=surat_initial(s)) if editable and s.jenis else None
    reject_form = RejectForm()
    if request.method == "POST" and request.POST.get("aksi") == "hapus" and not editable:
        try:
            services.delete_surat(s)
        except services.SuratError:
            return redirect(_url("sim:surat-detail", w, s.pk))
        return redirect(_url("sim:surat", w, filter="semua", ok="surat-hapus"))
    if request.method == "POST" and editable:
        action = request.POST.get("aksi")
        if action in ("simpan", "terbit") and s.jenis:
            form = surat_form_class(s.jenis, public=False)(request.POST)
            if form.is_valid():
                _update_surat(s, form.cleaned_data)
                if action == "terbit":
                    try:
                        services.issue(s, signer=request.POST.get("penanda_tangan", ""), title=request.POST.get("jabatan", ""))
                    except services.SuratError:
                        pass
                    return redirect(_url("sim:surat-detail", w, s.pk, ok="terbit"))
                return redirect(_url("sim:surat-detail", w, s.pk, ok="surat"))
        elif action == "tolak":
            reject_form = RejectForm(request.POST)
            if reject_form.is_valid():
                try:
                    services.reject(s, reject_form.cleaned_data["alasan"])
                except services.SuratError:
                    pass
                return redirect(_url("sim:surat-detail", w, s.pk, ok="tolak"))
    elif request.method == "POST" and request.POST.get("aksi") == "catatan":
        s.catatan_pengurus = (request.POST.get("catatan") or "")[:1000]
        s.save(update_fields=["catatan_pengurus", "updated_at"])
        return redirect(_url("sim:surat-detail", w, s.pk, ok="surat"))
    return _render(request, "sim/surat_detail.html", {
        "s": s,
        "form": form,
        "reject_form": reject_form,
        "lacak_url": request.build_absolute_uri(s.lacak_path),
        "page_title": f"{s.jenis_nama} — {s.nama}",
    }, status=400 if (form is not None and form.errors) or reject_form.errors else 200)


def _update_surat(s: Surat, cleaned: dict) -> None:
    data = {}
    for key, _ in services.STANDARD_FIELDS:
        if key in ("nama", "nik"):
            continue
        value = cleaned.get(key)
        data[key] = value.isoformat() if isinstance(value, date) else str(value or "")
    for spec in s.jenis.kolom or []:
        value = cleaned.get(f"x_{spec['key']}")
        data[spec["key"]] = value.isoformat() if isinstance(value, date) else str(value or "")
    s.nama = cleaned["nama"][:100]
    s.nik = cleaned.get("nik", "") or ""
    s.data = data
    s.save(update_fields=["nama", "nik", "data", "updated_at"])


@require_safe
@wilayah_view("surat")
def surat_cetak(request, w: Wilayah, pk: int):
    s = get_object_or_404(w.surat_set.select_related("jenis"), pk=pk)
    return printing.render_letter(request, s, w, images_url=lambda kind: _url("sim:gambar", w, kind), draft=not s.is_issued)


# ---------------------------------------------------------------------------
# Format surat
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("format", edit=True)
def format_list(request, w: Wilayah):
    if request.method == "POST" and request.POST.get("aksi") == "bawaan":
        services.seed_jenis_surat(w)
        return redirect(_url("sim:format", w, ok="format-bawaan"))
    return _render(request, "sim/format_list.html", {
        "jenis_list": w.jenis_surat.annotate(jumlah=Count("surat_set")), "page_title": "Format surat",
    })


@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("format", edit=True)
def format_form(request, w: Wilayah, pk: int | None = None):
    jenis = get_object_or_404(w.jenis_surat, pk=pk) if pk else None
    if jenis is None and request.method == "POST" and w.jenis_surat.count() >= services.MAX_JENIS_SURAT:
        raise Http404
    form = JenisSuratForm(request.POST or None, instance=jenis, wilayah=w)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_url("sim:format", w, ok="format"))
    return _render(request, "sim/format_form.html", {
        "form": form,
        "jenis": jenis,
        "has_default": bool(jenis and services.default_spec(jenis.kode, w.level)),
        "standard_fields": services.STANDARD_FIELDS,
        "page_title": jenis.nama if jenis else "Format surat baru",
    }, status=400 if form.errors else 200)


@require_POST
@wilayah_view("format", edit=True)
def format_hapus(request, w: Wilayah, pk: int):
    get_object_or_404(w.jenis_surat, pk=pk).delete()
    return redirect(_url("sim:format", w, ok="format-hapus"))


@require_POST
@wilayah_view("format", edit=True)
def format_reset(request, w: Wilayah, pk: int):
    jenis = get_object_or_404(w.jenis_surat, pk=pk)
    spec = services.default_spec(jenis.kode, w.level)
    if spec is None:
        raise Http404
    for key in ("nama", "judul", "kode_surat", "keterangan", "isi", "kolom"):
        setattr(jenis, key, spec[key])
    jenis.butuh_mengetahui = spec["butuh_mengetahui"] and bool(w.parent_level)
    jenis.save()
    return redirect(_url("sim:format", w, ok="format-reset"))


@require_safe
@wilayah_view("format")
def format_contoh(request, w: Wilayah, pk: int):
    """Pratinjau format dengan data contoh, untuk melihat hasil cetak sebelum dipakai."""
    jenis = get_object_or_404(w.jenis_surat, pk=pk)
    sample = Surat(
        wilayah=w, jenis=jenis, jenis_nama=jenis.nama, judul=jenis.judul, nama="BUDI SANTOSO", nik="3201010101900001",
        data={
            "jenis_kelamin": "L", "tempat_lahir": "BOGOR", "tanggal_lahir": "1990-01-01", "agama": "Islam",
            "status_perkawinan": "Kawin", "pekerjaan": "WIRASWASTA", "kewarganegaraan": "WNI",
            "alamat": "JL. MELATI NO. 1", "keperluan": "Contoh keperluan",
        },
    )
    sample.isi = services.render_text(jenis.isi, sample, w)
    return printing.render_letter(request, sample, w, images_url=lambda kind: _url("sim:gambar", w, kind), draft=True, sample=True)


# ---------------------------------------------------------------------------
# Pengumuman
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("pengumuman", edit=True)
def pengumuman(request, w: Wilayah, pk: int | None = None):
    item = get_object_or_404(w.pengumuman_set, pk=pk) if pk else None
    form = PengumumanForm(request.POST or None, instance=item, wilayah=w)
    if request.method == "POST" and form.is_valid():
        if item is None and w.pengumuman_set.count() >= 200:
            raise Http404
        form.save()
        return redirect(_url("sim:pengumuman", w, ok="pengumuman"))
    upper = [p for p in Pengumuman.objects.filter(wilayah__in=services.ancestors(w), teruskan=True, aktif=True)[:10]]
    return _render(request, "sim/pengumuman.html", {
        "form": form, "item": item, "items": w.pengumuman_set.all()[:50], "upper": upper, "page_title": "Pengumuman",
    }, status=400 if form.errors else 200)


@require_POST
@wilayah_view("pengumuman", edit=True)
def pengumuman_hapus(request, w: Wilayah, pk: int):
    get_object_or_404(w.pengumuman_set, pk=pk).delete()
    return redirect(_url("sim:pengumuman", w, ok="pengumuman-hapus"))


# ---------------------------------------------------------------------------
# Jaringan wilayah
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("jaringan", edit=True)
def jaringan(request, w: Wilayah):
    is_join = request.method == "POST" and request.POST.get("aksi") == "gabung"
    join_form = JoinForm(request.POST if is_join else None)
    error = ""
    if request.method == "POST":
        action = request.POST.get("aksi")
        if action == "gabung" and join_form.is_valid():
            if not ratelimit.allow(f"sim-join:{w.pk}", limit=10, window=3600):
                error = "Terlalu banyak percobaan. Coba lagi nanti."
            else:
                try:
                    services.request_join(w, join_form.cleaned_data["kode"])
                    return redirect(_url("sim:jaringan", w, ok="gabung"))
                except services.NetworkError as exc:
                    error = str(exc)
        elif action == "batal-gabung":
            w.join_request = None
            w.save(update_fields=["join_request", "updated_at"])
            return redirect(_url("sim:jaringan", w, ok="gabung-batal"))
        elif action == "keluar":
            services.leave_parent(w)
            return redirect(_url("sim:jaringan", w, ok="keluar"))
        elif action in ("terima", "tolak") and request.POST.get("wilayah", "").isdigit():
            try:
                services.decide_join(w, int(request.POST["wilayah"]), accept=action == "terima")
            except Wilayah.DoesNotExist:
                raise Http404
            return redirect(_url("sim:jaringan", w, ok="terima" if action == "terima" else "tolak-gabung"))
        elif action == "lepas" and request.POST.get("wilayah", "").isdigit():
            services.remove_child(w, int(request.POST["wilayah"]))
            return redirect(_url("sim:jaringan", w, ok="lepas"))
        elif action == "kode-baru":
            w.join_code = new_join_code()
            w.save(update_fields=["join_code", "updated_at"])
            return redirect(_url("sim:jaringan", w, ok="kode-baru"))
    children = list(w.children.not_deleted())
    for child in children:
        child.stats = services.stats_for([child.pk] + [d.pk for d in services.descendants(child)])
    return _render(request, "sim/jaringan.html", {
        "join_form": join_form,
        "error": error,
        "ancestors": services.ancestors(w),
        "children": children,
        "requests": w.join_requests.all(),
        "ack_list": Surat.objects.filter(mengetahui_wilayah=w).select_related("wilayah").order_by("mengetahui", "-issued_at")[:50],
        "page_title": "Jaringan wilayah",
    }, status=400 if (error or join_form.errors) else 200)


@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("jaringan", edit=True)
def ketahui(request, w: Wilayah, pk: int):
    """Surat dari wilayah di bawah yang perlu 'diketahui' (hanya surat yang dikirim ke wilayah ini)."""
    s = get_object_or_404(Surat.objects.select_related("wilayah", "jenis"), pk=pk, mengetahui_wilayah=w)
    form = AckForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.acknowledge(s, w, accept=request.POST.get("aksi") != "tolak", note=form.cleaned_data["catatan"])
        except services.SuratError:
            pass
        return redirect(_url("sim:jaringan", w, ok="diketahui"))
    if request.GET.get("cetak"):
        return printing.render_letter(request, s, s.wilayah, images_url=None, draft=False)
    return _render(request, "sim/ketahui.html", {"s": s, "form": form, "page_title": f"Mengetahui: {s.jenis_nama}"})


# ---------------------------------------------------------------------------
# Pengaturan & perpanjangan
# ---------------------------------------------------------------------------
@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("pengaturan", edit=True)
def pengaturan(request, w: Wilayah):
    form = WilayahSettingsForm(request.POST or None, request.FILES or None, instance=w)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_url("sim:pengaturan", w, ok="pengaturan"))
    return _render(request, "sim/pengaturan.html", {"form": form, "page_title": "Pengaturan"},
                   status=400 if form.errors else 200)


@require_safe
@wilayah_view("pengaturan")
def gambar(request, w: Wilayah, kind: str):
    field = {"ttd": w.ttd, "cap": w.cap}.get(kind)
    if not field:
        raise Http404
    return serve_private(field)


@require_http_methods(["GET", "HEAD", "POST"])
@wilayah_view("ringkasan")
def perpanjang(request, w: Wilayah):
    existing = _open_renewal(w)
    form = RenewForm(request.POST or None, initial={"package": w.package_id})
    if request.method == "POST":
        if existing:
            return redirect("akun:pesanan", code=existing.code)
        if form.is_valid():
            package = form.cleaned_data["package"]
            order = Order.objects.create(
                member=request.member,
                order_type=Order.TYPE_RENEWAL,
                wilayah=w,
                package=package,
                package_name=package.name,
                package_category=package.category,
                price_text=package.price_text,
                amount=package.price,
                status=Order.STATUS_PAYMENT,
            )
            log.info("Perpanjangan SIM %s untuk wilayah #%s.", order.code, w.pk)
            return redirect(_with_query(reverse("akun:pesanan", args=[order.code]), ok="dibuat"))
    return _render(request, "sim/perpanjang.html", {"form": form, "existing": existing, "page_title": "Perpanjang"},
                   status=400 if form.errors else 200)
