"""Cek koneksi ke MariaDB dan tampilkan ringkasan (tanpa menampilkan password)."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from apps.core import mariadb


class Command(BaseCommand):
    help = "Cek koneksi ke database MariaDB."

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        target = f"{db['USER']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
            tables = connection.introspection.table_names()
        except DatabaseError as exc:
            raise CommandError(f"Tidak bisa terhubung ke database ({target}): {exc.args[-1] if exc.args else exc}") from exc
        own = mariadb.app_tables()
        self.stdout.write(self.style.SUCCESS(f"Terhubung ke MariaDB {version} ({target})."))
        self.stdout.write(f"Tabel aplikasi (hp_*): {len(own)}. Tabel lain di database ini: {len(tables) - len(own)} (tidak disentuh).")
