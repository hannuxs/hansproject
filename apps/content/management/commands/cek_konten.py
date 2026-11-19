"""Menampilkan data yang masih berupa contoh (placeholder) dan perlu diisi pemilik."""
from django.core.management.base import BaseCommand
from django.db import DatabaseError

from apps.content.checks import placeholder_reminders


class Command(BaseCommand):
    help = "Tampilkan daftar isian yang masih contoh (rekening, QRIS, jam kerja, dll.)."

    def handle(self, *args, **options):
        try:
            reminders = placeholder_reminders()
        except DatabaseError as exc:
            self.stderr.write(f"Tidak bisa membaca database: {exc}")
            return
        if not reminders:
            self.stdout.write(self.style.SUCCESS("Semua data utama sudah diisi."))
            return
        self.stdout.write(self.style.WARNING("Masih perlu diisi lewat panel pengelola:"))
        for item in reminders:
            self.stdout.write(f"  - {item.text}")
