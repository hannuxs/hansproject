"""Geometri grafik kecil untuk Dashboard (SVG tanpa style inline, aman untuk CSP ketat).

Spesifikasi batang (dataviz): lebar <= 24px, ujung atas membulat 4px dan rata di dasar,
celah antarbatang, garis dasar tipis, label angka hanya di nilai tertinggi.
"""
from __future__ import annotations

SLOT = 24  # lebar satu hari (px dalam viewBox)
BAR = 16  # lebar batang; sisanya celah
HEIGHT = 120  # tinggi area grafik
TOP_PAD = 18  # ruang label di atas batang tertinggi
RADIUS = 4


def compact_rupiah(value: int) -> str:
    """1.944.000 -> 'Rp1,9 jt'; 370.000 -> 'Rp370 rb'; 900 -> 'Rp900'."""
    if value >= 1_000_000:
        return "Rp" + f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " jt"
    if value >= 1_000:
        return f"Rp{round(value / 1_000)} rb"
    return f"Rp{value}"


def _bar_path(x: float, base: float, height: float) -> str:
    if height <= 0:
        return ""
    r = min(RADIUS, height, BAR / 2)
    top = base - height
    return (
        f"M{x:.1f},{base:.1f} V{top + r:.1f} Q{x:.1f},{top:.1f} {x + r:.1f},{top:.1f} "
        f"H{x + BAR - r:.1f} Q{x + BAR:.1f},{top:.1f} {x + BAR:.1f},{top + r:.1f} V{base:.1f} Z"
    )


def trend_bars(trend: list[dict], peak: int) -> dict:
    base = HEIGHT + TOP_PAD
    bars = []
    peak_index = max(range(len(trend)), key=lambda i: trend[i]["total"]) if trend and peak else None
    for i, item in enumerate(trend):
        h = (item["total"] / peak) * HEIGHT if peak else 0
        if item["total"] and h < 2:
            h = 2  # penjualan kecil tetap terlihat
        x = i * SLOT + (SLOT - BAR) / 2
        bars.append({
            "day": item["day"],
            "total": item["total"],
            "path": _bar_path(x, base, h),
            "hit_x": i * SLOT,
            # Label puncak dijaga tetap di dalam grafik (tidak terpotong di tepi).
            "label_x": min(max(x + BAR / 2, 26), len(trend) * SLOT - 26),
            "label_y": base - h - 6,
            "is_peak": i == peak_index,
            "peak_text": compact_rupiah(item["total"]) if i == peak_index else "",
            "show_date": i in (0, len(trend) // 2, len(trend) - 1),
        })
    return {"bars": bars, "width": len(trend) * SLOT, "height": base + 2, "base": base, "slot": SLOT}
