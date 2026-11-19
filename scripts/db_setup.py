"""Membuat database & user MariaDB KHUSUS aplikasi, lalu menyimpannya ke .env.

Dijalankan oleh install.bat / setup-dev.bat. Meminta user admin MariaDB
(misalnya root) SEKALI SAJA. Password admin tidak disimpan di mana pun.

Yang dilakukan (semuanya aman dijalankan ulang):
  1. CREATE DATABASE IF NOT EXISTS <DB_NAME> (utf8mb4). Database yang sudah
     ada TIDAK dihapus; tabel lain di dalamnya tidak disentuh.
  2. Membuat user <DB_USER> dengan password acak yang kuat.
  3. Memberi hak akses minimum, HANYA ke database tersebut.
  4. Menulis DB_USER & DB_PASSWORD ke file .env.
"""
from __future__ import annotations

import argparse
import getpass
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from envtool import read_env, set_values  # noqa: E402

IDENT = re.compile(r"^[A-Za-z0-9_]{1,64}$")
APP_PRIVILEGES = "SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES, LOCK TABLES"


def ask(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", action="store_true", help="Izinkan juga database tes (test_<nama>) untuk pengembangan.")
    args = parser.parse_args(argv)

    try:
        import MySQLdb
    except ImportError:
        print("[GAGAL] Driver mysqlclient belum terpasang. Jalankan install.bat dulu.")
        return 1

    env = read_env()
    host = env.get("DB_HOST") or "127.0.0.1"
    port = int(env.get("DB_PORT") or 3307)
    db_name = env.get("DB_NAME") or "hansproject_web"
    app_user = env.get("DB_USER") or "hansproject_app"
    if app_user.lower() == "root":
        app_user = "hansproject_app"

    print("\n=== Menyiapkan database MariaDB ===")
    print(f"Server: {host}:{port}")
    db_name = ask("Nama database untuk website", db_name)
    app_user = ask("Nama user khusus aplikasi", app_user)
    if not IDENT.match(db_name) or not IDENT.match(app_user):
        print("[GAGAL] Nama database/user hanya boleh huruf, angka, dan garis bawah.")
        return 1

    print("\nMasukkan akun ADMIN MariaDB (misalnya root) untuk membuat database & user.")
    print("Password ini hanya dipakai sekarang dan TIDAK disimpan.")
    admin_user = ask("User admin MariaDB", "root")
    admin_pass = getpass.getpass("Password admin MariaDB (tidak terlihat saat diketik): ")

    try:
        conn = MySQLdb.connect(host=host, port=port, user=admin_user, passwd=admin_pass, charset="utf8mb4")
    except MySQLdb.Error as exc:
        print(f"[GAGAL] Tidak bisa masuk ke MariaDB: {exc.args[-1] if exc.args else exc}")
        return 1
    del admin_pass  # tidak disimpan di mana pun

    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s", (db_name,)
    )
    tables = [row[0] for row in cur.fetchall()]
    own = [t for t in tables if t.startswith("hp_")]
    if tables:
        print(f"[INFO] Database '{db_name}' sudah berisi {len(tables)} tabel "
              f"({len(own)} milik website ini, {len(tables) - len(own)} tabel lain).")
        print("       Tabel lain TIDAK disentuh. Semua tabel website memakai awalan hp_.")
    else:
        print(f"[OK] Database '{db_name}' siap (masih kosong).")

    password = secrets.token_urlsafe(32)
    cur.execute("SELECT COUNT(*) FROM mysql.user WHERE User = %s", (app_user,))
    exists = cur.fetchone()[0] > 0
    for user_host in ("localhost", "127.0.0.1"):
        if exists:
            cur.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s", (app_user, user_host, password))
            cur.execute("ALTER USER %s@%s IDENTIFIED BY %s", (app_user, user_host, password))
        else:
            cur.execute("CREATE USER %s@%s IDENTIFIED BY %s", (app_user, user_host, password))
        cur.execute(f"GRANT {APP_PRIVILEGES} ON `{db_name}`.* TO %s@%s", (app_user, user_host))
        if args.dev:
            test_db = f"test_{db_name}".replace("_", r"\_")
            cur.execute(f"GRANT ALL PRIVILEGES ON `{test_db}`.* TO %s@%s", (app_user, user_host))
    cur.execute("FLUSH PRIVILEGES")
    conn.commit()
    conn.close()
    print(f"[OK] User '{app_user}' {'diperbarui' if exists else 'dibuat'} dengan password acak "
          f"(hak akses hanya ke database '{db_name}').")

    set_values({"DB_HOST": host, "DB_PORT": str(port), "DB_NAME": db_name, "DB_USER": app_user, "DB_PASSWORD": password})
    print("[OK] Kredensial database disimpan ke file .env")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nDibatalkan.")
        sys.exit(1)
