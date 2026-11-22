"""Login kasir di subdomain toko (``<toko>.hansproject.app/kasir/``).

- Satu toko = satu akun kasir: nama pengguna + PIN 6 angka, dibuat pemilik toko di
  hansproject.app. Akun yang sama boleh masuk di banyak perangkat sekaligus.
- PIN disimpan sebagai hash (Argon2), tidak pernah disimpan apa adanya.
- 5 kali salah: akun terkunci 15 menit. Ditambah batas percobaan per alamat IP.
- Cookie ``hp_kasir`` TANPA atribut Domain, jadi hanya berlaku di subdomain
  toko itu sendiri (tidak terkirim ke toko lain atau ke hansproject.app).
- Sesi juga diperiksa milik toko yang sedang dibuka, jadi cookie dari toko lain
  tidak berguna.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from .models import Cashier, CashierSession, Store

COOKIE = "hp_kasir"
SESSION_DAYS = 7
REFRESH_EVERY = timedelta(hours=1)
MAX_FAILURES = 5
LOCK_MINUTES = 15
_DUMMY_HASH = None


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", "ignore")).hexdigest()


def _lifetime() -> timedelta:
    return timedelta(days=SESSION_DAYS)


def set_pin(cashier: Cashier, pin: str) -> None:
    """Simpan PIN baru. Semua perangkat yang sedang login dengan akun ini ikut keluar."""
    cashier.pin_hash = make_password(pin)
    cashier.failed_count = 0
    cashier.locked_until = None
    if cashier.pk:
        cashier.sessions.all().delete()


def _dummy_check(pin: str) -> None:
    """Samakan waktu proses walau nama pengguna tidak ada (cegah menebak nama pengguna)."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = make_password("000000-dummy")
    check_password(pin, _DUMMY_HASH)


class LoginResult:
    def __init__(self, cashier: Cashier | None = None, error: str = ""):
        self.cashier = cashier
        self.error = error


def authenticate(store: Store, username: str, pin: str) -> LoginResult:
    generic = "Nama pengguna atau PIN salah."
    username = (username or "").strip().lower()
    cashier = Cashier.objects.filter(store=store, username=username, is_active=True, store__is_active=True).first()
    if cashier is None:
        _dummy_check(pin)
        return LoginResult(error=generic)
    if cashier.is_locked:
        minutes = max(1, int((cashier.locked_until - timezone.now()).total_seconds() // 60) + 1)
        return LoginResult(error=f"Terlalu banyak PIN salah. Akun ini terkunci sementara, coba lagi {minutes} menit lagi.")
    if not check_password(pin, cashier.pin_hash):
        cashier.failed_count += 1
        if cashier.failed_count >= MAX_FAILURES:
            cashier.locked_until = timezone.now() + timedelta(minutes=LOCK_MINUTES)
            cashier.failed_count = 0
        cashier.save(update_fields=["failed_count", "locked_until"])
        return LoginResult(error=generic)
    return LoginResult(cashier=cashier)


def _set_cookie(response, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(_lifetime().total_seconds()),
        path="/",
        secure=settings.MEMBER_COOKIE_SECURE,
        httponly=True,
        samesite="Strict",
    )


def login(request, response, cashier: Cashier) -> None:
    now = timezone.now()
    token = secrets.token_urlsafe(32)
    CashierSession.objects.create(cashier=cashier, key_hash=_hash(token), last_seen_at=now, expires_at=now + _lifetime())
    Cashier.objects.filter(pk=cashier.pk).update(last_login_at=now, failed_count=0, locked_until=None)
    _set_cookie(response, token)
    request._cashier = cashier


def logout(request, response) -> None:
    if token := request.COOKIES.get(COOKIE):
        CashierSession.objects.filter(key_hash=_hash(token)).delete()
    response.delete_cookie(COOKIE, path="/", samesite="Strict")
    request._cashier = None


def get_cashier(request, store: Store) -> Cashier | None:
    if hasattr(request, "_cashier"):
        return request._cashier
    cashier = None
    token = request.COOKIES.get(COOKIE, "")
    if 20 <= len(token) <= 100:
        now = timezone.now()
        session = (
            CashierSession.objects.select_related("cashier")
            .filter(
                key_hash=_hash(token),
                expires_at__gt=now,
                cashier__store=store,
                cashier__is_active=True,
                cashier__store__is_active=True,
            )
            .first()
        )
        if session:
            cashier = session.cashier
            cashier.store = store  # objek toko yang sama dengan request ini
            if now - session.last_seen_at > REFRESH_EVERY:
                CashierSession.objects.filter(pk=session.pk).update(last_seen_at=now, expires_at=now + _lifetime())
                request._cashier_refresh = token
    request._cashier = cashier
    return cashier


def finish_response(request, response):
    if getattr(request, "_cashier_refresh", None) and getattr(request, "_cashier", None):
        _set_cookie(response, request._cashier_refresh)
    elif request.COOKIES.get(COOKIE) and getattr(request, "_cashier", "unset") is None:
        response.delete_cookie(COOKIE, path="/", samesite="Strict")
    return response
