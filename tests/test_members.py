"""Akun pelanggan: login Google (tanpa menghubungi Google sungguhan), sesi, persetujuan, pesanan."""
from __future__ import annotations

import base64
import io
import json
import shutil
import time
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.content.models import LEGAL_VERSION_DEFAULT
from apps.members import auth, google
from apps.members.models import Member, MemberSession, Order

from .helpers import SeededTestCase, login_fully, make_admin

CLIENT_ID = settings.GOOGLE_CLIENT_ID


def fake_id_token(**claims) -> str:
    def enc(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{enc({'alg': 'RS256'})}.{enc(claims)}.tanda-tangan"


def claims_for(nonce: str, **extra) -> dict:
    now = int(time.time())
    data = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "Budi@Gmail.com",
        "email_verified": True,
        "name": "Budi Santoso",
        "iat": now,
        "exp": now + 3600,
        "nonce": nonce,
    }
    data.update(extra)
    return data


def make_member(sub="sub-1", email="budi@gmail.com", complete=True, accepted=True, **kwargs) -> Member:
    data = {"google_sub": sub, "email": email, "name": "Budi"}
    if complete:
        data.update(phone="6281234567890", business_name="Warung Budi")
    if accepted:  # sudah menyetujui S&K versi yang berlaku
        data.update(terms_version=LEGAL_VERSION_DEFAULT, terms_accepted_at=timezone.now())
    data.update(kwargs)
    return Member.objects.create(**data)


def login_member(client: Client, member: Member) -> None:
    response = HttpResponse()
    auth.login(RequestFactory().get("/"), response, member)
    client.cookies[auth.COOKIE] = response.cookies[auth.COOKIE].value
    client.cookies[auth.FLAG_COOKIE] = "1"


