"""Halaman warga (tanpa login): hansproject.app/w/<kode>/ dan /surat/...

- Warga mengajukan surat online, lalu mendapat KODE LACAK (acak, 24 karakter) untuk melihat
  status. Tidak ada daftar surat yang bisa dijelajahi; setiap halaman butuh kodenya.
- Data pribadi di halaman lacak/cek ditampilkan tersamar (NIK & nama).
- Semua halaman: no-store & noindex, dan dibatasi jumlah request per alamat IP.
"""
from __future__ import annotations

import logging
import re

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_safe

from apps.content import services as content_services
from apps.core import ratelimit
from apps.core.privacy import ip_hash
from apps.members.files import serve_private
from apps.pos.models import STATE_DELETED

from . import printing, services
from .forms import LacakForm, surat_form_class
from .models import Surat, Wilayah

log = logging.getLogger("hans")

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{10,40}$")


def _private(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _page(request, template: str, ctx: dict, status: int = 200):
    snap = content_services.get_snapshot()
    base = {"snap": snap, "site": snap.settings, "member": getattr(request, "_member", None)}
    base.update(ctx)
    return _private(render(request, template, base, status=status))


def _too_many(request):
    return _page(request, "warga/sibuk.html", {"page_title": "Terlalu banyak permintaan"}, status=429)


def _wilayah_or_404(kode: str) -> Wilayah:
    w = get_object_or_404(Wilayah.objects.select_related("parent"), kode=kode)
    if w.state() == STATE_DELETED:
        raise Http404
    return w


@require_safe
def wilayah(request, kode: str):
    if not ratelimit.allow(f"warga:{ip_hash(request)}", limit=120, window=600):
        return _too_many(request)
    w = _wilayah_or_404(kode)
    return _page(request, "warga/wilayah.html", {
        "w": w,
        "open": w.serves_public,
        "jenis_list": w.jenis_surat.filter(aktif=True, online=True) if w.serves_public and w.terima_online else [],
        "pengumuman": services.public_announcements(w) if w.serves_public else [],
        "lacak_form": LacakForm(),
        "page_title": w.label,
    })


@require_http_methods(["GET", "HEAD", "POST"])
def ajukan(request, kode: str, jenis: str):
    w = _wilayah_or_404(kode)
    if not (w.serves_public and w.terima_online):
        raise Http404
    jenis_obj = get_object_or_404(w.jenis_surat, kode=jenis, aktif=True, online=True)
    form = surat_form_class(jenis_obj, public=True)(request.POST or None)
    if request.method == "POST":
        who = ip_hash(request)
        if not (ratelimit.allow(f"ajukan:{who}", limit=5, window=3600)
                and ratelimit.allow(f"ajukan-w:{w.pk}", limit=150, window=86400)):
            return _too_many(request)
        if form.is_valid():
            s = services.create_request(w, jenis_obj, form.cleaned_data, source=Surat.SOURCE_ONLINE, ip_hash=who)
            log.info("Pengajuan surat online #%s di wilayah #%s.", s.pk, w.pk)
            return redirect(f"{reverse('warga:lacak', args=[s.lacak_token])}?baru=1")
    return _page(request, "warga/ajukan.html", {
        "w": w, "jenis": jenis_obj, "form": form, "page_title": f"Ajukan {jenis_obj.nama}",
    }, status=400 if form.errors else 200)


@require_http_methods(["GET", "HEAD", "POST"])
def lacak_cari(request):
    form = LacakForm(request.POST or request.GET or None)
    if form.is_bound and form.is_valid():
        token = re.sub(r"\s+", "", form.cleaned_data["kode"])
        if TOKEN_RE.match(token):
            return redirect("warga:lacak", token=token)
        form.add_error("kode", "Kode lacak tidak dikenali.")
    return _page(request, "warga/lacak_cari.html", {"form": form, "page_title": "Lacak surat"},
                 status=400 if form.errors else 200)


def _surat_by_lacak(request, token: str) -> Surat:
    if not TOKEN_RE.match(token or ""):
        raise Http404
    s = Surat.objects.select_related("wilayah", "jenis").filter(lacak_token=token).first()
    if s is None or s.wilayah.state() == STATE_DELETED:
        raise Http404
    return s


@require_safe
def lacak(request, token: str):
    if not ratelimit.allow(f"lacak:{ip_hash(request)}", limit=60, window=600):
        return _too_many(request)
    s = _surat_by_lacak(request, token)
    can_print = s.is_issued and s.wilayah.warga_boleh_cetak and s.wilayah.serves_public
    return _page(request, "warga/lacak.html", {
        "s": s, "w": s.wilayah, "baru": request.GET.get("baru") == "1", "can_print": can_print,
        "lacak_url": request.build_absolute_uri(s.lacak_path), "page_title": "Status surat",
    })


@require_safe
def lacak_cetak(request, token: str):
    if not ratelimit.allow(f"lacak:{ip_hash(request)}", limit=60, window=600):
        return _too_many(request)
    s = _surat_by_lacak(request, token)
    w = s.wilayah
    if not (s.is_issued and w.warga_boleh_cetak and w.serves_public):
        raise Http404
    return printing.render_letter(
        request, s, w, images_url=lambda kind: reverse("warga:lacak-gambar", args=[token, kind]), draft=False,
    )


@require_safe
def lacak_gambar(request, token: str, kind: str):
    s = _surat_by_lacak(request, token)
    w = s.wilayah
    if not (s.is_issued and w.warga_boleh_cetak and w.serves_public):
        raise Http404
    field = {"ttd": w.ttd, "cap": w.cap}.get(kind)
    if not field:
        raise Http404
    return _private(serve_private(field))


@require_safe
def cek(request, token: str):
    """Halaman keaslian dari QR di surat: hanya data minimal & tersamar."""
    if not ratelimit.allow(f"cek-surat:{ip_hash(request)}", limit=60, window=600):
        return _too_many(request)
    if not TOKEN_RE.match(token or ""):
        raise Http404
    s = Surat.objects.select_related("wilayah").filter(verify_token=token, status=Surat.STATUS_ISSUED).first()
    if s is None or s.wilayah.state() == STATE_DELETED:
        raise Http404
    return _page(request, "warga/cek.html", {"s": s, "w": s.wilayah, "page_title": "Cek keaslian surat"})
