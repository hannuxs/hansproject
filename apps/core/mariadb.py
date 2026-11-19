"""Bantuan untuk alat bawaan MariaDB (mariadb-dump / mariadb) tanpa membocorkan password.

Password TIDAK pernah ditulis di command line (yang bisa terlihat di daftar
proses). Kredensial ditulis sementara ke file opsi di folder ``run/`` lalu
langsung dihapus setelah perintah selesai.
"""
from __future__ import annotations

import glob
import os
import re
import secrets
import shutil
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.db import connection

TABLE_NAME = re.compile(r"`([^`]+)`")


class MariaDBToolError(RuntimeError):
    pass


def find_tool(*names: str) -> str:
    """Cari program MariaDB: MARIADB_BIN_DIR di .env, PATH, lalu folder instalasi umum."""
    folders: list[str] = []
    if settings.MARIADB_BIN_DIR:
        folders.append(settings.MARIADB_BIN_DIR)
    folders += sorted(glob.glob(r"C:\Program Files\MariaDB*\bin"), reverse=True)
    for name in names:
        exe = name + (".exe" if os.name == "nt" else "")
        for folder in folders:
            candidate = Path(folder) / exe
            if candidate.is_file():
                return str(candidate)
        found = shutil.which(name)
        if found:
            return found
    raise MariaDBToolError(
        f"Program {names[0]} tidak ditemukan. Isi MARIADB_BIN_DIR di .env dengan folder bin MariaDB, "
        r"contoh: C:\Program Files\MariaDB 11.4\bin"
    )


def _quote(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


@contextmanager
def credentials_file():
    """File opsi [client] sementara berisi kredensial database (dihapus otomatis)."""
    db = settings.DATABASES["default"]
    run_dir = Path(settings.RUN_DIR)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f".db-{secrets.token_hex(8)}.cnf"
    content = (
        "[client]\n"
        f"host={_quote(db['HOST'] or '127.0.0.1')}\n"
        f"port={int(db['PORT'] or 3307)}\n"
        f"user={_quote(db['USER'])}\n"
        f"password={_quote(db['PASSWORD'])}\n"
        "default-character-set=utf8mb4\n"
    )
    if (db["HOST"] or "127.0.0.1") in ("127.0.0.1", "localhost", "::1"):
        # Klien MariaDB 11.4+ secara bawaan mewajibkan SSL. Koneksi ke komputer yang sama
        # tidak lewat jaringan, jadi SSL dimatikan agar backup/restore tetap jalan.
        content += "skip-ssl\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        yield str(path)
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def app_tables() -> list[str]:
    """Hanya tabel milik aplikasi ini (berawalan hp_). Tabel lain tidak pernah disentuh."""
    prefix = settings.DB_TABLE_PREFIX
    return sorted(t for t in connection.introspection.table_names() if t.startswith(prefix))


def foreign_tables_in_dump(lines) -> set[str]:
    """Nama tabel di file dump yang BUKAN milik aplikasi ini (untuk mencegah restore berbahaya)."""
    prefix = settings.DB_TABLE_PREFIX
    foreign: set[str] = set()
    pattern = re.compile(
        r"^(?:DROP TABLE(?: IF EXISTS)?|CREATE TABLE(?: IF NOT EXISTS)?|INSERT INTO|REPLACE INTO|"
        r"LOCK TABLES|ALTER TABLE|TRUNCATE(?: TABLE)?|DELETE FROM|UPDATE)\s+`([^`]+)`",
        re.IGNORECASE,
    )
    for line in lines:
        match = pattern.match(line.lstrip("/*!0123456789 "))
        if match and not match.group(1).startswith(prefix):
            foreign.add(match.group(1))
        if re.match(r"^\s*(CREATE|DROP)\s+DATABASE|^\s*USE\s", line, re.IGNORECASE):
            foreign.add("(perintah database)")
    return foreign
