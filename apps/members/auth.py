"""Sesi login pelanggan.

- Cookie ``hp_akun``: token acak (HttpOnly, Secure di produksi, SameSite=Lax).
  Database hanya menyimpan hash SHA-256-nya, jadi isi database yang bocor
  tidak bisa dipakai untuk masuk.
- Cookie ``hp_masuk=1``: tanda "sedang login" TANPA rahasia, dibaca JavaScript
  untuk mengganti tombol "Daftar / Masuk" menjadi "Profil" di halaman publik
  (halaman publik di-cache sama untuk semua pengunjung).
- Sesi diperpanjang otomatis selama pelanggan aktif; keluar = sesi dihapus.

Sesi ini terpisah total dari sesi panel pengelola (cookie ``hp_panel``).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Member, MemberSession

COOKIE = "hp_akun"
FLAG_COOKIE = "hp_masuk"
REFRESH_EVERY = timedelta(hours=1)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", "ignore")).hexdigest()


def _lifetime() -> timedelta:
    return timedelta(days=settings.MEMBER_SESSION_DAYS)


def _set_cookies(response, token: str) -> None:
    age = int(_lifetime().total_seconds())
    secure = settings.MEMBER_COOKIE_SECURE
    response.set_cookie(COOKIE, token, max_age=age, path="/", secure=secure, httponly=True, samesite="Lax")
    response.set_cookie(FLAG_COOKIE, "1", max_age=age, path="/", secure=secure, httponly=False, samesite="Lax")


def clear_cookies(response) -> None:
    for name in (COOKIE, FLAG_COOKIE):
        response.delete_cookie(name, path="/", samesite="Lax")


def login(request, response, member: Member) -> None:
    now = timezone.now()
    MemberSession.objects.filter(expires_at__lt=now).delete()  # bersih-bersih sesi kedaluwarsa
    token = secrets.token_urlsafe(32)
    MemberSession.objects.create(member=member, key_hash=_hash(token), last_seen_at=now, expires_at=now + _lifetime())
    Member.objects.filter(pk=member.pk).update(last_login_at=now)
    _set_cookies(response, token)
    request._member = member


def logout(request, response, *, everywhere: bool = False) -> None:
    member = get_member(request)
    if member and everywhere:
        member.sessions.all().delete()
    elif token := request.COOKIES.get(COOKIE):
        MemberSession.objects.filter(key_hash=_hash(token)).delete()
    clear_cookies(response)
    request._member = None


def get_member(request) -> Member | None:
    """Pelanggan yang sedang login (atau None). Hasilnya disimpan di request."""
    if hasattr(request, "_member"):
        return request._member
    member = None
    token = request.COOKIES.get(COOKIE, "")
    if 20 <= len(token) <= 100:
        now = timezone.now()
        session = (
            MemberSession.objects.select_related("member")
            .filter(key_hash=_hash(token), expires_at__gt=now, member__is_active=True)
            .first()
        )
        if session:
            member = session.member
            if now - session.last_seen_at > REFRESH_EVERY:
                MemberSession.objects.filter(pk=session.pk).update(last_seen_at=now, expires_at=now + _lifetime())
                request._member_refresh = token
    request._member = member
    return member


def finish_response(request, response):
    """Perbarui umur cookie bila sesi diperpanjang; hapus cookie bila sesinya sudah tidak berlaku."""
    if getattr(request, "_member_refresh", None) and getattr(request, "_member", None):
        _set_cookies(response, request._member_refresh)
    elif request.COOKIES.get(COOKIE) and getattr(request, "_member", "unset") is None:
        clear_cookies(response)
    elif request.COOKIES.get(FLAG_COOKIE) and not request.COOKIES.get(COOKIE):
        clear_cookies(response)
    return response


def safe_next(request, value: str | None, default: str = "") -> str:
    """Hanya izinkan alamat tujuan di situs ini (cegah open redirect)."""
    default = default or reverse("akun:dashboard")
    if (
        value
        and value.startswith("/")
        and not value.startswith("//")
        and "\\" not in value
        and url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    ):
        return value
    return default


def login_url(next_path: str) -> str:
    return f"{reverse('akun:masuk')}?{urlencode({'next': next_path})}"


def legal_version():
    """Versi Syarat & Ketentuan / Kebijakan Privasi yang berlaku (diatur di panel)."""
    from apps.content import services

    return services.get_snapshot().settings.legal_version


def needs_terms(member: Member) -> bool:
    return member.needs_terms(legal_version())


def member_required(view=None, *, complete_profile: bool = True, require_terms: bool = True):
    """Wajib login.

    - ``require_terms``: wajib sudah menyetujui Syarat & Ketentuan versi terbaru (popup persetujuan).
    - ``complete_profile``: profil (nama, HP, usaha) juga wajib lengkap.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            member = get_member(request)
            if member is None:
                response = redirect(login_url(request.get_full_path()))
            elif require_terms and needs_terms(member):
                response = redirect(f"{reverse('akun:persetujuan')}?{urlencode({'next': request.get_full_path()})}")
            elif complete_profile and not member.profile_complete:
                response = redirect(f"{reverse('akun:lengkapi')}?{urlencode({'next': request.get_full_path()})}")
            else:
                request.member = member
                response = func(request, *args, **kwargs)
            return finish_response(request, response)

        return wrapper

    return decorator(view) if view else decorator
