"""Panel pengelola: wajib login + 2FA, pembatasan percobaan, CRUD, riwayat."""
from __future__ import annotations

import time

import pyotp
from django.conf import settings
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from apps.accounts.models import LoginAttempt, TwoFactorDevice
from apps.content.models import AuditLog, Faq, Package, SiteSettings

from .helpers import PASSWORD, SeededTestCase, login_fully, make_admin


class AccessTests(SeededTestCase):
    def test_panel_requires_login(self):
        for name in ["panel:dashboard", "panel:paket-list", "panel:pengaturan", "panel:account", "panel:audit"]:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn(reverse("panel:login"), r["Location"])

    def test_panel_is_not_at_admin_and_is_noindex(self):
        self.assertTrue(reverse("panel:login").startswith(f"/{settings.ADMIN_URL_PATH}/"))
        r = self.client.get(reverse("panel:login"))
        self.assertIn("noindex", r["X-Robots-Tag"])
        self.assertIn("no-store", r["Cache-Control"])
        self.assertContains(r, 'name="robots" content="noindex')

    def test_password_alone_is_not_enough_when_2fa_required(self):
        user = make_admin(with_2fa=True)
        r = self.client.post(reverse("panel:login"), {"username": user.username, "password": PASSWORD})
        self.assertRedirects(r, reverse("panel:otp-verify"))
        self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 302)

    def test_development_mode_password_only_even_with_authenticator(self):
        """Komputer pengembangan (ADMIN_REQUIRE_2FA=false): tidak diminta kode Authenticator."""
        from django.test import override_settings

        user = make_admin(with_2fa=True)
        with override_settings(ADMIN_REQUIRE_2FA=False):
            r = self.client.post(reverse("panel:login"), {"username": user.username, "password": PASSWORD})
            self.assertEqual(r["Location"], reverse("panel:dashboard"))
            self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 200)

    def test_production_always_requires_2fa(self):
        source = (settings.BASE_DIR / "config" / "settings" / "production.py").read_text(encoding="utf-8")
        self.assertRegex(source, r"(?m)^ADMIN_REQUIRE_2FA = True$")

    def test_first_login_forces_2fa_setup(self):
        user = make_admin()
        r = self.client.post(reverse("panel:login"), {"username": user.username, "password": PASSWORD})
        self.assertRedirects(r, reverse("panel:otp-setup"))
        page = self.client.get(reverse("panel:otp-setup"))
        self.assertContains(page, "<svg")
        device = TwoFactorDevice.objects.get(user=user)
        r = self.client.post(reverse("panel:otp-setup"), {"code": pyotp.TOTP(device.secret).now()})
        self.assertRedirects(r, reverse("panel:dashboard"))
        device.refresh_from_db()
        self.assertIsNotNone(device.confirmed_at)
        self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 200)

    def test_full_login_and_logout(self):
        user = make_admin(with_2fa=True)
        login_fully(self.client, user)
        self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 200)
        session_key = self.client.session.session_key
        self.client.post(reverse("panel:logout"))
        from django.contrib.sessions.models import Session

        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 302)

    def test_otp_code_cannot_be_reused(self):
        user = make_admin(with_2fa=True)
        device = TwoFactorDevice.objects.get(user=user)
        code = pyotp.TOTP(device.secret).now()
        self.client.post(reverse("panel:login"), {"username": user.username, "password": PASSWORD})
        self.client.post(reverse("panel:otp-verify"), {"code": code})
        other = Client(HTTP_HOST="testserver")
        other.post(reverse("panel:login"), {"username": user.username, "password": PASSWORD})
        r = other.post(reverse("panel:otp-verify"), {"code": code})
        self.assertEqual(r.status_code, 400)

    def test_lockout_after_failures(self):
        user = make_admin(with_2fa=True)
        for _ in range(settings.LOGIN_MAX_FAILURES):
            self.client.post(reverse("panel:login"), {"username": user.username, "password": "salah"})
        r = self.client.post(reverse("panel:login"), {"username": user.username, "password": PASSWORD})
        self.assertEqual(r.status_code, 429)
        self.assertContains(r, "Terlalu banyak percobaan", status_code=429)
        self.assertEqual(LoginAttempt.objects.filter(success=False).count(), settings.LOGIN_MAX_FAILURES)
        self.assertFalse(LoginAttempt.objects.exclude(ip_hash__regex=r"^[0-9a-f]{24}$").exists())  # IP tidak mentah

    def test_session_max_age_enforced(self):
        user = make_admin(with_2fa=True)
        login_fully(self.client, user)
        session = self.client.session
        session["hp_login_at"] = time.time() - (settings.ADMIN_SESSION_MAX_HOURS * 3600 + 60)
        session.save()
        self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 302)

    def test_csrf_enforced(self):
        user = make_admin(with_2fa=True)
        client = Client(enforce_csrf_checks=True, HTTP_HOST="testserver")
        r = client.post(reverse("panel:login"), {"username": user.username, "password": PASSWORD})
        self.assertEqual(r.status_code, 403)

    def test_session_cookie_limited_to_panel_path(self):
        self.assertEqual(settings.SESSION_COOKIE_PATH, f"/{settings.ADMIN_URL_PATH}/")
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)


class CrudTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_admin(with_2fa=True)
        login_fully(self.client, self.user)

    def test_all_section_pages_render(self):
        from apps.panel.registry import SECTIONS

        for s in SECTIONS:
            self.assertEqual(self.client.get(s.nav_url).status_code, 200, s.key)
        pkg = Package.objects.get(code="tumbuh")
        self.assertEqual(self.client.get(reverse("panel:paket-update", args=[pkg.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("panel:paket-create")).status_code, 200)

    def test_create_update_delete_faq_with_audit(self):
        r = self.client.post(reverse("panel:faq-create"), {"question": "Ada demo?", "answer": "Ada, di halaman utama.", "order": 5, "is_active": "on"})
        self.assertRedirects(r, reverse("panel:faq-list"))
        faq = Faq.objects.get(question="Ada demo?")
        self.client.post(reverse("panel:faq-update", args=[faq.pk]), {"question": "Ada demo kasir?", "answer": "Ada.", "order": 5})
        faq.refresh_from_db()
        self.assertEqual((faq.question, faq.is_active), ("Ada demo kasir?", False))
        self.client.post(reverse("panel:faq-delete", args=[faq.pk]))
        self.assertFalse(Faq.objects.filter(pk=faq.pk).exists())
        actions = list(AuditLog.objects.filter(target_type="pertanyaan").values_list("action", flat=True))
        self.assertEqual(sorted(actions), ["create", "delete", "update"])

    def test_settings_instagram_username_updates_site(self):
        site = SiteSettings.load()
        data = {f: getattr(site, f) for f in [
            "hero_title", "hero_subtitle", "seo_title", "seo_description",
        ]}
        data.update({"instagram_username": "@toko.hans", "legal_version": "2026-11-19", "rekening-TOTAL_FORMS": "0", "rekening-INITIAL_FORMS": "0"})
        r = self.client.post(reverse("panel:pengaturan"), data)
        self.assertEqual(r.status_code, 302, r.content.decode()[:2000])
        self.assertEqual(SiteSettings.load().instagram_username, "toko.hans")
        cache.clear()
        self.assertIn("https://www.instagram.com/toko.hans", self.client.get("/").content.decode())

    def test_invalid_input_rejected_server_side(self):
        r = self.client.post(reverse("panel:pengaturan"), {"instagram_username": "bukan valid!", "instagram_url": "http://x.com"})
        self.assertEqual(r.status_code, 400)

    def test_reorder(self):
        first, second = list(Faq.objects.all()[:2])
        self.client.post(reverse("panel:faq-move", args=[second.pk, "naik"]))
        self.assertEqual(list(Faq.objects.all()[:2]), [second, first])
