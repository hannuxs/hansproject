"""Pembatas jumlah request sederhana (fixed window) berbasis cache."""
from __future__ import annotations

import time

from django.core.cache import cache


def allow(key: str, *, limit: int, window: int) -> bool:
    """Kembalikan True bila request masih di bawah batas ``limit`` per ``window`` detik."""
    bucket = f"rl:{key}:{int(time.time() // window)}"
    if cache.add(bucket, 1, window + 5):
        return True
    try:
        count = cache.incr(bucket)
    except ValueError:  # kunci kedaluwarsa di antara add() dan incr()
        cache.set(bucket, 1, window + 5)
        return True
    return count <= limit
