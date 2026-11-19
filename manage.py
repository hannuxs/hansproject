#!/usr/bin/env python
"""Perintah administrasi Django untuk HANS Project."""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Django tidak ditemukan. Pastikan virtual environment (.venv) sudah aktif "
            "dan dependensi sudah dipasang (jalankan install.bat / setup-dev.bat)."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
