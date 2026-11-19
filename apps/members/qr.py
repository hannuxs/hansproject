"""Kode QR keaslian pesanan (SVG, dibuat di server; tanpa gambar eksternal)."""
from __future__ import annotations

import segno
from django.conf import settings
from django.utils.safestring import mark_safe


def verify_url(order) -> str:
    return settings.SITE_URL + order.verify_path if order.verify_token else ""


def order_qr_svg(order) -> str:
    url = verify_url(order)
    if not url:
        return ""
    # omitsize=True: tanpa width/height tetap, segno memberi viewBox sehingga QR MENGECIL mengikuti
    # kotaknya (bukan terpotong). Alamat produksi lebih panjang -> QR lebih rapat -> harus bisa diskalakan.
    # border=4 = zona tenang standar QR agar mudah dipindai kamera HP.
    svg = segno.make(url, error="m").svg_inline(
        dark="#3B1A12", light="#ffffff", border=4, omitsize=True, svgclass="qr-svg",
    )
    return mark_safe(svg)  # nosec B308 B703 - SVG dibuat segno dari URL milik sendiri
