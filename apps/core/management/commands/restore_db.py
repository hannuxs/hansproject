"""Mengembalikan database dari file backup (hanya tabel aplikasi hp_*)."""
from __future__ import annotations

import gzip
import subprocess  # nosec B404 - menjalankan klien mariadb dengan argumen tetap (tanpa shell)
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from apps.core import mariadb

from .backup_db import run_backup


def _open(path: Path):
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open("r", encoding="utf-8")


class Command(BaseCommand):
    help = "Mengembalikan tabel aplikasi dari file backup (.sql.gz). Tabel lain di database tidak disentuh."

    def add_arguments(self, parser):
        parser.add_argument("file", nargs="?", help="Path file backup. Kosongkan untuk melihat daftar backup.")
        parser.add_argument("--ya", action="store_true", help="Lewati konfirmasi (hati-hati).")

    def handle(self, *args, **options):
        backup_dir = Path(settings.BACKUP_DIR)
        if not options["file"]:
            files = sorted(backup_dir.glob("hansproject-*.sql.gz"), reverse=True)
            if not files:
                self.stdout.write("Belum ada file backup di folder backups.")
                return
            self.stdout.write("File backup yang tersedia (terbaru di atas):")
            for f in files[:30]:
                self.stdout.write(f"  {f.name}  ({f.stat().st_size // 1024} KB)")
            return

        path = Path(options["file"])
        if not path.is_absolute() and not path.exists():
            path = backup_dir / path
        if not path.is_file():
            raise CommandError(f"File tidak ditemukan: {path}")

        with _open(path) as handle:
            foreign = mariadb.foreign_tables_in_dump(handle)
        if foreign:
            raise CommandError(
                "File ini berisi perintah untuk tabel/database di luar aplikasi ini dan DITOLAK demi keamanan "
                f"data lain: {', '.join(sorted(foreign))}"
            )

        db_name = settings.DATABASES["default"]["NAME"]
        self.stdout.write(self.style.WARNING(
            f"\nPERHATIAN: semua tabel aplikasi (hp_*) di database '{db_name}' akan DITIMPA dengan isi file:\n"
            f"  {path}\nTabel lain di database tersebut tidak disentuh."
        ))
        if not options["ya"]:
            answer = input("Ketik YA (huruf besar) untuk melanjutkan: ").strip()
            if answer != "YA":
                self.stdout.write("Dibatalkan. Tidak ada yang diubah.")
                return

        self.stdout.write("Membuat backup pengaman dari kondisi sekarang...")
        try:
            safety = run_backup(label="sebelum-restore")
            self.stdout.write(f"  Backup pengaman: {safety}")
        except CommandError as exc:
            self.stdout.write(self.style.WARNING(f"  Backup pengaman dilewati: {exc}"))

        client = mariadb.find_tool("mariadb", "mysql")
        with mariadb.credentials_file() as cnf:
            cmd = [client, f"--defaults-extra-file={cnf}", "--default-character-set=utf8mb4", db_name]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)  # nosec B603
            if proc.stdin is None:  # pragma: no cover
                raise CommandError("Gagal menjalankan klien mariadb.")
            opener = gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")
            with opener as src:
                while chunk := src.read(1024 * 256):
                    proc.stdin.write(chunk)
            _, err = proc.communicate()
        if proc.returncode != 0:
            message = err.decode("utf-8", "replace").strip().splitlines()
            raise CommandError("Restore gagal: " + (message[-1] if message else "mariadb error"))
        cache.clear()
        self.stdout.write(self.style.SUCCESS("Restore selesai. Jalankan 'migrate' bila file backup berasal dari versi lama."))
