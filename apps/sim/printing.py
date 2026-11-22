"""Tampilan cetak surat (A4) dari browser: kop, isi rapi, tanda tangan, mengetahui, QR keaslian.

Dicetak lewat fitur "Cetak / Simpan sebagai PDF" di browser, jadi tidak butuh pustaka PDF
dan bisa dipakai dari HP, laptop, atau komputer kantor mana saja.
"""
from __future__ import annotations

import segno
from django.conf import settings
from django.shortcuts import render
from django.utils.safestring import mark_safe

from . import services


def verify_url(surat) -> str:
    return settings.SITE_URL + surat.verify_path


def qr_svg(url: str) -> str:
    svg = segno.make(url, error="m").svg_inline(dark="#111111", light="#ffffff", border=2, omitsize=True, svgclass="qr-svg")
    return mark_safe(svg)  # nosec B308 B703 - SVG dibuat segno dari URL milik sendiri


def render_letter(request, surat, wilayah, *, images_url, draft: bool, sample: bool = False, status: int = 200):
    """``images_url(kind)`` -> URL gambar tanda tangan/cap, atau None bila gambar tidak boleh tampil."""
    text = surat.isi or (services.render_text(surat.jenis.isi, surat, wilayah) if surat.jenis else "")
    show_images = bool(images_url) and request.GET.get("gambar", "1") != "0"
    parent = wilayah.parent if wilayah.parent_id else None
    needs_ack = bool(surat.jenis and surat.jenis.butuh_mengetahui and parent)
    ctx = {
        "s": surat,
        "w": wilayah,
        "kop": wilayah.kop_lines,
        "blocks": services.blocks(text),
        "tanggal": services.format_date(surat.tanggal) if surat.tanggal else "",
        "draft": draft,
        "sample": sample,
        "ttd_url": images_url("ttd") if show_images and wilayah.ttd else "",
        "cap_url": images_url("cap") if show_images and wilayah.cap else "",
        "qr": qr_svg(verify_url(surat)) if surat.is_issued and surat.pk else "",
        "verify_url": verify_url(surat) if surat.is_issued and surat.pk else "",
        "ack": needs_ack or surat.mengetahui,
        "ack_title": surat.mengetahui_jabatan or (parent.signer_title if parent else ""),
        "ack_name": surat.mengetahui_nama if surat.mengetahui == surat.ACK_DONE else "",
    }
    response = render(request, "sim/cetak.html", ctx, status=status)
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
