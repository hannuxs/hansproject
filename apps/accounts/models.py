from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class AdminUser(AbstractUser):
    """Akun pengelola situs (pemilik)."""

    class Meta:
        db_table = "hp_admin_user"
        verbose_name = "akun admin"
        verbose_name_plural = "akun admin"

    @property
    def has_2fa(self) -> bool:
        device = getattr(self, "totp_device", None)
        return bool(device and device.confirmed_at)


class TwoFactorDevice(models.Model):
    """Kunci TOTP untuk verifikasi dua langkah (Google Authenticator, dll.)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="totp_device")
    secret = models.CharField(max_length=64)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    # Langkah waktu terakhir yang dipakai: mencegah kode yang sama dipakai dua kali.
    last_used_step = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hp_admin_totp"
        verbose_name = "perangkat 2FA"


class LoginAttempt(models.Model):
    """Catatan percobaan masuk panel. IP disimpan dalam bentuk hash, bukan mentah."""

    STAGE_PASSWORD = "password"  # nosec B105 - nama tahap login, bukan password
    STAGE_OTP = "otp"
    STAGES = [(STAGE_PASSWORD, "Password"), (STAGE_OTP, "Kode 2FA")]

    username = models.CharField(max_length=150, db_index=True)
    ip_hash = models.CharField(max_length=32, db_index=True)
    success = models.BooleanField(default=False)
    stage = models.CharField(max_length=10, choices=STAGES, default=STAGE_PASSWORD)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "hp_login_attempt"
        ordering = ["-created_at"]
        verbose_name = "percobaan masuk"
        verbose_name_plural = "percobaan masuk"
