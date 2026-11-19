"""Aplikasi kasir: subdomain toko, aktivasi pesanan, dashboard pemilik, login kasir, transaksi, laporan."""
from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.content.models import Package
from apps.members.models import Order
from apps.pos import cashier_auth, services, subdomains
from apps.pos.models import Cashier, CashierSession, Category, Outlet, Product, Sale, Store, add_months

from .helpers import SeededTestCase, login_fully, make_admin
from .test_members import login_member, make_member

PIN = "482915"


def make_store(owner, sub="warungbudi", *, days=20, package="tunas", **kwargs) -> Store:
    pkg = Package.objects.get(code=package)
    store = Store.objects.create(
        owner=owner, subdomain=sub, name=kwargs.pop("name", "Warung Budi"), package=pkg, package_name=pkg.name,
        base_outlets=pkg.outlet_count or 1, active_until=timezone.localdate() + timedelta(days=days), **kwargs,
    )
    Outlet.objects.create(store=store, number=1, name="Toko utama")
    return store


def make_cashier(store, username="kasir1", pin=PIN, outlet=None) -> Cashier:
    cashier = Cashier(store=store, outlet=outlet or store.outlets.first(), username=username)
    cashier_auth.set_pin(cashier, pin)
    cashier.save()
    return cashier


def store_client(sub="warungbudi") -> Client:
    return Client(HTTP_HOST=f"{sub}.hansproject.app")


def kasir_login(client, username="kasir1", pin=PIN):
    return client.post("/kasir/masuk/", {"username": username, "pin": pin})


def pay(client, items, **extra):
    payload = {"key": extra.pop("key", "kunci-" + timezone.now().strftime("%H%M%S%f")), "items": items, "method": "tunai"}
    payload.update(extra)
    return client.post("/kasir/bayar/", json.dumps(payload), content_type="application/json", HTTP_ACCEPT="application/json")


# ---------------------------------------------------------------------------
# Aturan alamat toko
# ---------------------------------------------------------------------------
class SubdomainRuleTests(SimpleTestCase):
    def test_valid_and_normalized(self):
        self.assertEqual(subdomains.validate("  WarungBudi "), "warungbudi")
        self.assertEqual(subdomains.validate("kopi-ani-2"), "kopi-ani-2")
        self.assertEqual(subdomains.validate("tokoku.hansproject.app"), "tokoku")

    def test_rejected(self):
        for bad in ["ab", "a" * 31, "-toko", "toko-", "to ko", "toko_ku", "tókö", "xn--abc", "www", "admin", "kasir", "api", "toko.lain"]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                subdomains.validate(bad)

    def test_host_parsing(self):
        self.assertEqual(subdomains.subdomain_from_host("warungbudi.hansproject.app"), "warungbudi")
        self.assertEqual(subdomains.subdomain_from_host("WarungBudi.hansproject.app:443"), "warungbudi")
        for host in ["hansproject.app", "www.hansproject.app", "a.b.hansproject.app", "evil.com", "hansproject.app.evil.com", "127.0.0.1:8432"]:
            with self.subTest(host=host):
                self.assertIsNone(subdomains.subdomain_from_host(host))

    def test_store_url(self):
        self.assertEqual(subdomains.store_url("warungbudi", "/kasir/"), "https://warungbudi.hansproject.app/kasir/")

    @override_settings(SITE_URL="http://127.0.0.1:8432", STORE_BASE_DOMAIN="localhost")
    def test_store_url_development(self):
        self.assertEqual(subdomains.store_url("warungbudi", "/kasir/"), "http://warungbudi.localhost:8432/kasir/")

    def test_add_months_clamps_to_month_end(self):
        from datetime import date

        self.assertEqual(add_months(date(2026, 1, 31)), date(2026, 2, 28))
        self.assertEqual(add_months(date(2026, 12, 15)), date(2027, 1, 15))


