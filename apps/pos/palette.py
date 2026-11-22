"""Palet warna Halaman toko dari SATU warna pilihan pemilik.

Pemilik hanya memilih satu warna. Halaman web butuh lebih banyak: warna tombol yang
cukup kontras dengan teks putih, latar lembut, teks gelap senada, garis, warna aksen
untuk label, dan latar gelap untuk bagian yang menonjol. Semuanya diturunkan di sini
(tidak pernah ditampilkan ke pemilik) dan dikirim sebagai file CSS kecil berisi
variabel ``--hp-*`` (``/_tema/v<versi>/<hex>.css``), jadi tetap patuh CSP tanpa
``style`` inline.

Kontras dihitung dengan rumus WCAG 2.1 (teks normal minimal 4,5 : 1).
"""
from __future__ import annotations

import colorsys
import re
from functools import lru_cache

VERSION = 1  # naikkan bila rumus berubah (alamat CSS ikut berubah, cache lama tidak terpakai)
HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
DEFAULT = "#c2410c"

# Pilihan cepat di editor (pemilik tetap bebas memilih warna lain).
PRESETS = [
    ("#c2410c", "Oranye bata"),
    ("#b91c1c", "Merah cabai"),
    ("#be185d", "Merah muda"),
    ("#7c3aed", "Ungu"),
    ("#1d4ed8", "Biru"),
    ("#0e7490", "Biru laut"),
    ("#15803d", "Hijau daun"),
    ("#a16207", "Kuning kunyit"),
    ("#78350f", "Cokelat kopi"),
    ("#334155", "Abu batu"),
]

RGB = tuple[float, float, float]


def normalize(value: str) -> str | None:
    """'#AbC123' / 'abc123' -> '#abc123'; selain itu None."""
    match = HEX_RE.match((value or "").strip())
    return f"#{match.group(1).lower()}" if match else None


def _rgb(hex_value: str) -> RGB:
    h = hex_value.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(rgb: RGB) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in rgb)


def _hls(h: float, l: float, s: float) -> RGB:
    return colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))


def luminance(rgb: RGB) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: RGB, b: RGB) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


WHITE: RGB = (1.0, 1.0, 1.0)


def _darken_until(h: float, l: float, s: float, against: RGB, ratio: float) -> RGB:
    """Turunkan kecerahan sampai kontras dengan ``against`` mencapai ``ratio``."""
    while l > 0.05:
        rgb = _hls(h, l, s)
        if contrast(rgb, against) >= ratio:
            return rgb
        l -= 0.01
    return _hls(h, 0.05, s)


@lru_cache(maxsize=256)
def build(hex_value: str) -> dict[str, str]:
    """Semua warna turunan (nama variabel tanpa awalan ``--hp-``)."""
    color = normalize(hex_value) or DEFAULT
    h, l, s = colorsys.rgb_to_hls(*_rgb(color))
    neutral = s < 0.12 or l < 0.06 or l > 0.97  # abu-abu / hampir hitam / hampir putih
    if neutral:
        s = min(s, 0.12)
        l = min(max(l, 0.3), 0.45)

    brand = _darken_until(h, min(l, 0.6), max(s, 0.0), WHITE, 4.6)
    bh, bl, bs = colorsys.rgb_to_hls(*brand)
    vivid = _hls(h, min(max(l, 0.42), 0.62), s if neutral else max(s, 0.55))
    tint = min(s, 0.75)

    bg = _hls(h, 0.975, min(tint, 0.55))
    soft = _hls(h, 0.93, min(tint, 0.7))
    ink = _hls(h, 0.13, min(s, 0.3))
    muted = _darken_until(h, 0.42, min(s, 0.16), bg, 4.8)
    line = _hls(h, 0.86, min(s, 0.3))

    # Aksen: warna "teman" (hue bergeser) untuk label & sorotan kecil. Untuk warna netral: kuning keemasan.
    ah, asat = ((0.11, 0.85) if neutral else ((h + 0.42) % 1.0, max(min(s, 0.85), 0.55)))
    accent = _hls(ah, 0.55, asat)
    accent_soft = _hls(ah, 0.92, min(asat, 0.8))
    accent_ink = _darken_until(ah, 0.35, asat, accent_soft, 5.0)

    deep = _hls(h, 0.15, min(max(s, 0.08), 0.6))
    on_deep = _hls(h, 0.96, min(s, 0.45))
    on_deep_muted = _hls(h, 0.78, min(s, 0.3))
    strong = _hls(bh, bl * 0.82, bs)

    return {
        "brand": _hex(brand),
        "brand-strong": _hex(strong),
        "brand-vivid": _hex(vivid),
        "on-brand": "#ffffff",
        "bg": _hex(bg),
        "soft": _hex(soft),
        "surface": "#ffffff",
        "ink": _hex(ink),
        "muted": _hex(muted),
        "line": _hex(line),
        "accent": _hex(accent),
        "accent-soft": _hex(accent_soft),
        "accent-ink": _hex(accent_ink),
        "deep": _hex(deep),
        "on-deep": _hex(on_deep),
        "on-deep-muted": _hex(on_deep_muted),
    }


def css(hex_value: str) -> str:
    colors = build(normalize(hex_value) or DEFAULT)
    body = ";".join(f"--hp-{name}:{value}" for name, value in colors.items())
    grad = f"--hp-grad:linear-gradient(135deg,{colors['brand-vivid']} 0%,{colors['brand']} 55%,{colors['brand-strong']} 100%)"
    return f":root{{{body};{grad}}}\n"
