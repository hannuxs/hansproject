"""Backup database: hanya tabel aplikasi (hp_*), dikompres, nama bertanggal, rotasi otomatis."""
from __future__ import annotations

import gzip
import shutil
import subprocess  # nosec B404 - menjalankan mariadb-dump dengan argumen tetap (tanpa shell)
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core import mariadb

BACKUP_PATTERN = "hansproject-*.sql.gz"


class Command(BaseCommand):
    help = "Backup tabel aplikasi (berawalan hp_) ke folder backups, lalu hapus backup lama."

    def add_arguments(self, parser):
        parser.add_argument("--label", default="", help="Tambahan nama file, misalnya 'sebelum-update'.")

    def handle(self, *args, **options):
        path = run_backup(label=options["label"])
        size_kb = path.stat().st_size // 1024
        self.stdout.write(self.style.SUCCESS(f"Backup berhasil: {path} ({size_kb} KB)"))
        removed = rotate_backups()
        if removed:
            self.stdout.write(f"Backup lama dihapus: {removed} file.")


def run_backup(label: str = "") -> Path:
    tables = mariadb.app_tables()
    if not tables:
        raise CommandError("Belum ada tabel aplikasi di database. Jalankan migrasi dulu.")
    try:
        dump = mariadb.find_tool("mariadb-dump", "mysqldump")
    except mariadb.MariaDBToolError as exc:
        raise CommandError(str(exc)) from exc

    backup_dir = Path(settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_label = "".join(ch for ch in label.lower() if ch.isalnum() or ch == "-")[:30]
    name = f"hansproject-{stamp}{'-' + safe_label if safe_label else ''}.sql.gz"
    target = backup_dir / name
    partial = target.with_suffix(".partial")

    with mariadb.credentials_file() as cnf:
        cmd = [
            dump, f"--defaults-extra-file={cnf}",
            "--single-transaction", "--quick", "--no-tablespaces", "--hex-blob",
            "--add-drop-table", "--skip-comments", "--default-character-set=utf8mb4",
            settings.DATABASES["default"]["NAME"], *tables,
        ]
        with gzip.open(partial, "wb") as out:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # nosec B603
            if proc.stdout is None:  # pragma: no cover
                raise CommandError("Gagal menjalankan mariadb-dump.")
            shutil.copyfileobj(proc.stdout, out)
            _, err = proc.communicate()
    if proc.returncode != 0:
        partial.unlink(missing_ok=True)
        message = err.decode("utf-8", "replace").strip().splitlines()
        raise CommandError("Backup gagal: " + (message[-1] if message else "mariadb-dump error"))
    partial.replace(target)
    return target


def rotate_backups() -> int:
    """Simpan maksimal BACKUP_KEEP file terbaru dan hapus yang lebih tua dari BACKUP_MAX_DAYS hari."""
    files = sorted(Path(settings.BACKUP_DIR).glob(BACKUP_PATTERN), key=lambda p: p.stat().st_mtime, reverse=True)
    max_age = settings.BACKUP_MAX_DAYS * 86400
    now = time.time()
    removed = 0
    for index, file in enumerate(files):
        too_many = index >= settings.BACKUP_KEEP
        too_old = index > 0 and now - file.stat().st_mtime > max_age  # backup terbaru selalu disimpan
        if too_many or too_old:
            file.unlink(missing_ok=True)
            removed += 1
    return removed
