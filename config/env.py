"""Pembaca konfigurasi dari file .env dan environment variable.

Semua rahasia (secret key, password database, dll.) hanya dibaca dari sini,
tidak pernah ditulis langsung di kode.
"""
from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = Path(os.environ.get("HANS_ENV_FILE", BASE_DIR / ".env"))

# Nilai yang sudah ada di environment (misalnya dari service) tidak ditimpa.
load_dotenv(ENV_FILE, override=False, encoding="utf-8")

_TRUE = {"1", "true", "yes", "ya", "on"}
_FALSE = {"0", "false", "no", "tidak", "off"}


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ImproperlyConfigured(f"{name} harus bernilai true atau false (sekarang: {raw!r}).")


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} harus berupa angka (sekarang: {raw!r}).") from exc


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env_str(name, default).split(",") if item.strip()]


def env_path(name: str, default: str) -> Path:
    """Path relatif dianggap relatif terhadap folder proyek."""
    path = Path(env_str(name, default) or default)
    return path if path.is_absolute() else BASE_DIR / path


APP_ENV = env_str("APP_ENV", "development").lower()
