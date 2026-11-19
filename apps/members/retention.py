"""Penghapusan data yang sudah lewat masa simpannya (lihat Kebijakan Privasi)."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from .models import MemberSession, Order

log = logging.getLogger("hans")


def purge_old_orders(now=None) -> int:
    """Pesanan (dan bukti bayar) yang lebih tua dari 10 tahun dihapus permanen."""
    now = now or timezone.now()
    limit = now - timedelta(days=round(365.25 * Order.RETENTION_YEARS))
    count = 0
    for order in Order.objects.filter(created_at__lt=limit):
        order.delete()  # signal ikut menghapus file bukti bayar
        count += 1
    if count:
        log.info("%s pesanan berumur lebih dari %s tahun dihapus permanen.", count, Order.RETENTION_YEARS)
    return count


def purge_expired_sessions(now=None) -> int:
    return MemberSession.objects.filter(expires_at__lt=now or timezone.now()).delete()[0]
