"""Hapus permanen data toko yang tidak diperpanjang lebih dari 30 hari.

Dijalankan otomatis setiap malam oleh ``backup.bat /auto`` (setelah backup),
atau manual: ``manage.py pos_bersihkan``. Pakai ``--cek`` untuk melihat daftar tanpa menghapus.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.pos import services


class Command(BaseCommand):
    help = "Hapus permanen data toko yang masa aktifnya habis lebih dari 30 hari (aturan pemilik)."

    def add_arguments(self, parser):
        parser.add_argument("--cek", action="store_true", help="Hanya tampilkan toko yang akan dihapus.")

    def handle(self, *args, **options):
        if options["cek"]:
            due = list(services.stores_due_for_deletion())
            for store in due:
                self.stdout.write(f"- {store.subdomain} (aktif sampai {store.active_until})")
            self.stdout.write(f"{len(due)} toko akan dihapus.")
            return
        deleted = services.delete_expired_stores()
        self.stdout.write(self.style.SUCCESS(f"Selesai. {len(deleted)} toko dihapus permanen."))
