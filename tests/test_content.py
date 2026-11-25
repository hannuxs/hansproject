"""Harga & isi paket harus sama persis dengan docs/01-bisnis-dan-harga.md."""
from urllib.parse import unquote

from django.core.cache import cache

from apps.content.models import AddOn, ComparisonRow, Faq, LegalPage, Package, SiteSettings
from apps.content.seeding import seed
from apps.content.services import get_snapshot

from .helpers import SeededTestCase


class SeedDataTests(SeededTestCase):
    def test_package_prices_match_business_facts(self):
        tunas = Package.objects.get(code="tunas")
        tumbuh = Package.objects.get(code="tumbuh")
        rimba = Package.objects.get(code="rimba")
        self.assertEqual((tunas.price, tunas.price_suffix, tunas.outlet_count), (25000, "/bulan", 2))
        self.assertEqual((tumbuh.price, tumbuh.price_suffix, tumbuh.outlet_count), (99000, "/bulan", 10))
        self.assertEqual((rimba.price, rimba.price_prefix, rimba.monthly_price), (349000, "Mulai", 200000))
        self.assertTrue(tumbuh.is_highlighted)
        self.assertEqual(tumbuh.includes_from, tunas)
        self.assertEqual(rimba.category, Package.CATEGORY_SERVICE)

    def test_feature_counts_and_key_facts(self):
        tunas = Package.objects.get(code="tunas")
        self.assertEqual(tunas.features.count(), 11)
        self.assertEqual(Package.objects.get(code="tumbuh").features.count(), 5)
        self.assertEqual(Package.objects.get(code="rimba").features.count(), 7)
        self.assertEqual(Package.objects.get(code="rimba").notes.count(), 3)
        technical = set(tunas.features.values_list("technical", flat=True))
        self.assertIn("Penyimpanan 1 GB", technical)
        self.assertIn("2 toko, 1 subdomain & 1 akun kasir per toko", technical)

    def test_storage_migration_only_changes_untouched_text(self):
        import importlib

        from django.apps import apps as django_apps

        migration = importlib.import_module("apps.content.migrations.0003_tunas_penyimpanan_1gb")
        tunas = Package.objects.get(code="tunas")
        feature = tunas.features.get(technical="Penyimpanan 1 GB")
        feature.technical = "Penyimpanan 1,5 GB"
        feature.save()
        row = ComparisonRow.objects.get(label="Penyimpanan")
        row.values = {**row.values, "tunas": "2 GB (diubah pemilik)"}
        row.save()
        migration.forwards(django_apps, None)
        feature.refresh_from_db()
        row.refresh_from_db()
        self.assertEqual(feature.technical, "Penyimpanan 1 GB")
        self.assertEqual(row.values["tunas"], "2 GB (diubah pemilik)")

    def test_addon_prices(self):
        self.assertEqual(AddOn.objects.get(group="outlet").price, 15000)
        storage = dict(AddOn.objects.filter(group="storage").values_list("name", "price"))
        self.assertEqual(storage, {"+1 GB": 10000, "+5 GB": 35000, "+10 GB": 60000})

    def test_seed_is_idempotent_and_respects_owner_deletions(self):
        counts = (Package.objects.count(), Faq.objects.count(), ComparisonRow.objects.count())
        Faq.objects.filter(question__startswith="Bayarnya").delete()
        self.assertEqual(seed(), {})  # jalan ulang tidak mengubah apa pun
        self.assertEqual(Package.objects.count(), counts[0])
        self.assertEqual(Faq.objects.count(), counts[1] - 1)  # tidak dihidupkan lagi

    def test_placeholder_faq_hidden(self):
        self.assertFalse(Faq.objects.get(question="Bisa pindah paket?").is_active)

    def test_legal_pages_are_final(self):
        self.assertEqual(LegalPage.objects.filter(is_draft=False).count(), 2)
        for page in LegalPage.objects.all():
            self.assertNotIn("PERLU", page.body, page.slug)  # tidak ada lagi bagian yang belum diisi

    def test_outlet_tip_matches_docs_example(self):
        tip = get_snapshot().outlet_tip
        self.assertEqual((tip.extra_outlets, tip.base_total), (5, 100000))  # Tunas + 5 toko = Rp100.000