def png_upload(name="bukti.png"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    buf = io.BytesIO()
    Image.new("RGB", (120, 80), (30, 120, 200)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class PrivateMediaMixin:
    def tearDown(self):
        shutil.rmtree(settings.PRIVATE_MEDIA_ROOT, ignore_errors=True)
        super().tearDown()


# ---------------------------------------------------------------------------
# Login Google
# ---------------------------------------------------------------------------
@override_settings(SITE_URL="http://testserver")
class GoogleLoginTests(SeededTestCase):
    def start(self, next_path="/akun/pesan/tunas/"):
        r = self.client.get(reverse("akun:google"), {"next": next_path})
        self.assertEqual(r.status_code, 302)
        return r, parse_qs(urlsplit(r["Location"]).query)

    def test_start_redirects_to_google_with_pkce_state_nonce(self):
        r, q = self.start()
        self.assertTrue(r["Location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?"))
        self.assertEqual(q["client_id"], [CLIENT_ID])
        self.assertEqual(q["redirect_uri"], ["http://testserver/akun/google/callback/"])
        self.assertEqual(q["scope"], ["openid email profile"])
        self.assertEqual(q["code_challenge_method"], ["S256"])
        self.assertGreaterEqual(len(q["state"][0]), 40)
        self.assertGreaterEqual(len(q["nonce"][0]), 40)
        cookie = r.cookies["hp_oauth"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/akun/google/")
        self.assertNotIn(settings.GOOGLE_CLIENT_SECRET, r["Location"])  # rahasia tidak pernah ke browser

    @override_settings(SITE_URL="http://127.0.0.1:8432")
    def test_start_moves_to_canonical_host_first(self):
        r = self.client.get("/akun/google/?next=/akun/", HTTP_HOST="localhost")
        self.assertEqual(r["Location"], "http://127.0.0.1:8432/akun/google/?next=/akun/")

    def test_full_login_creates_member_and_session(self):
        _, q = self.start()
        token = fake_id_token(**claims_for(q["nonce"][0]))
        with mock.patch.object(google, "_post_token", return_value={"id_token": token}) as post:
            r = self.client.get(reverse("akun:google-callback"), {"state": q["state"][0], "code": "kode-uji"})
        sent = post.call_args.args[0]
        self.assertEqual(sent["client_secret"], settings.GOOGLE_CLIENT_SECRET)
        self.assertEqual(len(sent["code_verifier"]), len(sent["code_verifier"].strip()))
        member = Member.objects.get(google_sub="1234567890")
        self.assertEqual((member.email, member.name), ("budi@gmail.com", "Budi Santoso"))
        # Akun baru -> popup persetujuan dulu, lalu data diri, lalu kembali ke pesanan.
        self.assertEqual(r["Location"], "/akun/persetujuan/?next=%2Fakun%2Fpesan%2Ftunas%2F")
        page = self.client.get(r["Location"])
        self.assertContains(page, 'name="setuju"')
        self.assertContains(page, 'href="/syarat-ketentuan/"')
        self.assertContains(page, 'href="/kebijakan-privasi/"')
        r2 = self.client.post(r["Location"], {"setuju": "1"})
        self.assertEqual(r2["Location"], "/akun/pesan/tunas/")
        self.assertEqual(self.client.get(r2["Location"])["Location"], "/akun/data-diri/?next=%2Fakun%2Fpesan%2Ftunas%2F")
        cookie = r.cookies[auth.COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(r.cookies[auth.FLAG_COOKIE].value, "1")
        session = MemberSession.objects.get(member=member)
        self.assertNotEqual(session.key_hash, cookie.value)  # database hanya menyimpan hash
        self.assertEqual(r.cookies["hp_oauth"].value, "")  # cookie pengaman dihapus

    def test_wrong_state_rejected(self):
        _, q = self.start()
        with mock.patch.object(google, "_post_token") as post:
            r = self.client.get(reverse("akun:google-callback"), {"state": "palsu", "code": "x"})
        post.assert_not_called()
        self.assertEqual(r["Location"], "/akun/masuk/?gagal=kedaluwarsa")
        self.assertFalse(Member.objects.exists())

    def test_callback_without_start_rejected(self):
        r = self.client.get(reverse("akun:google-callback"), {"state": "a", "code": "b"})
        self.assertEqual(r["Location"], "/akun/masuk/?gagal=kedaluwarsa")

    def test_user_cancelled(self):
        self.start()
        r = self.client.get(reverse("akun:google-callback"), {"error": "access_denied"})
        self.assertEqual(r["Location"], "/akun/masuk/?gagal=batal")

    def test_google_error_handled(self):
        _, q = self.start()
        with mock.patch.object(google, "_post_token", side_effect=google.GoogleLoginError("HTTP 400")):
            r = self.client.get(reverse("akun:google-callback"), {"state": q["state"][0], "code": "x"})
        self.assertEqual(r["Location"], "/akun/masuk/?gagal=gagal")
        self.assertContains(self.client.get(r["Location"]), "sedang gagal")

    def test_inactive_member_blocked(self):
        make_member(sub="1234567890", is_active=False)
        _, q = self.start()
        token = fake_id_token(**claims_for(q["nonce"][0]))
        with mock.patch.object(google, "_post_token", return_value={"id_token": token}):
            r = self.client.get(reverse("akun:google-callback"), {"state": q["state"][0], "code": "x"})
        self.assertEqual(r["Location"], "/akun/masuk/?gagal=nonaktif")
        self.assertNotIn(auth.COOKIE, r.cookies)

    def test_returning_member_goes_to_next(self):
        make_member(sub="1234567890")
        _, q = self.start("/akun/pesan/tunas/")
        token = fake_id_token(**claims_for(q["nonce"][0]))
        with mock.patch.object(google, "_post_token", return_value={"id_token": token}):
            r = self.client.get(reverse("akun:google-callback"), {"state": q["state"][0], "code": "x"})
        self.assertEqual(r["Location"], "/akun/pesan/tunas/")
        self.assertEqual(Member.objects.count(), 1)

    def test_open_redirect_blocked(self):
        make_member(sub="1234567890")
        _, q = self.start("https://situs-jahat.example/curi")
        token = fake_id_token(**claims_for(q["nonce"][0]))
        with mock.patch.object(google, "_post_token", return_value={"id_token": token}):
            r = self.client.get(reverse("akun:google-callback"), {"state": q["state"][0], "code": "x"})
        self.assertEqual(r["Location"], "/akun/")

    @override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
    def test_not_configured(self):
        self.assertContains(self.client.get("/akun/masuk/"), "sedang disiapkan")
        self.assertEqual(self.client.get("/akun/google/")["Location"], "/akun/masuk/?gagal=belum-siap")


class ClaimValidationTests(SimpleTestCase):
    def check_rejected(self, **bad):
        claims = claims_for("n0nce")
        claims.update(bad)
        with self.assertRaises(google.GoogleLoginError):
            google.validate_claims(claims, "n0nce")

    def test_valid(self):
        identity = google.validate_claims(claims_for("n0nce"), "n0nce")
        self.assertEqual((identity.sub, identity.email), ("1234567890", "budi@gmail.com"))

    def test_rejections(self):
        self.check_rejected(iss="https://penipu.example")
        self.check_rejected(aud="aplikasi-lain.apps.googleusercontent.com")
        self.check_rejected(exp=int(time.time()) - 3600)
        self.check_rejected(nonce="lain")
        self.check_rejected(email_verified=False)
        self.check_rejected(sub="")

    def test_bad_token_format(self):
        with self.assertRaises(google.GoogleLoginError):
            google._decode_payload("bukan-token")


# ---------------------------------------------------------------------------
# Sesi & halaman akun
# ---------------------------------------------------------------------------
class SessionTests(SeededTestCase):
    def test_pages_require_login(self):
        for path in ["/akun/", "/akun/data-diri/", "/akun/pesan/tunas/", "/akun/chat/baru/?topik=umum"]:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertTrue(r["Location"].startswith("/akun/masuk/?next="), path)

    def test_incomplete_profile_must_be_completed(self):
        login_member(self.client, make_member(complete=False))
        r = self.client.get("/akun/pesan/tunas/")
        self.assertEqual(r["Location"], "/akun/data-diri/?next=%2Fakun%2Fpesan%2Ftunas%2F")
        r = self.client.post(
            "/akun/data-diri/?next=/akun/pesan/tunas/",
            {"name": " Budi  Santoso ", "phone": "0812-3456 7890", "business_name": "Warung Budi"},
        )
        self.assertEqual(r["Location"], "/akun/pesan/tunas/")
        member = Member.objects.get()
        self.assertEqual((member.name, member.phone), ("Budi Santoso", "6281234567890"))
        self.assertEqual(member.phone_display, "0812-3456-7890")

    def test_invalid_phone_rejected(self):
        login_member(self.client, make_member(complete=False))
        r = self.client.post("/akun/data-diri/", {"name": "Budi", "phone": "12345", "business_name": "X"})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "Nomor HP tidak valid", status_code=400)

    def test_profile_page_private_and_not_cached(self):
        login_member(self.client, make_member())
        r = self.client.get("/akun/profil/")
        self.assertContains(r, "Warung Budi")
        self.assertIn("no-store", r["Cache-Control"])
        self.assertIn("noindex", r["X-Robots-Tag"])
        self.assertIn('class="profile-btn home-btn" href="/"', r.content.decode())  # tombol Beranda di header akun

    def test_public_page_is_same_for_members(self):
        """Halaman publik di-cache sama untuk semua orang: tidak boleh memuat data pelanggan."""
        login_member(self.client, make_member(business_name="Toko Rahasia Uji"))
        r = self.client.get("/")
        self.assertNotIn("Toko Rahasia Uji", r.content.decode())
        self.assertNotIn("budi@gmail.com", r.content.decode())
        self.assertEqual(len(r.cookies), 0)

    def test_logout_ends_session(self):
        login_member(self.client, make_member())
        r = self.client.post("/akun/keluar/")
        self.assertEqual(r["Location"], "/")
        self.assertEqual(r.cookies[auth.COOKIE].value, "")
        self.assertEqual(r.cookies[auth.FLAG_COOKIE].value, "")
        self.assertFalse(MemberSession.objects.exists())

    def test_logout_everywhere(self):
        member = make_member()
        other = Client(HTTP_HOST="testserver")
        login_member(other, member)
        login_member(self.client, member)
        self.client.post("/akun/keluar/", {"semua": "1"})
        self.assertEqual(other.get("/akun/").status_code, 302)

    def test_stale_cookie_is_cleared(self):
        self.client.cookies[auth.COOKIE] = "x" * 43
        self.client.cookies[auth.FLAG_COOKIE] = "1"
        r = self.client.get("/akun/masuk/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.cookies[auth.FLAG_COOKIE].value, "")

    def test_logged_in_member_skips_login_page(self):
        login_member(self.client, make_member())
        self.assertEqual(self.client.get("/akun/masuk/?next=/akun/tanya/")["Location"], "/akun/tanya/")

    def test_csrf_enforced_on_account_forms(self):
        client = Client(enforce_csrf_checks=True, HTTP_HOST="testserver")
        login_member(client, make_member())
        self.assertEqual(client.post("/akun/pesan/tunas/").status_code, 403)
        self.assertFalse(Order.objects.exists())

    def test_member_cookie_does_not_open_panel(self):
        login_member(self.client, make_member())
        r = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("panel:login"), r["Location"])


# ---------------------------------------------------------------------------
# Pesanan & bukti bayar
# ---------------------------------------------------------------------------
class OrderTests(PrivateMediaMixin, SeededTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member()
        login_member(self.client, self.member)

    def order(self, code="tunas", subdomain="warungbudi") -> Order:
        r = self.client.post(f"/akun/pesan/{code}/", {"subdomain": subdomain})
        self.assertEqual(r.status_code, 302, r.content[:800])
        return Order.objects.latest("created_at")

    def test_create_order_snapshot_and_status(self):
        page = self.client.get("/akun/pesan/tunas/")
        self.assertContains(page, "Buat pesanan")
        order = self.order()
        self.assertEqual((order.package_name, order.status), ("Tunas", Order.STATUS_PAYMENT))
        self.assertTrue(order.code.startswith("HP-"))
        self.assertIn("25.000", order.price_text)
        self.assertEqual(self.order("rimba").status, Order.STATUS_CONSULT)

    def test_duplicate_open_order_prevented(self):
        first = self.order()
        r = self.client.post("/akun/pesan/tunas/", {"subdomain": "tokolain"})
        self.assertEqual(r["Location"], f"/akun/pesanan/{first.code}/")
        self.assertEqual(Order.objects.count(), 1)

    def test_unknown_or_hidden_package_404(self):
        self.assertEqual(self.client.get("/akun/pesan/tidak-ada/").status_code, 404)

    def test_other_member_cannot_see_order(self):
        order = self.order()
        other = Client(HTTP_HOST="testserver")
        login_member(other, make_member(sub="sub-2", email="lain@gmail.com"))
        self.assertEqual(other.get(f"/akun/pesanan/{order.code}/").status_code, 404)

    def test_upload_proof_private_and_reencoded(self):
        order = self.order()
        r = self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "bukti", "proof": png_upload("saya.png")})
        self.assertEqual(r.status_code, 302, r.content[:500])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CHECKING)
        self.assertTrue(order.payment_proof.name.endswith(".webp"))
        self.assertNotIn("saya", order.payment_proof.name)
        # Pemilik bisa membuka buktinya ...
        own = self.client.get(f"/akun/pesanan/{order.code}/bukti/")
        self.assertEqual((own.status_code, own["Content-Type"]), (200, "image/webp"))
        self.assertIn("sandbox", own["Content-Security-Policy"])
        # ... orang lain & pengunjung tidak.
        other = Client(HTTP_HOST="testserver")
        self.assertEqual(other.get(f"/akun/pesanan/{order.code}/bukti/").status_code, 302)
        login_member(other, make_member(sub="sub-2", email="lain@gmail.com"))
        self.assertEqual(other.get(f"/akun/pesanan/{order.code}/bukti/").status_code, 404)
        self.assertEqual(Client().get(f"/media/{order.payment_proof.name}").status_code, 404)

    def test_resend_proof_replaces_old_file(self):
        order = self.order()
        self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "bukti", "proof": png_upload()})
        order.refresh_from_db()
        old = order.payment_proof.name
        self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "bukti", "proof": png_upload()})
        order.refresh_from_db()
        self.assertNotEqual(order.payment_proof.name, old)
        self.assertFalse(order.payment_proof.storage.exists(old))

    def test_fake_image_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        order = self.order()
        bad = SimpleUploadedFile("bukti.jpg", b"MZ bukan gambar", content_type="image/jpeg")
        r = self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "bukti", "proof": bad})
        self.assertEqual(r.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PAYMENT)

    def test_cancel_order(self):
        order = self.order()
        self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "batal"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        # Pesanan yang sudah batal tidak bisa diberi bukti bayar lagi.
        r = self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "bukti", "proof": png_upload()})
        self.assertEqual(r.status_code, 400)

    def test_profile_lists_orders(self):
        order = self.order()
        self.assertContains(self.client.get("/akun/pesanan/"), order.code)

    def test_admin_updates_status_and_sees_proof(self):
        order = self.order()
        self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "bukti", "proof": png_upload()})
        admin = Client(HTTP_HOST="testserver")
        login_fully(admin, make_admin(with_2fa=True))
        page = admin.get(reverse("panel:pesanan-update", args=[order.pk]))
        self.assertContains(page, "Warung Budi")
        self.assertEqual(admin.get(reverse("panel:pesanan-bukti", args=[order.pk])).status_code, 200)
        admin.post(reverse("panel:pesanan-update", args=[order.pk]), {"status": "aktif", "admin_note": "Link aplikasi: https://contoh"})
        page = self.client.get(f"/akun/pesanan/{order.code}/")
        self.assertContains(page, "Aktif")
        self.assertContains(page, "Link aplikasi")
        # Pesanan kasir yang diaktifkan langsung membuat toko.
        self.assertContains(page, "Kelola toko")
        order.refresh_from_db()
        self.assertEqual(order.store.subdomain, "warungbudi")

    def test_deleting_member_keeps_paid_orders_for_tax_records(self):
        unpaid = self.order("tunas", "tokobelumbayar")
        paid = self.order("tumbuh", "tokosudahbayar")
        self.client.post(f"/akun/pesanan/{paid.code}/", {"aksi": "bukti", "proof": png_upload()})
        paid.refresh_from_db()
        storage, name = paid.payment_proof.storage, paid.payment_proof.name
        self.member.delete()
        self.assertFalse(Order.objects.filter(pk=unpaid.pk).exists())
        paid.refresh_from_db()
        self.assertIsNone(paid.member)
        self.assertEqual((paid.buyer_name, paid.buyer_email, paid.buyer_business), ("Budi", "budi@gmail.com", "Warung Budi"))
        self.assertEqual(paid.customer_phone, "0812-3456-7890")
        self.assertTrue(storage.exists(name))
        # Panel tetap bisa membuka pesanan tanpa akun.
        admin = Client(HTTP_HOST="testserver")
        login_fully(admin, make_admin(with_2fa=True))
        self.assertContains(admin.get(reverse("panel:pesanan-update", args=[paid.pk])), "akun sudah dihapus")
        self.assertContains(admin.get(reverse("panel:pesanan-list")), "Budi")

    def test_orders_older_than_ten_years_purged_with_proof(self):
        from datetime import timedelta

        from django.core.management import call_command

        order = self.order()
        self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "bukti", "proof": png_upload()})
        order.refresh_from_db()
        storage, name = order.payment_proof.storage, order.payment_proof.name
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(days=3653))
        recent = self.order("rimba")
        out = io.StringIO()
        call_command("bersihkan_data", stdout=out)
        self.assertIn("1 pesanan lama", out.getvalue())
        self.assertFalse(Order.objects.filter(pk=order.pk).exists())
        self.assertFalse(storage.exists(name))
        self.assertTrue(Order.objects.filter(pk=recent.pk).exists())


