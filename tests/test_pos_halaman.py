"""Halaman toko (<toko>.hansproject.app/): template, palet dari satu warna, draf/pratinjau/terbit,
barang unggulan, dan panduan "Langkah memulai toko" di luar tab."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from datetime import timedelta

from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.pos import palette
from apps.pos.models import CashierSession, Product, StoreHighlight, StorePage

from .helpers import SeededTestCase
from .test_members import login_member, make_member, png_upload
from .test_pos import make_cashier, make_store, set_until, store_client

TMP_MEDIA = Path(tempfile.gettempdir()) / "hansproject-test-media"


class PaletteTests(SimpleTestCase):
    COLORS = ["#c2410c", "#facc15", "#ffffff", "#000000", "#777777", "#22d3ee", "#a3e635", "#1d4ed8", "#f9a8d4", "#7c3aed"]

    def test_readable_for_any_color(self):
        white = (1.0, 1.0, 1.0)
        for color in self.COLORS:
            with self.subTest(color=color):
                p = palette.build(color)
                rgb = {k: palette._rgb(v) for k, v in p.items()}
                self.assertGreaterEqual(palette.contrast(rgb["brand"], white), 4.5)  # tombol: teks putih
                self.assertGreaterEqual(palette.contrast(rgb["muted"], rgb["bg"]), 4.5)
                self.assertGreaterEqual(palette.contrast(rgb["ink"], rgb["bg"]), 7)
                self.assertGreaterEqual(palette.contrast(rgb["accent-ink"], rgb["accent-soft"]), 4.5)
                self.assertGreaterEqual(palette.contrast(rgb["on-deep"], rgb["deep"]), 7)
                self.assertGreaterEqual(len(set(p.values())), 12)  # satu warna -> banyak warna turunan

    def test_normalize_and_css(self):
        self.assertEqual(palette.normalize("ABCDEF"), "#abcdef")
        self.assertIsNone(palette.normalize("red"))
        self.assertIsNone(palette.normalize("#abc;}body{"))
        css = palette.css("#15803d")
        self.assertTrue(css.startswith(":root{--hp-brand:#"))
        self.assertIn("--hp-grad:linear-gradient(", css)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class StorePageTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member()
        self.store = make_store(self.member, address="Jl. Melati 3")
        login_member(self.client, self.member)
        self.url = reverse("toko:halaman", args=["warungbudi"])
        self.preview = reverse("toko:halaman-pratinjau", args=["warungbudi"])
        self.kopi = Product.objects.create(store=self.store, name="Kopi Susu Gula Aren", price=18000)

    def tearDown(self):
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)
        super().tearDown()

    def save(self, **data):
        payload = {"aksi": "simpan", "template": "sederhana", "color": "#15803d", "tagline": "", "about": "", "hours": "",
                   "phone": "", "instagram": "", "maps_url": "", "show_prices": "on"}
        payload.update(data)
        return self.client.post(self.url, payload)

    def act(self, aksi, **data):
        return self.client.post(self.url, {"aksi": aksi, **data})

    def add_highlight(self, **data):
        payload = {"aksi": "unggulan", "unggulan-product": "", "unggulan-title": "", "unggulan-caption": ""}
        payload.update({f"unggulan-{k}": v for k, v in data.items()})
        return self.client.post(self.url, payload)

    # --- Draf, pratinjau, terbit -------------------------------------------------
    def test_draft_preview_publish_flow(self):
        self.assertContains(self.client.get(self.url), "Belum terbit")
        r = self.save(template="menu", color="#1D4ED8", tagline="Kopi enak dekat kampus", about="Buka sejak 2019.\nBiji kopi lokal.",
                      hours="Setiap hari 08.00–22.00", phone="0812-3456-7890", instagram="@kopiku", maps_url="https://maps.app.goo.gl/abc123")
        self.assertRedirects(r, self.url + "?ok=halaman-draf", fetch_redirect_response=False)
        page = StorePage.objects.get(store=self.store)
        self.assertEqual((page.template, page.color, page.instagram), ("menu", "#1d4ed8", "kopiku"))

        # Draf belum terlihat pengunjung.
        public = store_client().get("/")
        self.assertContains(public, "segera hadir")
        self.assertEqual(public["X-Robots-Tag"], "noindex, nofollow")

        # Pratinjau: hanya pemilik, isi draf + bilah pratinjau.
        pv = self.client.get(self.preview)
        self.assertContains(pv, "Kopi enak dekat kampus")
        self.assertContains(pv, "tpl-menu")
        self.assertContains(pv, "/_tema/v1/1d4ed8.css")
        self.assertContains(pv, "Pratinjau")
        self.assertContains(pv, 'value="terbitkan"')
        self.assertContains(pv, "Rp18.000")  # daftar harga
        self.assertContains(pv, "tel:081234567890")
        self.assertIn("noindex", pv["X-Robots-Tag"])

        self.act("terbitkan")
        page.refresh_from_db()
        self.assertTrue(page.is_published)
        public = store_client().get("/")
        self.assertContains(public, "Kopi enak dekat kampus")
        self.assertContains(public, "Biji kopi lokal.")
        self.assertContains(public, "Jl. Melati 3")
        self.assertContains(public, "instagram.com/kopiku/")
        self.assertContains(public, '<link rel="canonical" href="https://warungbudi.hansproject.app/">')
        self.assertContains(public, "application/ld+json")
        self.assertNotContains(public, "Pratinjau")
        self.assertNotIn("X-Robots-Tag", public)  # halaman terbit boleh diindeks Google
        robots = store_client().get("/robots.txt").content.decode()
        self.assertIn("Allow: /$", robots)
        self.assertIn("Disallow: /", robots)
        # Kasir tetap tidak diindeks.
        self.assertEqual(store_client().get("/kasir/masuk/")["X-Robots-Tag"], "noindex, nofollow")

        # Ubah lagi: pengunjung tetap melihat versi terbit sampai diterbitkan ulang.
        self.save(template="berani", color="#b91c1c", tagline="Tagline baru")
        self.assertContains(self.client.get(self.url), "Ada perubahan belum terbit")
        public = store_client().get("/")
        self.assertContains(public, "Kopi enak dekat kampus")
        self.assertNotContains(public, "Tagline baru")
        self.act("terbitkan")
        self.assertContains(store_client().get("/"), "Tagline baru")
        self.assertContains(store_client().get("/"), "tpl-berani")

        # Sembunyikan -> kembali "segera hadir".
        self.act("sembunyikan")
        self.assertContains(store_client().get("/"), "segera hadir")
        self.assertIn("Disallow: /\n", store_client().get("/robots.txt").content.decode())

    def test_owner_can_try_other_template_in_preview(self):
        self.save(template="sederhana")
        pv = self.client.get(self.preview + "?template=etalase")
        self.assertContains(pv, "tpl-etalase")
        self.assertContains(pv, "Pakai template ini")
        self.assertContains(self.client.get(self.preview + "?template=<script>"), "tpl-sederhana")
        r = self.act("template", template="etalase")
        self.assertRedirects(r, self.preview, fetch_redirect_response=False)
        self.assertEqual(StorePage.objects.get(store=self.store).template, "etalase")

    def test_public_page_hidden_when_store_cannot_sell(self):
        self.save(tagline="Promo besar")
        self.act("terbitkan")
        self.assertContains(store_client().get("/"), "Promo besar")
        set_until(self.store, -10)  # terkunci
        r = store_client().get("/")
        self.assertNotContains(r, "Promo besar")
        self.assertContains(r, "sedang tidak tersedia")
        set_until(self.store, 10)
        self.store.is_active = False
        self.store.save()
        self.assertNotContains(store_client().get("/"), "Promo besar")

    def test_validation(self):
        r = self.save(color="merah", instagram="bukan instagram!", maps_url="https://evil.example/maps", phone="abc")
        self.assertEqual(r.status_code, 400)
        form = r.context["form"]
        self.assertEqual(set(form.errors), {"color", "instagram", "maps_url", "phone"})
        self.assertEqual(self.save(instagram="https://www.instagram.com/kopi.ku/?hl=id").status_code, 302)
        self.assertEqual(StorePage.objects.get(store=self.store).instagram, "kopi.ku")
        for ok in ["https://www.google.com/maps/place/Toko", "https://goo.gl/maps/abc", "https://maps.app.goo.gl/x"]:
            with self.subTest(ok=ok):
                self.assertEqual(self.save(maps_url=ok).status_code, 302)
        self.assertEqual(self.save(maps_url="http://maps.app.goo.gl/x").status_code, 400)
        self.assertEqual(self.save(template="lain").status_code, 400)

    def test_text_is_escaped(self):
        self.save(tagline="<script>alert(1)</script>", about="</script><b>x</b>")
        self.act("terbitkan")
        r = store_client().get("/")
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertNotContains(r, "</script><b>")
        self.assertContains(r, "&lt;script&gt;")

    def test_logo_cover_upload_and_cleanup(self):
        self.save(logo=png_upload("logo.png"), cover=png_upload("sampul.png"))
        page = StorePage.objects.get(store=self.store)
        self.assertTrue(page.logo.name.startswith(f"uploads/toko/{self.store.pk}/") and page.logo.name.endswith(".webp"))
        logo_path = Path(page.logo.path)
        self.assertTrue(logo_path.exists())
        self.act("terbitkan")
        # Gambar disajikan dari alamat toko sendiri.
        self.assertEqual(store_client().get(page.logo.url).status_code, 200)
        self.assertContains(store_client().get("/"), page.cover.url)
        # Hapus logo dari draf: file tetap ada karena masih dipakai versi terbit.
        self.save(remove_logo="on")
        self.assertTrue(logo_path.exists())
        self.act("terbitkan")
        self.assertFalse(logo_path.exists())  # setelah terbit ulang, file lama dibersihkan
        # Toko dihapus -> seluruh folder gambarnya ikut terhapus.
        folder = TMP_MEDIA / "uploads" / "toko" / str(self.store.pk)
        self.assertTrue(folder.exists())
        self.store.delete()
        self.assertFalse(folder.exists())

    def test_non_image_upload_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        r = self.save(cover=SimpleUploadedFile("x.png", b"<svg onload=alert(1)>", content_type="image/png"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("cover", r.context["form"].errors)

    # --- Barang unggulan -------------------------------------------------------------
    def test_highlights(self):
        self.assertEqual(self.add_highlight(product=self.kopi.pk, caption="Paling laris").status_code, 302)
        # Gambar lain wajib berjudul; tanpa barang & tanpa gambar ditolak.
        r = self.add_highlight()
        self.assertEqual(r.status_code, 400)
        self.assertIn("image", r.context["hl_form"].errors)
        r = self.add_highlight(image=png_upload("promo.png"))
        self.assertIn("title", r.context["hl_form"].errors)
        self.assertEqual(self.add_highlight(image=png_upload("promo.png"), title="Promo Jumat").status_code, 302)
        # Barang yang sama tidak bisa dipilih dua kali; barang toko lain tidak bisa dipilih.
        self.assertEqual(self.add_highlight(product=self.kopi.pk).status_code, 400)
        other = Product.objects.create(store=make_store(make_member("sub-2", "lain@gmail.com"), "tokolain"), name="Teh", price=1)
        self.assertEqual(self.add_highlight(product=other.pk).status_code, 400)

        items = list(StoreHighlight.objects.filter(page__store=self.store))
        self.assertEqual([h.title or h.product.name for h in items], ["Kopi Susu Gula Aren", "Promo Jumat"])
        self.act("unggulan-naik", id=items[1].pk)
        self.assertEqual(list(StoreHighlight.objects.values_list("title", flat=True)), ["Promo Jumat", ""])

        self.act("terbitkan")
        public = store_client().get("/")
        self.assertContains(public, "Barang unggulan")
        self.assertContains(public, "Promo Jumat")
        self.assertContains(public, "Paling laris")
        # Harga ikut data barang terbaru (tanpa terbit ulang).
        Product.objects.filter(pk=self.kopi.pk).update(price=21000)
        self.assertContains(store_client().get("/"), "Rp21.000")
        # Barang tidak dijual lagi -> hilang dari unggulan.
        Product.objects.filter(pk=self.kopi.pk).update(is_active=False)
        self.assertNotContains(store_client().get("/"), "Kopi Susu Gula Aren")

        # Hapus: file gambar dibersihkan setelah tidak dipakai versi terbit.
        promo = StoreHighlight.objects.get(title="Promo Jumat")
        path = Path(promo.image.path)
        self.act("unggulan-hapus", id=promo.pk)
        self.assertTrue(path.exists())
        self.act("terbitkan")
        self.assertFalse(path.exists())

    def test_highlight_limit(self):
        for i in range(StorePage.MAX_HIGHLIGHTS):
            Product.objects.create(store=self.store, name=f"Barang {i}", price=1000 + i)
        for product in Product.objects.filter(store=self.store)[: StorePage.MAX_HIGHLIGHTS]:
            self.assertEqual(self.add_highlight(product=product.pk).status_code, 302)
        last = Product.objects.filter(store=self.store).last()
        r = self.add_highlight(product=last.pk)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(StoreHighlight.objects.count(), StorePage.MAX_HIGHLIGHTS)
        self.assertContains(self.client.get(self.url), "Hapus salah satu untuk menggantinya")

    # --- Akses ---------------------------------------------------------------------------
    def test_other_member_and_locked_store(self):
        other = Client()
        login_member(other, make_member("sub-9", "orang@gmail.com"))
        self.assertEqual(other.get(self.url).status_code, 404)
        self.assertEqual(other.get(self.preview).status_code, 404)
        self.assertEqual(Client().get(self.url).status_code, 302)  # belum login
        set_until(self.store, -10)
        r = self.save(tagline="Tidak boleh")
        self.assertEqual(r.status_code, 302)
        self.assertFalse(StorePage.objects.filter(tagline="Tidak boleh").exists())

    def test_theme_css_endpoint(self):
        for client in (Client(), store_client()):
            r = client.get("/_tema/v1/15803d.css")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r["Content-Type"], "text/css; charset=utf-8")
            self.assertIn("immutable", r["Cache-Control"])
            self.assertIn("--hp-brand", r.content.decode())
        self.assertEqual(Client().get("/_tema/v99/15803d.css").status_code, 404)
        self.assertEqual(Client().get("/_tema/v1/zzzzzz.css").status_code, 404)


class SetupGuideTests(SeededTestCase):
    """Panduan tampil di SEMUA menu toko (bukan hanya Ringkasan) sampai 4 langkah selesai."""

    def setUp(self):
        super().setUp()
        self.member = make_member()
        self.store = make_store(self.member)
        login_member(self.client, self.member)

    def get(self, name="barang"):
        return self.client.get(reverse(f"toko:{name}", args=["warungbudi"]))

    def test_steps_progress_and_disappear(self):
        r = self.get("ringkasan")
        self.assertContains(r, "Langkah memulai toko")
        self.assertContains(r, "0 dari 4 selesai")
        self.assertContains(r, "Tambah barang")

        Product.objects.create(store=self.store, name="Kopi", price=5000)
        r = self.get("barang")  # tetap terlihat setelah barang diisi, di menu Barang sekalipun
        self.assertContains(r, "1 dari 4 selesai")
        self.assertContains(r, "Buat akun kasir")
        self.assertContains(r, 'aria-current="step"')

        cashier = make_cashier(self.store)
        r = self.get("kasir")
        self.assertContains(r, "2 dari 4 selesai")
        self.assertContains(r, "warungbudi.hansproject.app/kasir")

        CashierSession.objects.create(cashier=cashier, key_hash="x" * 64, last_seen_at=timezone.now(), expires_at=timezone.now() + timedelta(days=1))
        r = self.get("laporan")
        self.assertContains(r, "3 dari 4 selesai")
        self.assertContains(r, "Atur halaman toko")

        page = StorePage.objects.create(store=self.store)
        page.is_published = True
        page.save()
        for tab in ("ringkasan", "barang", "halaman", "pengaturan"):
            with self.subTest(tab=tab):
                self.assertNotContains(self.get(tab), "Langkah memulai toko")

    def test_ringkasan_has_no_old_box(self):
        self.assertNotContains(self.get("ringkasan"), "Mulai pakai kasir")
