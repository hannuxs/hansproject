"""Isian {kata} pada teks dari panel, misalnya {harga_mulai} di judul utama."""
from __future__ import annotations

import re

_TOKEN = re.compile(r"\{(\w+)\}")


def fill(template: str, **values: str) -> str:
    """Ganti {kata} dengan nilainya. Kata yang tidak dikenal dibiarkan apa adanya.

    Sengaja tidak memakai str.format supaya template dari panel tidak bisa
    mengakses atribut objek Python.
    """
    return _TOKEN.sub(lambda m: str(values.get(m.group(1), m.group(0))), template or "")