# ---------------------------------------------------------------------------
# Popup persetujuan Syarat & Ketentuan / Kebijakan Privasi
# ---------------------------------------------------------------------------
class ConsentTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member(accepted=False)
        login_member(self.client, self.member)

    def test_all_account_pages_wait_for_consent(self):
        for path in ["/akun/", "/akun/data-diri/", "/akun/chat/", "/akun/pesanan/", "/akun/pesan/tunas/"]:
            r = self.client.get(path)
            self.assertTrue(r["Location"].startswith("/akun/persetujuan/?next="), path)
        page = self.client.get("/akun/persetujuan/?next=/akun/")
        self.assertContains(page, "Satu langkah lagi")
        self.assertContains(page, '<dialog class="consent-dialog" id="consent-dialog" closedby="none"')
        self.assertNotContains(page, 'aria-modal')
        self.assertNotContains(page, '{#')  # komentar template tidak boleh bocor ke halaman
        self.assertEqual(page["Cache-Control"], "no-store, max-age=0")

    def test_checkbox_required(self):
        r = self.client.post("/akun/persetujuan/", {})
        self.assertContains(r, "Centang kotak persetujuan", status_code=400)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.terms_version)

    def test_accept_once_then_never_again(self):
        r = self.client.post("/akun/persetujuan/?next=/akun/", {"setuju": "1"})
        self.assertEqual(r["Location"], "/akun/")
        self.member.refresh_from_db()
        self.assertEqual(self.member.terms_version, LEGAL_VERSION_DEFAULT)
        self.assertIsNotNone(self.member.terms_accepted_at)
        self.assertEqual(self.client.get("/akun/").status_code, 200)
        # Halaman persetujuan langsung meneruskan bila sudah setuju.
        self.assertEqual(self.client.get("/akun/persetujuan/?next=/akun/")["Location"], "/akun/")
        # Masuk lagi (sesi baru) tetap tidak ditanya lagi.
        other = Client(HTTP_HOST="testserver")
        login_member(other, self.member)
        self.assertEqual(other.get("/akun/").status_code, 200)

    def test_new_document_version_asks_again(self):
        from datetime import date

        from apps.content.models import SiteSettings

        self.client.post("/akun/persetujuan/", {"setuju": "1"})
        site = SiteSettings.load()
        site.legal_version = date(2027, 1, 16)
        site.save()
        r = self.client.get("/akun/")
        self.assertTrue(r["Location"].startswith("/akun/persetujuan/"))
        self.assertContains(self.client.get(r["Location"]), "Ada pembaruan")

    def test_decline_logs_out(self):
        r = self.client.post("/akun/keluar/")
        self.assertEqual(r.status_code, 302)
        self.assertFalse(MemberSession.objects.filter(member=self.member).exists())

    def test_toko_dashboard_also_waits(self):
        from apps.pos.models import Outlet, Store

        store = Store.objects.create(owner=self.member, subdomain="tokoku", name="Tokoku", package_name="Tunas",
                                     active_until=timezone.localdate())
        Outlet.objects.create(store=store, number=1, name="Utama")
        r = self.client.get("/akun/toko/tokoku/")
        self.assertTrue(r["Location"].startswith("/akun/persetujuan/"))
