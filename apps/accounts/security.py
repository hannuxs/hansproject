"""Pembatasan percobaan login dan verifikasi dua langkah (TOTP)."""
from __future__ import annotations

import hmac
import logging
import time
from datetime import timedelta

import pyotp
import segno
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import LoginAttempt, TwoFactorDevice

log = logging.getLogger("hans.security")

TOTP_ISSUER = "HANS Project"
TOTP_INTERVAL = 30
ATTEMPT_RETENTION_DAYS = 90


# ---------------------------------------------------------------------------
# Pembatasan percobaan login
# ---------------------------------------------------------------------------
def lock_remaining_seconds(username: str, ip_hash: str) -> int:
    """Sisa detik penguncian; 0 bila boleh mencoba lagi.

    Dikunci bila dalam jendela waktu ``LOGIN_LOCK_MINUTES`` ada
    ``LOGIN_MAX_FAILURES`` kegagalan untuk username yang sama ATAU dari IP yang sama.
    """
    window = timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
    since = timezone.now() - window
    username = (username or "").strip().lower()[:150]
    failures = LoginAttempt.objects.filter(success=False, created_at__gte=since).filter(
        Q(username=username) | Q(ip_hash=ip_hash)
    )
    recent = list(failures.order_by("-created_at").values_list("created_at", flat=True)[: settings.LOGIN_MAX_FAILURES])
    if len(recent) < settings.LOGIN_MAX_FAILURES:
        return 0
    unlock_at = recent[-1] + window
    return max(0, int((unlock_at - timezone.now()).total_seconds()))


def record_attempt(username: str, ip_hash: str, *, success: bool, stage: str = LoginAttempt.STAGE_PASSWORD) -> None:
    username = (username or "").strip().lower()[:150]
    LoginAttempt.objects.create(username=username, ip_hash=ip_hash, success=success, stage=stage)
    outcome = "BERHASIL" if success else "GAGAL"
    log.info("Login admin %s (tahap=%s, user=%s, ip_hash=%s)", outcome, stage, username or "-", ip_hash)
    if success:
        cutoff = timezone.now() - timedelta(days=ATTEMPT_RETENTION_DAYS)
        LoginAttempt.objects.filter(created_at__lt=cutoff).delete()


# ---------------------------------------------------------------------------
# TOTP (Google Authenticator, Microsoft Authenticator, Aegis, dll.)
# ---------------------------------------------------------------------------
def new_secret() -> str:
    return pyotp.random_base32(length=32)


def provisioning_uri(username: str, secret: str) -> str:
    return pyotp.TOTP(secret, interval=TOTP_INTERVAL).provisioning_uri(name=username, issuer_name=TOTP_ISSUER)


def qr_svg(uri: str) -> str:
    """Kode QR sebagai SVG inline (tanpa atribut style, aman untuk CSP)."""
    return segno.make(uri, error="m").svg_inline(dark="#3B1A12", light="#ffffff", border=4, omitsize=True)


def _normalize(code: str) -> str:
    return "".join(ch for ch in (code or "") if ch.isdigit())


def verify_code(device: TwoFactorDevice, code: str) -> bool:
    """Cek kode 6 digit (toleransi ±30 detik) dan tolak kode yang sudah pernah dipakai."""
    code = _normalize(code)
    if len(code) != 6:
        return False
    totp = pyotp.TOTP(device.secret, interval=TOTP_INTERVAL)
    now_step = int(time.time()) // TOTP_INTERVAL
    for step in (now_step - 1, now_step, now_step + 1):
        if step <= device.last_used_step:
            continue
        if hmac.compare_digest(totp.at(step * TOTP_INTERVAL), code):
            device.last_used_step = step
            device.save(update_fields=["last_used_step"])
            return True
    return False
