"""Pemeriksaan konfigurasi tambahan (muncul saat ``manage.py check``)."""
from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def hans_security_checks(app_configs, **kwargs):
    issues = []
    if not settings.ADMIN_REQUIRE_2FA:
        issues.append(
            Warning(
                "Verifikasi dua langkah (2FA) admin dimatikan.",
                hint="Set ADMIN_REQUIRE_2FA=true di file .env.",
                id="hans.W001",
            )
        )
    if settings.ADMIN_URL_PATH in settings.WEAK_ADMIN_PATHS:
        issues.append(
            Warning(
                "Alamat panel pengelola mudah ditebak.",
                hint="Ganti ADMIN_URL_PATH di .env dengan alamat acak.",
                id="hans.W002",
            )
        )
    if settings.ADMIN_SESSION_MINUTES > 120:
        issues.append(
            Warning(
                "Batas waktu sesi admin lebih dari 2 jam.",
                hint="Disarankan ADMIN_SESSION_MINUTES=30.",
                id="hans.W003",
            )
        )
    return issues
