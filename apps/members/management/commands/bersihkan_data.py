"""Hapus permanen data yang sudah lewat masa simpannya, sesuai Kebijakan Privasi.

- Toko kasir yang masa aktifnya habis lebih dari 30 hari.
- Wilayah SIM (data warga, scan KK/KTP, surat) yang masa aktifnya habis lebih dari 30 hari.
- Pesanan & bukti bayar yang lebih tua dari 10 tahun.
- Sesi login yang sudah kedaluwarsa.

Dijalankan otomatis oleh ``backup.bat /auto`` setelah backup berhasil.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.members import retention
from apps.pos import services as pos_services
from apps.sim import services as sim_services


class Command(BaseCommand):
    help = "Hapus permanen data yang sudah lewat masa simpannya (toko, wilayah SIM, pesanan lama, sesi)."

    def handle(self, *args, **options):
        stores = pos_services.delete_expired_stores()
        wilayah = sim_services.delete_expired_wilayah()
        orders = retention.purge_old_orders()
        sessions = retention.purge_expired_sessions()
        self.stdout.write(
            self.style.SUCCESS(
                f"Selesai. {len(stores)} toko, {len(wilayah)} wilayah SIM, {orders} pesanan lama, dan {sessions} sesi kedaluwarsa dihapus."
            )
        )
