"""Format angka & harga gaya Indonesia (contoh: Rp25.000, Rp25 ribu)."""
from __future__ import annotations

from decimal import Decimal


def thousands(value: int | float | Decimal) -> str:
    return f"{int(value):,}".replace(",", ".")


def rupiah(value) -> str:
    """25000 -> 'Rp25.000' (tanpa spasi setelah Rp, titik pemisah ribuan)."""
    if value is None or value == "":
        return ""
    return f"Rp{thousands(value)}"


def rupiah_short(value) -> str:
    """25000 -> 'Rp25 ribu', 1500000 -> 'Rp1,5 juta'. Untuk judul yang ringkas."""
    if value is None or value == "":
        return ""
    value = int(value)
    if value >= 1_000_000 and value % 100_000 == 0:
        number = f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"Rp{number} juta"
    if value >= 1_000 and value % 1_000 == 0:
        return f"Rp{thousands(value // 1_000)} ribu"
    return rupiah(value)
