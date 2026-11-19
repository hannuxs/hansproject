"""Bantuan bersama untuk tes."""
from __future__ import annotations

import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import TwoFactorDevice
from apps.content.seeding import seed

PASSWORD = "Kata-Sandi-Uji-Yang-Panjang-2026"


class SeededTestCase(TestCase):
    """Database tes berisi data awal (seed) yang sama dengan instalasi asli."""

    def setUp(self):
        cache.clear()
        seed()
        self.client = Client(HTTP_HOST="testserver")


def make_admin(username: str = "pemilik", *, with_2fa: bool = False):
    user = get_user_model().objects.create_user(username=username, password=PASSWORD, is_staff=True, is_superuser=True)
    if with_2fa:
        TwoFactorDevice.objects.create(user=user, secret=pyotp.random_base32(), confirmed_at="2026-01-01T00:00:00Z")
        user.refresh_from_db()
    return user


def login_fully(client: Client, user) -> None:
    """Masuk panel lengkap dengan 2FA (seperti pemilik sungguhan)."""
    client.post(reverse("panel:login"), {"username": user.username, "password": PASSWORD})
    device = TwoFactorDevice.objects.get(user=user)
    code = pyotp.TOTP(device.secret).now()
    client.post(reverse("panel:otp-verify"), {"code": code})
