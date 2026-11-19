"""Alat kecil untuk membuat & mengisi file .env (tanpa Django).

Contoh:
    python scripts/envtool.py init --mode production
    python scripts/envtool.py init --mode development --db-port 3309
    python scripts/envtool.py get ADMIN_URL_PATH
    python scripts/envtool.py set DB_PORT=3307

Nilai yang sudah diisi pemilik TIDAK pernah ditimpa (kecuali lewat "set").
"""
from __future__ import annotations

import argparse
import re
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"

PLACEHOLDERS = {"", "ganti-alamat-panel-ini"}
_LINE = re.compile(r"^\s*([A-Z0-9_]+)\s*=(.*)$")


def read_env(path: Path = ENV) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _LINE.match(line)
            if match:
                values[match.group(1)] = match.group(2).strip().strip('"').strip("'")
    return values


def set_values(updates: dict[str, str], path: Path = ENV) -> None:
    """Ubah/tambah nilai sambil mempertahankan komentar dan urutan baris."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(updates)
    for i, line in enumerate(lines):
        match = _LINE.match(line)
        if match and match.group(1) in pending:
            lines[i] = f"{match.group(1)}={pending.pop(match.group(1))}"
    lines += [f"{k}={v}" for k, v in pending.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def new_secret_key() -> str:
    return secrets.token_urlsafe(64)


def new_admin_path() -> str:
    return "kelola-" + secrets.token_hex(6)


def init(mode: str, db_port: str | None = None) -> None:
    created = False
    if not ENV.exists():
        shutil.copyfile(EXAMPLE, ENV)
        created = True
        print("[OK] File .env dibuat dari .env.example")
    current = read_env()
    updates: dict[str, str] = {}
    if created:
        updates["APP_ENV"] = mode
        if mode == "development":
            updates.update(
                DEBUG="true",
                ALLOWED_HOSTS="127.0.0.1,localhost",
                SITE_URL="http://127.0.0.1:8432",
                STORE_BASE_DOMAIN="localhost",
                SECURE_SSL_REDIRECT="false",
                LOG_TO_FILE="false",
            )
        if db_port:
            updates["DB_PORT"] = db_port
    if current.get("SECRET_KEY", "") in PLACEHOLDERS or len(current.get("SECRET_KEY", "")) < 50:
        updates["SECRET_KEY"] = new_secret_key()
        print("[OK] SECRET_KEY acak dibuat")
    if current.get("ADMIN_URL_PATH", "") in PLACEHOLDERS:
        updates["ADMIN_URL_PATH"] = new_admin_path()
        print("[OK] Alamat panel acak dibuat")
    if updates:
        set_values(updates)
    if not created:
        print("[OK] File .env sudah ada; nilai yang sudah diisi tidak diubah")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--mode", choices=["production", "development"], default="production")
    p_init.add_argument("--db-port")
    p_get = sub.add_parser("get")
    p_get.add_argument("key")
    p_set = sub.add_parser("set")
    p_set.add_argument("pair", help="KUNCI=nilai")
    p_has = sub.add_parser("has", help="exit code 0 bila KUNCI sudah berisi nilai")
    p_has.add_argument("key")
    sub.add_parser("summary", help="tampilkan alamat website & panel")
    sub.add_parser("check-python", help="exit code 1 bila Python terpasang di folder pengguna")
    args = parser.parse_args(argv)

    if args.cmd == "init":
        init(args.mode, args.db_port)
    elif args.cmd == "get":
        print(read_env().get(args.key, ""))
    elif args.cmd == "has":
        return 0 if read_env().get(args.key, "") not in PLACEHOLDERS else 1
    elif args.cmd == "summary":
        env = read_env()
        site = env.get("SITE_URL", "https://hansproject.app").rstrip("/")
        print(f"  Website     : {site}/")
        print(f"  Panel admin : {site}/{env.get('ADMIN_URL_PATH', '')}/   (RAHASIAKAN)")
        print(f"  Database    : {env.get('DB_NAME', '')} di {env.get('DB_HOST', '')}:{env.get('DB_PORT', '')}")
    elif args.cmd == "check-python":
        # Windows Service (akun terbatas) tidak bisa membaca Python di C:\Users\...
        return 1 if "\\users\\" in sys.base_prefix.lower() else 0
    elif args.cmd == "set":
        key, _, value = args.pair.partition("=")
        if not re.fullmatch(r"[A-Z0-9_]+", key):
            print("Nama kunci tidak valid", file=sys.stderr)
            return 2
        set_values({key: value})
        print(f"[OK] {key} diperbarui")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