class HomePageTests(SeededTestCase):
    def test_prices_rendered_from_database(self):
        html = self.client.get("/").content.decode()
        for text in ["Rp25.000", "Rp99.000", "Rp349.000"]:
            self.assertIn(text, html)
        kasir = self.client.get("/aplikasi-kasir/").content.decode()
        for text in ["Rp25.000", "Rp99.000", "Rp15.000", "Rp10.000", "Rp35.000", "Rp60.000"]:
            self.assertIn(text, kasir)
        self.assertIn("Rp25 ribu", kasir)  # judul halaman kasir
        jasa = self.client.get("/website-aplikasi/").content.decode()
        for text in ["Rp349.000", "Rp200.000"]:
            self.assertIn(text, jasa)
        Package.objects.filter(code="tunas").update(price=30000)
        cache.clear()
        self.assertIn("Rp30.000", self.client.get("/").content.decode())
        self.assertIn("Rp30.000", self.client.get("/aplikasi-kasir/").content.decode())

    def test_home_is_platform_not_cashier(self):
        """Halaman utama = solusi digital (ringkas); detail kasir/SIM/jasa ada di halamannya sendiri."""
        html = self.client.get("/").content.decode()
        self.assertIn("Solusi <span class=\"hl\">digital</span>", html)
        for path in ("/aplikasi-kasir/", "/sistem-informasi-manajemen/", "/website-aplikasi/"):
            self.assertIn(f'href="{path}"', html)
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertIn("Sistem Informasi Manajemen", html)
        self.assertNotIn("SIM Wilayah", html)
        # Detail kasir tidak lagi memenuhi halaman utama.
        for kasir_only in ('id="fitur"', 'id="halaman-promosi"', "data-calc", 'id="detail-teknis"'):
            self.assertNotIn(kasir_only, html)
        # Tab harga: Kasir & SIM, masing-masing Tunas & Tumbuh.
        self.assertIn('id="harga-kasir"', html)
        self.assertIn('id="harga-sim"', html)
        for code in ("tunas", "tumbuh", "sim-tunas", "sim-tumbuh"):
            self.assertIn(f'id="hp-{code}"', html)

    def test_users_count_on_home_only_and_editable(self):
        from django.core.cache import cache

        from apps.content.models import SiteSettings

        self.assertIn("sudah dipakai <b>±900 orang</b>", self.client.get("/").content.decode())
        self.assertNotIn("±900 orang", self.client.get("/aplikasi-kasir/").content.decode())
        SiteSettings.objects.filter(pk=1).update(users_count=1250)
        cache.clear()
        self.assertIn("±1.250 orang", self.client.get("/").content.decode())
        SiteSettings.objects.filter(pk=1).update(users_count=None)
        cache.clear()
        self.assertNotIn("sudah dipakai", self.client.get("/").content.decode())

    def test_rimba_not_in_same_pricing_grid(self):
        html = self.client.get("/aplikasi-kasir/").content.decode()
        plans = html[html.index('class="plans"'): html.index('class="addons"')]
        self.assertIn("Tunas", plans)
        self.assertIn("Tumbuh", plans)
        self.assertNotIn("Rimba", plans)

    def test_no_whatsapp_anywhere(self):
        self.assertFalse(hasattr(SiteSettings, "whatsapp_number"))
        for path in ["/", "/syarat-ketentuan/", "/kebijakan-privasi/", "/tidak-ada/", "/.well-known/security.txt", "/akun/masuk/"]:
            body = unquote(self.client.get(path).content.decode()).lower()
            for word in ["wa.me", "whatsapp", "api.whatsapp"]:
                self.assertNotIn(word, body, path)

    def test_instagram_dm_link_from_settings(self):
        html = self.client.get("/").content.decode()
        self.assertIn('href="https://www.instagram.com/hansproject.app"', html)
        self.assertIn("@hansproject.app", html)
        self.assertNotIn("ig.me/", html)
        # Kolom lama instagram_url diabaikan: semua link tetap dari username.
        site = SiteSettings.load()
        site.instagram_url = "https://www.instagram.com/akun-lain/"
        site.save()
        html = self.client.get("/").content.decode()
        self.assertNotIn("akun-lain", html)
        site.instagram_username = ""
        site.save()
        self.assertNotIn("instagram.com/", self.client.get("/").content.decode())

    def test_ask_buttons_lead_to_ask_page(self):
        html = self.client.get("/aplikasi-kasir/").content.decode()
        for topic in ("kasir", "tambah-toko", "tambah-simpan"):
            self.assertIn(f'href="/akun/chat/baru/?topik={topic}"', html)
        self.assertIn('href="/akun/chat/baru/?topik=tiket"', self.client.get("/").content.decode())
        self.assertIn('href="/akun/chat/baru/?topik=sim"', self.client.get("/sistem-informasi-manajemen/").content.decode())

    def test_technical_terms_shown_by_default(self):
        html = self.client.get("/aplikasi-kasir/").content.decode()
        self.assertIn('<input type="checkbox" id="tech-harga" checked>', html)

    def test_testimonials_hidden_by_default(self):
        self.assertNotIn('id="testimoni"', self.client.get("/").content.decode())

    def test_legal_pages_and_seo_files(self):
        for path in ["/syarat-ketentuan/", "/kebijakan-privasi/", "/robots.txt", "/sitemap.xml", "/manifest.webmanifest"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        terms = self.client.get("/syarat-ketentuan/")
        self.assertNotContains(terms, "Draf")
        self.assertContains(terms, "Berlaku sejak: 22 November 2026")
        self.assertContains(terms, "Sistem Informasi Manajemen")
        self.assertContains(self.client.get("/kebijakan-privasi/"), "data warga")
        privacy = self.client.get("/kebijakan-privasi/")
        for text in ["3 x 24 jam", "10 tahun", "30 hari setelah masa aktif habis", "Limited Use", "@hansproject.app"]:
            self.assertContains(privacy, text)


class NavigationTests(SeededTestCase):
    def test_bottom_nav_replaces_burger_and_floating_whatsapp(self):
        html = self.client.get("/").content.decode()
        self.assertIn('class="bottom-nav"', html)
        # Beranda · Solusi · Harga (tengah) · Cara mulai · Bantuan; halaman solusi di menu atas.
        for href in ["/#beranda", "/#solusi", "/#harga", "/#cara-daftar", "/#faq", "/aplikasi-kasir/", "/sistem-informasi-manajemen/", "/website-aplikasi/"]:
            self.assertIn(f'href="{href}"', html)
        self.assertNotIn("nav-mobile", html)  # menu burger sudah dihapus
        self.assertNotIn("wa-float", html)  # tombol WhatsApp melayang sudah dihapus
        header = html[html.index('<header class="site-header">'): html.index("</header>")]
        self.assertNotIn("wa.me", header)  # tidak ada tombol kontak WhatsApp di header

    def test_account_buttons_on_public_page(self):
        """Halaman publik (di-cache) memuat versi tamu & pelanggan; JS memilih lewat cookie penanda."""
        html = self.client.get("/").content.decode()
        self.assertIn('class="btn btn-sm account-btn when-guest" href="/akun/masuk/"', html)
        self.assertIn('class="profile-btn when-member" href="/akun/"', html)
        # Tombol akun pindah ke header (juga di HP); menu bawah berisi "Bantuan".
        nav = html[html.index('<nav class="bottom-nav"'):]
        self.assertNotIn("/akun/", nav[: nav.index("</nav>")])
        self.assertIn('href="/#faq"', nav)

    def test_profile_shown_when_member_logged_in(self):
        from types import SimpleNamespace

        from django.template.loader import render_to_string

        member = SimpleNamespace(display_name="budi", initial="B")
        for place in ("header",):
            out = render_to_string("components/account_button.html", {"place": place, "member": member})
            self.assertIn('href="/akun/"', out)
            self.assertIn(">B<", out)
            self.assertNotIn("/akun/masuk/", out)
        self.assertNotIn("Daftar", render_to_string("components/account_button.html", {"place": "cta", "member": member}))

    def test_package_buttons_are_order_links(self):
        html = self.client.get("/").content.decode()
        for code in ("tunas", "tumbuh"):
            self.assertIn(f'href="/akun/pesan/{code}/"', html)
            self.assertNotIn(f'data-wa="{code}"', html)  # tidak lagi ke WhatsApp
        # Paket SIM belum berharga (Rp0): tampil "Segera diumumkan" + "Tanya harga", tidak bisa dipesan.
        for code in ("sim-tunas", "sim-tumbuh"):
            self.assertNotIn(f'href="/akun/pesan/{code}/"', html)
        self.assertIn("Segera diumumkan", html)
        self.assertEqual(html.count("order-btn"), 4)  # satu tombol per paket (2 kasir + 2 SIM)
        self.assertIn('href="/akun/pesan/rimba/"', self.client.get("/website-aplikasi/").content.decode())
        Package.objects.filter(code="sim-tunas").update(price=50000)
        cache.clear()
        self.assertIn('href="/akun/pesan/sim-tunas/"', self.client.get("/").content.decode())
