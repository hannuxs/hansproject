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
            due = list(services.subscriptions_due_for_deletion())
            count = 0
            for sub in due:
                hosts = [store.subdomain for store in sub.stores.all()]
                count += len(hosts)
                self.stdout.write(f"- Paket {sub.package_name} #{sub.pk}: {', '.join(hosts) or '-'} (aktif sampai {sub.active_until})")
            self.stdout.write(f"{count} toko ({len(due)} langganan) akan dihapus.")
            return
        deleted = services.delete_expired_stores()
        self.stdout.write(self.style.SUCCESS(f"Selesai. {len(deleted)} toko dihapus permanen."))
