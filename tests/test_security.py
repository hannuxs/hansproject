"""Standar keamanan dari docs/05-keamanan.md."""
from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase, override_settings
from PIL import Image

from apps.content.models import ContactClick
from apps.core.images import PHOTO, process_image
from apps.core.textformat import render

from .helpers import SeededTestCase

ROOT = Path(__file__).resolve().parent.parent


class HeaderTests(SeededTestCase):
    def test_security_headers_on_public_page(self):
        r = self.client.get("/")
        csp = r["Content-Security-Policy"]
        self.assertIn("default-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("unsafe-eval", csp)
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("camera=()", r["Permissions-Policy"])
        self.assertEqual(r["Cross-Origin-Opener-Policy"], "same-origin")

    def test_public_pages_set_no_cookies(self):
        for path in ["/", "/syarat-ketentuan/", "/tidak-ada/"]:
            self.assertEqual(len(self.client.get(path).cookies), 0, path)

    def test_no_inline_styles_or_scripts(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn(' style="', html)
        self.assertNotIn("<script>", html)

    def test_public_html_always_revalidated(self):
        """Update langsung terlihat: browser wajib cek ulang, dan dapat 304 bila tidak berubah."""
        r = self.client.get("/")
        self.assertIn("no-cache", r["Cache-Control"])
        self.assertNotIn("max-age=300", r["Cache-Control"])
        etag = r["ETag"]
        again = self.client.get("/", HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(again.status_code, 304)
        self.assertEqual(again.content, b"")

    def test_update_keeps_old_static_files(self):
        for bat in ["update.bat", "install.bat"]:
            self.assertNotIn("--clear", (ROOT / bat).read_text(encoding="ascii"), bat)

    def test_admin_path_not_revealed(self):
        for path in ["/robots.txt", "/sitemap.xml", "/"]:
            self.assertNotIn(settings.ADMIN_URL_PATH, self.client.get(path).content.decode(), path)
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_404_does_not_leak_details(self):
        body = self.client.get("/halaman-tidak-ada/").content.decode()
        for leak in ["Traceback", "Django", "settings", "urlpatterns", str(ROOT)]:
            self.assertNotIn(leak, body)

    @override_settings(DEBUG=False)
    def test_500_page_is_generic(self):
        from apps.web.views import error_500

        body = error_500(None).content.decode()
        self.assertIn("gangguan", body)
        self.assertNotIn("Traceback", body)


class ClickBeaconTests(SeededTestCase):
    url = "/api/klik/"

    def test_valid_click_counted_without_personal_data(self):
        self.assertEqual(self.client.post(self.url, {"t": "tunas"}).status_code, 204)
        self.client.post(self.url, {"t": "tunas"})
        click = ContactClick.objects.get(target="tunas")
        self.assertEqual(click.count, 2)
        self.assertEqual({f.name for f in ContactClick._meta.fields}, {"id", "date", "target", "count"})

    def test_unknown_target_rejected(self):
        self.assertEqual(self.client.post(self.url, {"t": "<script>"}).status_code, 400)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_cross_site_rejected(self):
        r = self.client.post(self.url, {"t": "tunas"}, HTTP_SEC_FETCH_SITE="cross-site")
        self.assertEqual(r.status_code, 403)

    def test_rate_limited(self):
        codes = [self.client.post(self.url, {"t": "instagram"}).status_code for _ in range(25)]
        self.assertIn(429, codes)
        self.assertLessEqual(ContactClick.objects.get(target="instagram").count, 20)


class TextFormatTests(SimpleTestCase):
    def test_html_is_escaped(self):
        out = str(render('<script>alert(1)</script> <img src=x onerror=alert(1)> **tebal**'))
        self.assertNotIn("<script", out)
        self.assertNotIn("<img", out)
        self.assertIn("<strong>tebal</strong>", out)

    def test_dangerous_links_removed(self):
        out = str(render("[klik](javascript:alert(1)) [aman](https://hansproject.app)"))
        self.assertNotIn("javascript:", out.replace("[klik](javascript:alert(1))", ""))
        self.assertIn('href="https://hansproject.app"', out)

    def test_lists(self):
        out = str(render("- satu\n- dua\n\n1. a\n2. b"))
        self.assertIn("<ul><li>satu</li><li>dua</li></ul>", out)
        self.assertIn("<ol><li>a</li><li>b</li></ol>", out)


class UploadTests(SimpleTestCase):
    def _png(self, **save_kwargs) -> bytes:
        buf = io.BytesIO()
        Image.new("RGB", (50, 40), (255, 120, 0)).save(buf, "PNG", **save_kwargs)
        return buf.getvalue()

    def test_svg_rejected(self):
        svg = SimpleUploadedFile("qris.png", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        with self.assertRaises(ValidationError):
            process_image(svg, PHOTO)

    def test_fake_extension_rejected(self):
        with self.assertRaises(ValidationError):
            process_image(SimpleUploadedFile("foto.jpg", b"MZ\x90\x00 bukan gambar"), PHOTO)

    def test_image_reencoded_with_random_name_and_no_metadata(self):
        exif = Image.Exif()
        exif[0x010F] = "KameraRahasia"  # Make
        buf = io.BytesIO()
        Image.new("RGB", (60, 60), (10, 200, 10)).save(buf, "JPEG", exif=exif.tobytes())
        result = process_image(SimpleUploadedFile("saya.jpg", buf.getvalue()), PHOTO)
        self.assertTrue(result.name.endswith(".webp"))
        self.assertNotIn("saya", result.name)
        self.assertNotIn(b"KameraRahasia", result.read())

    @override_settings(UPLOAD_MAX_BYTES=100)
    def test_size_limit(self):
        with self.assertRaises(ValidationError):
            process_image(SimpleUploadedFile("a.png", self._png()), PHOTO)


class TablePrefixTests(SimpleTestCase):
    def test_every_table_uses_prefix(self):
        for model in apps.get_models(include_auto_created=True):
            self.assertTrue(model._meta.db_table.startswith("hp_"), model._meta.db_table)
        self.assertEqual(MigrationRecorder.Migration._meta.db_table, "hp_django_migrations")


class ProductionGuardTests(SimpleTestCase):
    """Mode produksi wajib menolak berjalan bila konfigurasinya berbahaya."""

    def _run(self, **env):
        base = {k: v for k, v in os.environ.items() if not k.startswith(("DB_", "SECRET", "DEBUG", "ALLOWED", "ADMIN_", "SITE_"))}
        base.update(APP_ENV="production", HANS_ENV_FILE=str(ROOT / "tidak-ada.env"), DJANGO_SETTINGS_MODULE="config.settings")
        base.update(env)
        code = "import django; django.setup(); from django.conf import settings; print('OK', settings.DEBUG, settings.SESSION_COOKIE_SECURE)"
        return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=base, capture_output=True, text=True, timeout=60)  # nosec B603

    def test_dangerous_config_refused(self):
        result = self._run(DEBUG="true", SECRET_KEY="pendek", ALLOWED_HOSTS="", ADMIN_URL_PATH="admin", DB_USER="root")
        self.assertNotEqual(result.returncode, 0)
        for text in ["DITOLAK", "DEBUG", "SECRET_KEY", "ALLOWED_HOSTS", "ADMIN_URL_PATH", "root"]:
            self.assertIn(text, result.stderr)

    def test_safe_config_accepted(self):
        result = self._run(
            SECRET_KEY="k3Y-" + "aB9xQ2mZ7pL4vT8wR1nC6yH5jD0fG3sK" * 2,
            ALLOWED_HOSTS="hansproject.app",
            SITE_URL="https://hansproject.app",
            ADMIN_URL_PATH="kelola-a1b2c3d4e5",
            DB_USER="hansproject_app",
            DB_PASSWORD="rahasia-uji",
            LOG_TO_FILE="false",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK False True", result.stdout)