# ---------------------------------------------------------------------------
# Subdomain: hanya halaman toko & kasir
# ---------------------------------------------------------------------------
class HostRoutingTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.store = make_store(make_member())

    def test_store_home(self):
        r = store_client().get("/")
        self.assertContains(r, "Warung Budi")
        self.assertContains(r, "segera hadir")
        self.assertEqual(r["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("Disallow: /", store_client().get("/robots.txt").content.decode())

    def test_unknown_store_404_without_crash(self):
        r = store_client("tidakada").get("/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "tidak ditemukan", status_code=404)

    def test_main_site_pages_not_on_subdomain(self):
        client = store_client()
        for path in ["/akun/", "/akun/masuk/", f"/{self._panel()}/", "/kebijakan-privasi/", "/akun/toko/warungbudi/"]:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 404)

    def _panel(self):
        from django.conf import settings

        return settings.ADMIN_URL_PATH

    def test_main_domain_unaffected(self):
        self.assertEqual(Client(HTTP_HOST="hansproject.app").get("/").status_code, 200)
        self.assertEqual(Client(HTTP_HOST="www.hansproject.app").get("/").status_code, 200)

    def test_expired_beyond_30_days_is_gone(self):
        self.store.active_until = timezone.localdate() - timedelta(days=31)
        self.store.save()
        self.assertEqual(store_client().get("/").status_code, 404)
        self.assertEqual(store_client().get("/kasir/masuk/").status_code, 404)


class TlsAskTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        make_store(make_member())
        # Host apa pun: middleware ini berjalan sebelum pemeriksaan ALLOWED_HOSTS.
        self.client = Client(HTTP_HOST="127.0.0.1:8432", REMOTE_ADDR="127.0.0.1")

    def ask(self, domain, **extra):
        return self.client.get("/_tls/izin/", {"domain": domain}, **extra)

    def test_existing_store_allowed(self):
        self.assertEqual(self.ask("warungbudi.hansproject.app").status_code, 200)

    def test_unknown_or_other_domain_refused(self):
        for domain in ["lain.hansproject.app", "evil.com", "hansproject.app", ""]:
            with self.subTest(domain=domain):
                self.assertEqual(self.ask(domain).status_code, 404)

    def test_only_from_server_itself(self):
        self.assertEqual(self.ask("warungbudi.hansproject.app", REMOTE_ADDR="203.0.113.5").status_code, 404)
        self.assertEqual(self.ask("warungbudi.hansproject.app", HTTP_X_FORWARDED_FOR="203.0.113.5").status_code, 404)


# ---------------------------------------------------------------------------
# Pesan -> aktif -> perpanjang
# ---------------------------------------------------------------------------
class ActivationTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member()
        login_member(self.client, self.member)
        self.admin = Client(HTTP_HOST="testserver")
        login_fully(self.admin, make_admin(with_2fa=True))

    def order(self, sub="warungbudi", code="tunas"):
        r = self.client.post(f"/akun/pesan/{code}/", {"subdomain": sub})
        self.assertEqual(r.status_code, 302, r.content[:600])
        return Order.objects.latest("created_at")

    def activate(self, order, **extra):
        data = {"status": "aktif", "admin_note": "", "rincian-TOTAL_FORMS": "0", "rincian-INITIAL_FORMS": "0"}
        data.update(extra)
        return self.admin.post(reverse("panel:pesanan-update", args=[order.pk]), data)

    def test_order_form_requires_valid_free_subdomain(self):
        page = self.client.get("/akun/pesan/tunas/")
        self.assertContains(page, ".hansproject.app")
        for bad in ["", "admin", "a b"]:
            r = self.client.post("/akun/pesan/tunas/", {"subdomain": bad})
            self.assertEqual(r.status_code, 400)
        make_store(make_member(sub="lain", email="lain@gmail.com"), "dipakai")
        self.assertEqual(self.client.post("/akun/pesan/tunas/", {"subdomain": "dipakai"}).status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_subdomain_reserved_by_open_order(self):
        self.order("kopiani")
        other = Client(HTTP_HOST="testserver")
        login_member(other, make_member(sub="sub-2", email="lain@gmail.com"))
        r = other.post("/akun/pesan/tunas/", {"subdomain": "kopiani"})
        self.assertContains(r, "sudah dipakai", status_code=400)

    def test_activation_creates_store_once(self):
        order = self.order()
        self.assertEqual(self.activate(order).status_code, 302)
        order.refresh_from_db()
        store = order.store
        self.assertEqual((store.subdomain, store.owner, store.package_name, store.base_outlets), ("warungbudi", self.member, "Tunas", 2))
        self.assertEqual(store.active_until, add_months(timezone.localdate()))
        self.assertEqual(store.name, "Warung Budi")
        self.assertEqual(store.outlets.count(), 1)
        self.assertIsNotNone(order.activated_at)
        # Disimpan ulang (mis. ubah catatan) tidak membuat toko kedua / menambah masa aktif.
        self.activate(order, admin_note="halo")
        self.assertEqual(Store.objects.count(), 1)
        self.assertEqual(Store.objects.get().active_until, add_months(timezone.localdate()))
        # Pelanggan melihat tokonya di profil.
        self.assertContains(self.client.get("/akun/toko/"), "warungbudi.hansproject.app")

    def test_activation_blocked_when_subdomain_taken_meanwhile(self):
        order = self.order()
        make_store(make_member(sub="lain", email="lain@gmail.com"), "warungbudi")
        r = self.activate(order)
        self.assertEqual(r.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PAYMENT)

    def test_renewal_extends_switches_package_and_needs_approval_for_new_address(self):
        store = make_store(self.member, days=5)
        old_until = store.active_until
        r = self.client.post(
            reverse("toko:perpanjang", args=["warungbudi"]),
            {"package": Package.objects.get(code="tumbuh").pk, "new_subdomain": "budimart"},
        )
        self.assertEqual(r.status_code, 302)
        order = Order.objects.get(order_type=Order.TYPE_RENEWAL)
        self.assertEqual((order.store, order.subdomain, order.package_name), (store, "budimart", "Tumbuh"))
        # Hanya satu perpanjangan terbuka.
        r = self.client.get(reverse("toko:perpanjang", args=["warungbudi"]))
        self.assertEqual(r["Location"], f"/akun/pesanan/{order.code}/")

        page = self.admin.get(reverse("panel:pesanan-update", args=[order.pk]))
        self.assertContains(page, "Setujui ganti alamat")
        self.activate(order)  # tanpa centang persetujuan
        store.refresh_from_db()
        self.assertEqual(store.subdomain, "warungbudi")
        self.assertEqual((store.package_name, store.base_outlets), ("Tumbuh", 10))
        self.assertEqual(store.active_until, add_months(old_until))

    def test_renewal_with_approved_new_address(self):
        store = make_store(self.member)
        order = Order.objects.create(
            member=self.member, order_type=Order.TYPE_RENEWAL, store=store, subdomain="budimart",
            package=store.package, package_name="Tunas", package_category="kasir", price_text="x",
        )
        self.activate(order, approve_subdomain="on")
        store.refresh_from_db()
        self.assertEqual(store.subdomain, "budimart")
        self.assertEqual(store_client("budimart").get("/").status_code, 200)
        self.assertEqual(store_client("warungbudi").get("/").status_code, 404)

    def test_renewal_of_expired_store_counts_from_today(self):
        store = make_store(self.member, days=-12)
        order = Order.objects.create(
            member=self.member, order_type=Order.TYPE_RENEWAL, store=store, package=store.package,
            package_name="Tunas", package_category="kasir", price_text="x",
        )
        self.activate(order)
        store.refresh_from_db()
        self.assertEqual(store.active_until, add_months(timezone.localdate()))

    def test_downgrade_deactivates_extra_outlets(self):
        store = make_store(self.member, package="tumbuh")
        for n in range(2, 5):
            Outlet.objects.create(store=store, number=n, name=f"Cabang {n}")
        order = Order.objects.create(
            member=self.member, order_type=Order.TYPE_RENEWAL, store=store, package=Package.objects.get(code="tunas"),
            package_name="Tunas", package_category="kasir", price_text="x",
        )
        self.activate(order)
        self.assertEqual(list(store.outlets.filter(is_active=True).values_list("number", flat=True)), [1, 2])


# ---------------------------------------------------------------------------
# Dashboard pemilik (hansproject.app/akun/toko/...)
# ---------------------------------------------------------------------------
class OwnerDashboardTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member()
        self.store = make_store(self.member)
        login_member(self.client, self.member)
        self.url = lambda name, *args: reverse(f"toko:{name}", args=["warungbudi", *args])

    def test_all_pages_render(self):
        product = Product.objects.create(store=self.store, name="Kopi", price=5000)
        cashier = make_cashier(self.store)
        sale = services.checkout(cashier, {"key": "abcdefgh1", "items": [{"id": product.pk, "qty": 1}], "method": "qris"}).sale
        for name, args in [
            ("ringkasan", []), ("barang", []), ("barang-baru", []), ("barang-ubah", [product.pk]), ("kategori", []),
            ("outlet", []), ("outlet-baru", []), ("outlet-ubah", [self.store.outlets.first().pk]), ("transaksi", []),
            ("transaksi-detail", [sale.pk]), ("transaksi-struk", [sale.pk]), ("laporan", []), ("pengaturan", []),
            ("perpanjang", []),
        ]:
            with self.subTest(page=name):
                r = self.client.get(self.url(name, *args))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r["Cache-Control"], "no-store, max-age=0")
        self.assertEqual(self.client.get(self.url("laporan") + "?periode=bulan-lalu").status_code, 200)
        self.assertEqual(self.client.get(self.url("laporan") + "?dari=2026-01-01&sampai=2026-03-31").status_code, 200)

    def test_requires_login_and_ownership(self):
        self.assertEqual(Client(HTTP_HOST="testserver").get(self.url("ringkasan")).status_code, 302)
        other = Client(HTTP_HOST="testserver")
        login_member(other, make_member(sub="sub-2", email="lain@gmail.com"))
        for name in ["ringkasan", "barang", "laporan", "laporan-unduh", "pengaturan"]:
            self.assertEqual(other.get(self.url(name)).status_code, 404)

    def test_cannot_touch_other_stores_data(self):
        other_store = make_store(make_member(sub="sub-2", email="lain@gmail.com"), "tokolain")
        foreign = Product.objects.create(store=other_store, name="Rahasia", price=1)
        self.assertEqual(self.client.get(self.url("barang-ubah", foreign.pk)).status_code, 404)
        self.assertEqual(self.client.post(self.url("barang-hapus", foreign.pk)).status_code, 404)
        self.assertTrue(Product.objects.filter(pk=foreign.pk).exists())
        foreign_outlet = other_store.outlets.first()
        self.assertEqual(self.client.get(self.url("outlet-ubah", foreign_outlet.pk)).status_code, 404)

    def test_product_crud_with_rupiah_input(self):
        cat = Category.objects.create(store=self.store, name="Minuman")
        r = self.client.post(self.url("barang-baru"), {"name": " Es  Teh ", "price": "Rp 4.000", "category": cat.pk, "code": "", "is_active": "on"})
        self.assertEqual(r.status_code, 302)
        product = self.store.products.get()
        self.assertEqual((product.name, product.price, product.category), ("Es Teh", 4000, cat))
        # Kategori toko lain tidak bisa dipilih.
        foreign_cat = Category.objects.create(store=make_store(make_member(sub="s3", email="c@gmail.com"), "toko3"), name="X")
        r = self.client.post(self.url("barang-ubah", product.pk), {"name": "Es Teh", "price": "4000", "category": foreign_cat.pk})
        self.assertEqual(r.status_code, 400)
        self.client.post(self.url("barang-hapus", product.pk))
        self.assertFalse(self.store.products.exists())

    def test_product_code_unique_per_store(self):
        Product.objects.create(store=self.store, name="A", price=1, code="899123")
        r = self.client.post(self.url("barang-baru"), {"name": "B", "price": "1", "code": "899123"})
        self.assertContains(r, "sudah dipakai", status_code=400)

    def test_outlet_and_cashier_account(self):
        outlet = self.store.outlets.first()
        base = {"outlet-name": "Toko utama", "outlet-address": "", "outlet-is_active": "on", "kasir-username": "Kasir.Utama"}
        r = self.client.post(self.url("outlet-ubah", outlet.pk), {**base, "kasir-pin": "111111", "kasir-pin2": "111111"})
        self.assertContains(r, "mudah ditebak", status_code=400)
        r = self.client.post(self.url("outlet-ubah", outlet.pk), {**base, "kasir-pin": PIN, "kasir-pin2": "000001"})
        self.assertContains(r, "tidak sama", status_code=400)
        r = self.client.post(self.url("outlet-ubah", outlet.pk), {**base, "kasir-pin": PIN, "kasir-pin2": PIN})
        self.assertEqual(r.status_code, 302)
        cashier = Cashier.objects.get(outlet=outlet)
        self.assertEqual(cashier.username, "kasir.utama")
        self.assertNotIn(PIN, cashier.pin_hash)
        # Edit tanpa PIN: PIN lama tetap.
        r = self.client.post(self.url("outlet-ubah", outlet.pk), {**base, "kasir-is_active": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(cashier_auth.authenticate(self.store, "kasir.utama", PIN).cashier)

    def test_outlet_limit(self):
        self.client.post(self.url("outlet-baru"), {"outlet-name": "Cabang", "outlet-is_active": "on", "kasir-username": "kasir2", "kasir-pin": PIN, "kasir-pin2": PIN})
        self.assertEqual(self.store.outlets.filter(is_active=True).count(), 2)
        # Tunas = 2 outlet: halaman tambah outlet dialihkan.
        self.assertEqual(self.client.get(self.url("outlet-baru")).status_code, 302)
        r = self.client.post(self.url("outlet-baru"), {"outlet-name": "Cabang 3", "outlet-is_active": "on", "kasir-username": "kasir3", "kasir-pin": PIN, "kasir-pin2": PIN})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.store.outlets.count(), 2)

    def test_locked_store_is_read_only_but_reports_work(self):
        self.store.active_until = timezone.localdate() - timedelta(days=10)
        self.store.save()
        r = self.client.post(self.url("barang-baru"), {"name": "Kopi", "price": "5000"})
        self.assertIn("ok=terkunci", r["Location"])
        self.assertFalse(self.store.products.exists())
        self.assertEqual(self.client.get(self.url("laporan")).status_code, 200)
        self.assertEqual(self.client.get(self.url("laporan-unduh")).status_code, 200)
        self.assertContains(self.client.get(self.url("ringkasan")), "Perpanjang")

    def test_csv_export_escapes_formulas(self):
        product = Product.objects.create(store=self.store, name="=HYPERLINK(1)", price=1000)
        services.checkout(make_cashier(self.store), {"key": "abcdefgh2", "items": [{"id": product.pk, "qty": 2}], "method": "qris"})
        r = self.client.get(self.url("laporan-unduh") + "?jenis=barang")
        body = r.content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK(1)", body)
        self.assertIn("attachment;", r["Content-Disposition"])

    def test_void_sale(self):
        product = Product.objects.create(store=self.store, name="Kopi", price=5000)
        sale = services.checkout(make_cashier(self.store), {"key": "abcdefgh3", "items": [{"id": product.pk, "qty": 1}], "method": "qris"}).sale
        self.assertEqual(self.client.post(self.url("transaksi-detail", sale.pk), {"reason": ""}).status_code, 400)
        self.client.post(self.url("transaksi-detail", sale.pk), {"reason": "salah input"})
        sale.refresh_from_db()
        self.assertTrue(sale.is_void)
        today = timezone.localdate()
        self.assertEqual(services.build_report(self.store, today, today).revenue, 0)


# ---------------------------------------------------------------------------
# Kasir di subdomain
# ---------------------------------------------------------------------------
class CashierLoginTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.store = make_store(make_member())
        self.cashier = make_cashier(self.store)
        self.kasir = store_client()

    def test_login_and_pos_page(self):
        self.assertEqual(self.kasir.get("/kasir/")["Location"], "/kasir/masuk/")
        Product.objects.create(store=self.store, name="Kopi Susu", price=5000)
        Product.objects.create(store=self.store, name="Lama", price=1, is_active=False)
        r = kasir_login(self.kasir, "KASIR1")
        self.assertEqual(r["Location"], "/kasir/")
        cookie = r.cookies[cashier_auth.COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["domain"], "")  # hanya untuk subdomain ini
        page = self.kasir.get("/kasir/")
        self.assertContains(page, "Kopi Susu")
        self.assertNotContains(page, "Lama")
        self.assertEqual(page["Cache-Control"], "no-store, max-age=0")
        self.assertIn("default-src 'none'", page["Content-Security-Policy"])

    def test_wrong_pin_locks_after_five_tries(self):
        for _ in range(5):
            self.assertContains(kasir_login(self.kasir, pin="000000"), "PIN salah", status_code=400)
        r = kasir_login(self.kasir)
        self.assertContains(r, "terkunci sementara", status_code=400)
        self.cashier.refresh_from_db()
        self.cashier.locked_until = timezone.now() - timedelta(seconds=1)
        self.cashier.save()
        self.assertEqual(kasir_login(self.kasir).status_code, 302)

    def test_unknown_user_same_message(self):
        self.assertContains(kasir_login(self.kasir, username="tidakada"), "Nama pengguna atau PIN salah", status_code=400)

    def test_session_bound_to_its_store(self):
        other = make_store(make_member(sub="s2", email="b@gmail.com"), "tokolain")
        make_cashier(other)  # nama pengguna sama, toko lain
        r = kasir_login(self.kasir)
        token = r.cookies[cashier_auth.COOKIE].value
        foreign = store_client("tokolain")
        foreign.cookies[cashier_auth.COOKIE] = token
        self.assertEqual(foreign.get("/kasir/")["Location"], "/kasir/masuk/")

    def test_inactive_outlet_or_cashier_cannot_login(self):
        Outlet.objects.filter(pk=self.cashier.outlet_id).update(is_active=False)
        self.assertEqual(kasir_login(self.kasir).status_code, 400)
        Outlet.objects.filter(pk=self.cashier.outlet_id).update(is_active=True)
        Cashier.objects.filter(pk=self.cashier.pk).update(is_active=False)
        self.assertEqual(kasir_login(self.kasir).status_code, 400)

    def test_pin_change_logs_out_devices(self):
        kasir_login(self.kasir)
        self.assertEqual(self.kasir.get("/kasir/").status_code, 200)
        cashier_auth.set_pin(self.cashier, "735194")
        self.cashier.save()
        self.assertEqual(self.kasir.get("/kasir/").status_code, 302)

    def test_logout(self):
        kasir_login(self.kasir)
        self.kasir.post("/kasir/keluar/")
        self.assertFalse(CashierSession.objects.exists())
        self.assertEqual(self.kasir.get("/kasir/").status_code, 302)

    def test_grace_then_locked(self):
        kasir_login(self.kasir)
        self.store.active_until = timezone.localdate() - timedelta(days=3)
        self.store.save()
        self.assertContains(self.kasir.get("/kasir/"), "masih bisa dipakai sampai")
        self.store.active_until = timezone.localdate() - timedelta(days=8)
        self.store.save()
        r = self.kasir.get("/kasir/")
        self.assertContains(r, "Kasir sedang terkunci", status_code=403)
        self.assertEqual(store_client().get("/kasir/masuk/").status_code, 403)

    def test_suspended_store_locked(self):
        kasir_login(self.kasir)
        Store.objects.filter(pk=self.store.pk).update(status=Store.STATUS_SUSPENDED)
        self.assertEqual(self.kasir.get("/kasir/").status_code, 403)


class CheckoutTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.store = make_store(make_member())
        self.cashier = make_cashier(self.store)
        self.kopi = Product.objects.create(store=self.store, name="Kopi", price=5000)
        self.roti = Product.objects.create(store=self.store, name="Roti", price=7500)
        self.kasir = store_client()
        kasir_login(self.kasir)

    def test_server_computes_totals(self):
        r = pay(self.kasir, [{"id": self.kopi.pk, "qty": 2, "price": 1}, {"id": self.roti.pk, "qty": 1}], paid=20000)
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()["sale"]
        self.assertEqual((body["total"], body["change"], body["number"]), (17500, 2500, "1-00001"))
        sale = Sale.objects.get()
        self.assertEqual([(i.name, i.qty, i.line_total) for i in sale.items.all()], [("Kopi", 2, 10000), ("Roti", 1, 7500)])
        self.assertEqual(pay(self.kasir, [{"id": self.kopi.pk, "qty": 1}], paid=5000).json()["sale"]["number"], "1-00002")

    def test_discounts(self):
        r = pay(self.kasir, [{"id": self.roti.pk, "qty": 2}], discount_type="persen", discount_value=10, method="qris")
        self.assertEqual(r.json()["sale"]["total"], 13500)
        r = pay(self.kasir, [{"id": self.roti.pk, "qty": 1}], discount_type="rp", discount_value=500, method="transfer")
        self.assertEqual(r.json()["sale"]["total"], 7000)
        r = pay(self.kasir, [{"id": self.roti.pk, "qty": 1}], discount_type="rp", discount_value=99999, method="qris")
        self.assertEqual(r.status_code, 400)
        r = pay(self.kasir, [{"id": self.roti.pk, "qty": 1}], discount_type="persen", discount_value=150, method="qris")
        self.assertEqual(r.status_code, 400)

    def test_rejects_bad_input(self):
        other = make_store(make_member(sub="s2", email="b@gmail.com"), "tokolain")
        foreign = Product.objects.create(store=other, name="Asing", price=1)
        inactive = Product.objects.create(store=self.store, name="Habis", price=1, is_active=False)
        cases = [
            [],
            [{"id": foreign.pk, "qty": 1}],
            [{"id": inactive.pk, "qty": 1}],
            [{"id": self.kopi.pk, "qty": 0}],
            [{"id": self.kopi.pk, "qty": 10000}],
            [{"id": "x", "qty": 1}],
            [{"id": self.kopi.pk, "qty": True}],
        ]
        for items in cases:
            with self.subTest(items=items):
                self.assertEqual(pay(self.kasir, items, paid=10**6).status_code, 400)
        self.assertEqual(pay(self.kasir, [{"id": self.kopi.pk, "qty": 1}], paid=4000).status_code, 400)
        self.assertEqual(pay(self.kasir, [{"id": self.kopi.pk, "qty": 1}], method="hutang").status_code, 400)
        self.assertEqual(pay(self.kasir, [{"id": self.kopi.pk, "qty": 1}], key="x").status_code, 400)
        r = self.kasir.post("/kasir/bayar/", "bukan json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Sale.objects.exists())

    def test_same_key_saved_once(self):
        first = pay(self.kasir, [{"id": self.kopi.pk, "qty": 1}], key="kunci-sama-123", paid=5000)
        again = pay(self.kasir, [{"id": self.kopi.pk, "qty": 3}], key="kunci-sama-123", paid=50000)
        self.assertEqual((first.status_code, again.status_code), (201, 200))
        self.assertTrue(again.json()["duplicate"])
        self.assertEqual(Sale.objects.count(), 1)

    def test_not_logged_in_gets_json_401(self):
        r = pay(store_client(), [{"id": self.kopi.pk, "qty": 1}], paid=5000)
        self.assertEqual(r.status_code, 401)
        self.assertTrue(r.json()["login"])

    def test_csrf_enforced(self):
        client = Client(HTTP_HOST="warungbudi.hansproject.app", enforce_csrf_checks=True)
        client.cookies = self.kasir.cookies
        body = json.dumps({"key": "abcdefgh9", "items": [{"id": self.kopi.pk, "qty": 1}], "method": "qris"})
        self.assertEqual(client.post("/kasir/bayar/", body, content_type="application/json").status_code, 403)
        client.get("/kasir/")
        token = client.cookies["hp_token"].value
        r = client.post("/kasir/bayar/", body, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 201)

    def test_receipt_and_history_limited_to_own_outlet(self):
        sale_id = Sale.objects.get(pk=Sale.objects.create(
            store=self.store, outlet=self.store.outlets.first(), cashier_name="kasir1", number="1-09999", client_key="manual-0001",
            subtotal=1, total=1, paid=1,
        ).pk).pk
        r = self.kasir.get(f"/kasir/struk/{sale_id}/")
        self.assertContains(r, "1-09999")
        second = Outlet.objects.create(store=self.store, number=2, name="Cabang")
        other_sale = Sale.objects.create(store=self.store, outlet=second, cashier_name="x", number="2-00001", client_key="manual-0002", subtotal=1, total=1, paid=1)
        self.assertEqual(self.kasir.get(f"/kasir/struk/{other_sale.pk}/").status_code, 404)
        history = self.kasir.get("/kasir/riwayat/")
        self.assertContains(history, "1-09999")
        self.assertNotContains(history, "2-00001")


# ---------------------------------------------------------------------------
# Laporan & pembersihan data
# ---------------------------------------------------------------------------
class ReportTests(SeededTestCase):
    def test_report_totals(self):
        store = make_store(make_member())
        cashier = make_cashier(store)
        kopi = Product.objects.create(store=store, name="Kopi", price=5000)
        teh = Product.objects.create(store=store, name="Teh", price=3000)
        services.checkout(cashier, {"key": "rep-00001", "items": [{"id": kopi.pk, "qty": 2}], "method": "tunai", "paid": 10000})
        services.checkout(cashier, {"key": "rep-00002", "items": [{"id": teh.pk, "qty": 1}], "method": "qris"})
        voided = services.checkout(cashier, {"key": "rep-00003", "items": [{"id": kopi.pk, "qty": 9}], "method": "qris"}).sale
        services.void_sale(voided, "salah input")
        today = timezone.localdate()
        report = services.build_report(store, today, today)
        self.assertEqual((report.revenue, report.count, report.void_count, report.average), (13000, 2, 1, 6500))
        self.assertEqual(report.top_products[0]["name"], "Kopi")
        self.assertEqual(report.top_products[0]["qty"], 2)
        self.assertEqual(sum(d["total"] for d in report.by_day), 13000)
        self.assertEqual({m["label"] for m in report.by_method}, {"Tunai", "QRIS"})


class CleanupTests(SeededTestCase):
    def test_deletes_only_stores_expired_over_30_days(self):
        member = make_member()
        old = make_store(member, "lamasekali", days=-31)
        Product.objects.create(store=old, name="X", price=1)
        cashier = make_cashier(old)
        services.checkout(cashier, {"key": "cln-00001", "items": [{"id": old.products.get().pk, "qty": 1}], "method": "qris"})
        recent = make_store(member, "baruhabis", days=-29)
        waiting = make_store(member, "menunggu", days=-40)
        Order.objects.create(
            member=member, order_type=Order.TYPE_RENEWAL, store=waiting, package_name="Tunas", package_category="kasir",
            price_text="x", status=Order.STATUS_CHECKING,
        )
        out = StringIO()
        call_command("pos_bersihkan", stdout=out)
        self.assertIn("1 toko dihapus", out.getvalue())
        self.assertFalse(Store.objects.filter(pk=old.pk).exists())
        self.assertFalse(Sale.objects.exists())
        self.assertTrue(Store.objects.filter(pk=recent.pk).exists())
        self.assertTrue(Store.objects.filter(pk=waiting.pk).exists())

    def test_deleting_member_deletes_store(self):
        member = make_member()
        store = make_store(member)
        product = Product.objects.create(store=store, name="X", price=1)
        services.checkout(make_cashier(store), {"key": "cln-00002", "items": [{"id": product.pk, "qty": 1}], "method": "qris"})
        member.delete()
        self.assertFalse(Store.objects.exists())
        self.assertFalse(Sale.objects.exists())


class PanelStoreTests(SeededTestCase):
    def test_admin_can_edit_store(self):
        store = make_store(make_member())
        admin = Client(HTTP_HOST="testserver")
        login_fully(admin, make_admin(with_2fa=True))
        self.assertContains(admin.get(reverse("panel:toko-list")), "warungbudi.hansproject.app")
        page = admin.get(reverse("panel:toko-update", args=[store.pk]))
        self.assertContains(page, "Data dihapus setelah")
        data = {
            "name": "Warung Budi", "subdomain": "warungbudi", "status": "ditangguhkan",
            "active_until": store.active_until.isoformat(), "package": store.package_id, "package_name": "Tunas",
            "base_outlets": 2, "extra_outlets": 1, "admin_note": "Mohon konfirmasi pembayaran.",
        }
        self.assertEqual(admin.post(reverse("panel:toko-update", args=[store.pk]), data).status_code, 302)
        store.refresh_from_db()
        self.assertEqual((store.status, store.outlet_limit), (Store.STATUS_SUSPENDED, 3))
        r = admin.post(reverse("panel:toko-update", args=[store.pk]), {**data, "subdomain": "admin"})
        self.assertEqual(r.status_code, 400)
