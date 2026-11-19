"""Hapus permanen data yang sudah lewat masa simpannya, sesuai Kebijakan Privasi.

- Toko kasir yang masa aktifnya habis lebih dari 30 hari.
- Pesanan & bukti bayar yang lebih tua dari 10 tahun.
- Sesi login yang sudah kedaluwarsa.

Dijalankan otomatis oleh ``backup.bat /auto`` setelah backup berhasil.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.members import retention
from apps.pos import services as pos_services


class Command(BaseCommand):
    help = "Hapus permanen data yang sudah lewat masa simpannya (toko, pesanan lama, sesi)."

    def handle(self, *args, **options):
        stores = pos_services.delete_expired_stores()
        orders = retention.purge_old_orders()
        sessions = retention.purge_expired_sessions()
        self.stdout.write(
            self.style.SUCCESS(
                f"Selesai. {len(stores)} toko, {orders} pesanan lama, dan {sessions} sesi kedaluwarsa dihapus."
            )
        )
