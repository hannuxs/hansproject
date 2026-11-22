"""Area akun pelanggan: menu, Dashboard + pengumuman, refund, dan chat (bubble, gambar, balas, tutup)."""
from __future__ import annotations

import json
from datetime import timedelta

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.content.models import Announcement
from apps.members.models import ChatMessage, Conversation, Order, Refund
from apps.pos import services
from apps.pos.models import Product

from .helpers import ORDER_FORMSET_EMPTY, SeededTestCase, login_fully, make_admin
from .test_members import PrivateMediaMixin, login_member, make_member, png_upload
from .test_pos import make_cashier, make_store


class AkunNavigationTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member()
        login_member(self.client, self.member)

    def test_account_menu_replaces_site_menu(self):
        html = self.client.get("/akun/").content.decode()
        header = html[html.index('<header class="site-header">'): html.index("</header>")]
        for href in ["/akun/", "/akun/pesanan/", "/akun/layanan/", "/akun/chat/", "/akun/profil/"]:
            self.assertIn(f'href="{href}"', header)
            self.assertIn(f'href="{href}"', html[html.index('<nav class="bottom-nav"'):])
        # Satu menu "Layanan" untuk semua solusi, bukan menu "Toko" / "Wilayah" per produk.
        self.assertNotIn(">Toko<", header)
        self.assertNotIn(">Wilayah<", header)
        self.assertIn('class="profile-btn home-btn" href="/"', header)  # tombol Beranda
        self.assertNotIn('href="/#fitur"', header)  # menu situs tidak tampil di area akun
        self.assertIn('aria-current="page"', header)

    def test_every_tab_renders(self):
        for path in ["/akun/", "/akun/pesanan/", "/akun/layanan/", "/akun/toko/", "/akun/sim/", "/akun/pesan/",
                     "/akun/pesan/?layanan=kasir", "/akun/pesan/?layanan=sim", "/akun/pesan/?layanan=jasa",
                     "/akun/chat/", "/akun/chat/baru/", "/akun/profil/"]:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                self.assertNotContains(r, "{#")

    def test_old_ask_link_opens_new_chat(self):
        self.assertEqual(self.client.get("/akun/tanya/?topik=tambah-toko")["Location"], "/akun/chat/baru/?topik=tambah-toko")

    def test_unread_badge(self):
        conv = Conversation.objects.create(member=self.member)
        from apps.members import chat

        chat.post_message(conv, sender=ChatMessage.SENDER_MEMBER, text="Halo")
        self.assertNotContains(self.client.get("/akun/"), "belum dibaca")
        chat.post_message(conv, sender=ChatMessage.SENDER_ADMIN, text="Halo juga")
        self.assertContains(self.client.get("/akun/"), "belum dibaca")
        self.client.get(f"/akun/chat/{conv.pk}/")
        self.assertNotContains(self.client.get("/akun/"), "belum dibaca")


class DashboardTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member()
        login_member(self.client, self.member)

    def test_empty_state_without_store(self):
        r = self.client.get("/akun/")
        self.assertContains(r, "Belum ada layanan")
        for layanan in ("kasir", "sim", "jasa"):  # pilihan semua solusi, bukan hanya kasir
            self.assertContains(r, f'href="/akun/pesan/?layanan={layanan}"')
        self.assertNotContains(r, "Belum ada toko")
        self.assertNotContains(r, "announce-box")  # tidak ada pengumuman = tidak ada ruangnya

    def test_monitors_all_stores(self):
        a = make_store(self.member, "tokoa", name="Toko A")
        b = make_store(self.member, "tokob", name="Toko B")
        for store, price, key in [(a, 5000, "dash-0001"), (b, 7000, "dash-0002")]:
            product = Product.objects.create(store=store, name="Kopi", price=price)
            services.checkout(make_cashier(store), {"key": key, "items": [{"id": product.pk, "qty": 2}], "method": "qris"})
        foreign = make_store(make_member(sub="lain", email="lain@gmail.com"), "tokolain", name="Toko Orang Lain")
        services.checkout(make_cashier(foreign), {"key": "dash-0003", "items": [{"id": Product.objects.create(store=foreign, name="X", price=99000).pk, "qty": 1}], "method": "qris"})
        r = self.client.get("/akun/")
        self.assertContains(r, "Rp24.000")  # 2x5.000 + 2x7.000, hanya toko milik sendiri
        self.assertContains(r, "Aplikasi Kasir")
        self.assertContains(r, "2 toko")
        self.assertNotContains(r, "Toko Orang Lain")
        # Grafik & detail penjualan semua toko pindah ke Layanan › Aplikasi Kasir (Toko saya).
        r = self.client.get("/akun/toko/")
        self.assertContains(r, "Toko A")
        self.assertContains(r, "Toko B")
        self.assertNotContains(r, "Toko Orang Lain")
        self.assertContains(r, "Rp24.000")
        self.assertContains(r, "<svg")
        self.assertContains(r, "Lihat sebagai tabel")
        layanan = self.client.get("/akun/layanan/")
        self.assertContains(layanan, "Toko A")
        self.assertNotContains(layanan, "Toko Orang Lain")
        data = services.overview([a, b])
        self.assertEqual((data.today["revenue"], data.today["count"], len(data.rows)), (24000, 2, 2))

    def test_announcements_scheduled_and_without_close_button(self):
        now = timezone.now()
        Announcement.objects.create(title="Libur Lebaran", body="Layanan **libur** 2 hari.", tone="penting")
        Announcement.objects.create(title="Belum mulai", starts_at=now + timedelta(days=1))
        Announcement.objects.create(title="Sudah lewat", starts_at=now - timedelta(days=3), ends_at=now - timedelta(days=1))
        Announcement.objects.create(title="Dimatikan", is_active=False)
        r = self.client.get("/akun/")
        self.assertContains(r, "Libur Lebaran")
        self.assertContains(r, "<strong>libur</strong>")
        for hidden in ["Belum mulai", "Sudah lewat", "Dimatikan"]:
            self.assertNotContains(r, hidden)
        box = r.content.decode()
        box = box[box.index('class="announce-list"'): box.index("</section>", box.index('class="announce-list"'))]
        self.assertNotIn("<button", box)

    def test_admin_manages_announcements(self):
        admin = Client(HTTP_HOST="testserver")
        login_fully(admin, make_admin(with_2fa=True))
        self.assertEqual(admin.get(reverse("panel:pengumuman-create")).status_code, 200)
        start = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        r = admin.post(reverse("panel:pengumuman-create"), {"title": "Promo", "body": "", "tone": "promo", "starts_at": start, "ends_at": "", "is_active": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertContains(self.client.get("/akun/"), "Promo")
        r = admin.post(reverse("panel:pengumuman-create"), {"title": "Salah", "tone": "info", "starts_at": start, "ends_at": "2020-01-01T00:00", "is_active": "on"})
        self.assertEqual(r.status_code, 400)


class RefundTests(PrivateMediaMixin, SeededTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member()
        login_member(self.client, self.member)
        self.client.post("/akun/pesan/tunas/", {"subdomain": "warungbudi"})
        self.order = Order.objects.get()
        self.url = f"/akun/pesanan/{self.order.code}/"

    def pay(self):
        self.client.post(self.url, {"aksi": "bukti", "proof": png_upload()})
        self.order.refresh_from_db()

    def test_amount_copied_from_package(self):
        self.assertEqual(self.order.amount, 25000)

    def test_unpaid_cancel_has_no_refund(self):
        r = self.client.post(self.url, {"aksi": "batal"})
        self.assertIn("ok=batal", r["Location"])
        self.order.refresh_from_db()
        self.assertFalse(self.order.can_request_refund)
        self.assertEqual(self.client.post(self.url, {"aksi": "refund", "bank_name": "BRI", "account_number": "1234567", "account_holder": "Budi"}).status_code, 400)

    def test_full_refund_flow(self):
        self.pay()
        self.assertEqual(self.order.status, Order.STATUS_CHECKING)
        r = self.client.post(self.url, {"aksi": "batal"})  # sudah bayar, belum aktif -> boleh batal
        self.assertIn("ok=batal-refund", r["Location"])
        page = self.client.get(self.url)
        self.assertContains(page, "Ajukan refund")
        bad = self.client.post(self.url, {"aksi": "refund", "bank_name": "BRI", "account_number": "12ab", "account_holder": "Budi"})
        self.assertContains(bad, "hanya angka", status_code=400)
        r = self.client.post(self.url, {"aksi": "refund", "bank_name": " BRI ", "account_number": "1234-5678-90", "account_holder": "Budi Santoso"})
        self.assertIn("ok=refund", r["Location"])
        refund = Refund.objects.get()
        self.assertEqual((refund.account_number, refund.amount, refund.status), ("1234567890", 25000, Refund.STATUS_REQUESTED))
        self.assertContains(self.client.get("/akun/pesanan/"), "Refund")

        admin = Client(HTTP_HOST="testserver")
        login_fully(admin, make_admin(with_2fa=True))
        self.assertContains(admin.get(reverse("panel:refund-update", args=[refund.pk])), "1234567890")
        url = reverse("panel:refund-update", args=[refund.pk])
        # Selesai wajib ada bukti transfer.
        r = admin.post(url, {"status": "selesai", "amount": "25000", "admin_note": ""})
        self.assertEqual(r.status_code, 400)
        r = admin.post(url, {"status": "selesai", "amount": "25000", "admin_note": "Sudah ditransfer.", "transfer_proof": png_upload("tf.png")})
        self.assertEqual(r.status_code, 302)
        refund.refresh_from_db()
        self.assertIsNotNone(refund.processed_at)
        page = self.client.get(self.url)
        self.assertContains(page, "Sudah ditransfer")
        self.assertEqual(self.client.get(f"/akun/pesanan/{self.order.code}/refund/bukti/").status_code, 200)
        other = Client(HTTP_HOST="testserver")
        login_member(other, make_member(sub="s2", email="b@gmail.com"))
        self.assertEqual(other.get(f"/akun/pesanan/{self.order.code}/refund/bukti/").status_code, 404)

    def test_reject_needs_reason(self):
        self.pay()
        self.client.post(self.url, {"aksi": "batal"})
        self.client.post(self.url, {"aksi": "refund", "bank_name": "BCA", "account_number": "1234567", "account_holder": "Budi"})
        refund = Refund.objects.get()
        admin = Client(HTTP_HOST="testserver")
        login_fully(admin, make_admin(with_2fa=True))
        r = admin.post(reverse("panel:refund-update", args=[refund.pk]), {"status": "ditolak", "amount": "25000", "admin_note": ""})
        self.assertEqual(r.status_code, 400)

    def test_paid_cancelled_order_kept_when_account_deleted(self):
        self.pay()
        self.client.post(self.url, {"aksi": "batal"})
        self.client.post(self.url, {"aksi": "refund", "bank_name": "BCA", "account_number": "1234567", "account_holder": "Budi"})
        self.member.delete()
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())
        self.assertTrue(Refund.objects.exists())


class ChatTests(PrivateMediaMixin, SeededTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member()
        login_member(self.client, self.member)
        self.admin = Client(HTTP_HOST="testserver")
        login_fully(self.admin, make_admin(with_2fa=True))

    def start(self, text="Bisa tambah 2 cabang?", topic="tambah-toko"):
        r = self.client.post("/akun/chat/baru/", {"topic": topic, "text": text})
        self.assertEqual(r.status_code, 302, r.content[:500])
        return Conversation.objects.latest("pk")

    def test_start_chat_and_admin_reply_with_image_and_reply(self):
        page = self.client.get("/akun/chat/baru/?topik=tambah-toko")
        self.assertContains(page, 'value="tambah-toko" selected')
        conv = self.start()
        page = self.client.get(f"/akun/chat/{conv.pk}/")
        self.assertContains(page, "Bisa tambah 2 cabang?")
        self.assertContains(page, 'role="log"')
        first = conv.messages.get()

        # Admin membalas pesan pertama sambil mengirim gambar.
        self.assertContains(self.admin.get(reverse("panel:chat-list")), self.member.display_name)
        r = self.admin.post(reverse("panel:chat", args=[conv.pk]), {"text": "Bisa, ini daftar harganya.", "reply_to": first.pk, "image": png_upload("harga.png")})
        self.assertEqual(r.status_code, 302)
        reply = conv.messages.latest("pk")
        self.assertEqual((reply.sender, reply.reply_to_id), (ChatMessage.SENDER_ADMIN, first.pk))
        self.assertTrue(reply.image.name.endswith(".webp"))

        page = self.client.get(f"/akun/chat/{conv.pk}/")
        self.assertContains(page, "bubble-quote")
        self.assertContains(page, f"/akun/chat/{conv.pk}/gambar/{reply.pk}/")
        img = self.client.get(f"/akun/chat/{conv.pk}/gambar/{reply.pk}/")
        self.assertEqual((img.status_code, img["Content-Type"]), (200, "image/webp"))

    def test_send_via_json_and_poll(self):
        conv = self.start()
        r = self.client.post(f"/akun/chat/{conv.pk}/", {"text": "Halo lagi"}, HTTP_ACCEPT="application/json")
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("Halo lagi", body["html"])
        self.assertIn('class="bubble mine"', body["html"])
        last = body["last_id"]
        poll = self.client.get(f"/akun/chat/{conv.pk}/baru/?after={last}").json()
        self.assertEqual((poll["html"], poll["last_id"], poll["open"]), ("", last, True))
        from apps.members import chat

        chat.post_message(conv, sender=ChatMessage.SENDER_ADMIN, text="Balasan admin")
        poll = self.client.get(f"/akun/chat/{conv.pk}/baru/?after={last}").json()
        self.assertIn("Balasan admin", poll["html"])
        self.assertIn('class="bubble theirs"', poll["html"])
        empty = self.client.post(f"/akun/chat/{conv.pk}/", {"text": "  "}, HTTP_ACCEPT="application/json")
        self.assertEqual(empty.status_code, 400)

    def test_closed_chat_read_only_and_new_chat_separate(self):
        conv = self.start()
        self.admin.post(reverse("panel:chat", args=[conv.pk]), {"aksi": "tutup"})
        conv.refresh_from_db()
        self.assertEqual(conv.status, Conversation.STATUS_CLOSED)
        page = self.client.get(f"/akun/chat/{conv.pk}/")
        self.assertContains(page, "Buka obrolan baru")
        self.assertNotContains(page, "data-chat-form")
        r = self.client.post(f"/akun/chat/{conv.pk}/", {"text": "Masih bisa?"}, HTTP_ACCEPT="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(conv.messages.count(), 1)
        new = self.start("Pertanyaan lain", "umum")
        self.assertNotEqual(new.pk, conv.pk)
        self.assertEqual(new.messages.count(), 1)
        listing = self.client.get("/akun/chat/").content.decode()
        self.assertIn("Riwayat (selesai)", listing)
        self.assertIn(f"/akun/chat/{conv.pk}/", listing)  # riwayat tetap bisa dibuka
        self.assertContains(self.client.get(f"/akun/chat/{conv.pk}/"), "Bisa tambah 2 cabang?")

    def test_privacy_and_limits(self):
        conv = self.start("<script>alert(1)</script> halo")
        html = self.client.get(f"/akun/chat/{conv.pk}/").content.decode()
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("&lt;script&gt;", html)
        other = Client(HTTP_HOST="testserver")
        login_member(other, make_member(sub="s2", email="b@gmail.com"))
        self.assertEqual(other.get(f"/akun/chat/{conv.pk}/").status_code, 404)
        self.assertEqual(other.get(f"/akun/chat/{conv.pk}/baru/").status_code, 404)
        self.start("Dua", "umum")
        self.start("Tiga", "umum")
        r = self.client.post("/akun/chat/baru/", {"topic": "umum", "text": "Empat"})
        self.assertContains(r, "masih punya beberapa obrolan", status_code=400)
        self.assertEqual(Conversation.objects.filter(member=self.member).count(), 3)

    def test_panel_poll_and_dashboard_counter(self):
        conv = self.start()
        self.assertContains(self.admin.get(reverse("panel:dashboard")), "Chat perlu dibalas")
        poll = self.admin.get(reverse("panel:chat-poll", args=[conv.pk]) + "?after=0").json()
        self.assertIn("Bisa tambah 2 cabang?", poll["html"])
        self.assertIn('class="bubble theirs"', poll["html"])
        r = self.admin.post(reverse("panel:chat", args=[conv.pk]), {"text": "Siap"}, HTTP_ACCEPT="application/json")
        self.assertTrue(json.loads(r.content)["ok"])
        self.assertEqual(Client(HTTP_HOST="testserver").get(reverse("panel:chat", args=[conv.pk])).status_code, 302)


class StoreQuotaTests(SeededTestCase):
    """Paket Tunas = 2 toko: toko kedua dibuat dari kuota, bukan membeli paket lagi."""

    def setUp(self):
        super().setUp()
        self.member = make_member()
        login_member(self.client, self.member)
        self.store = make_store(self.member)  # Tunas: 2 toko, 1 sudah dibuat
        self.admin = Client(HTTP_HOST="testserver")
        login_fully(self.admin, make_admin(with_2fa=True))

    def test_package_buttons_stay_inside_account(self):
        self.assertContains(self.client.get("/akun/pesanan/"), 'href="/akun/pesan/"')
        self.assertContains(self.client.get("/akun/toko/"), 'href="/akun/toko/tambah/"')
        self.assertContains(self.client.get("/akun/pesan/"), 'href="/akun/pesan/?layanan=kasir"')  # langkah 1: pilih solusi
        page = self.client.get("/akun/pesan/?layanan=kasir")
        self.assertContains(page, 'href="/akun/pesan/tunas/"')
        self.assertContains(page, 'href="/akun/pesan/tumbuh/"')
        self.assertContains(page, "Toko › Tambah toko")  # sudah punya langganan: diarahkan ke kuota toko

    def test_quota_shown_and_second_store_from_quota(self):
        listing = self.client.get("/akun/toko/")
        self.assertContains(listing, "<b>1</b> / 2")
        self.assertContains(listing, "Paket Tunas 2")
        page = self.client.get("/akun/toko/tambah/")
        self.assertContains(page, "Masih bisa membuat <b>1 toko</b>")
        buat = reverse("toko:buat", args=[self.store.subscription_id])
        self.assertContains(page, buat)
        self.assertNotContains(page, reverse("toko:beli-toko", args=["warungbudi"]))
        r = self.client.post(buat, {
            "toko-name": "Cabang Pasar", "toko-subdomain": "cabangpasar", "kasir-username": "kasir2",
            "kasir-pin": "482915", "kasir-pin2": "482915",
        })
        self.assertEqual(r.status_code, 302)
        listing = self.client.get("/akun/toko/")
        self.assertContains(listing, "<b>2</b> / 2")
        self.assertContains(listing, "cabangpasar.hansproject.app")
        page = self.client.get("/akun/toko/tambah/")
        self.assertContains(page, "Kuota toko di langganan ini sudah penuh")
        self.assertContains(page, reverse("toko:beli-toko", args=["warungbudi"]))

    def test_buy_extra_store_then_quota_grows(self):
        url = reverse("toko:beli-toko", args=["warungbudi"])
        self.assertContains(self.client.get(url), "Rp15.000")
        r = self.client.post(url, {"quantity": "1"})
        order = Order.objects.get(order_type=Order.TYPE_ADDON)
        self.assertEqual(r["Location"], f"/akun/pesanan/{order.code}/?ok=dibuat")
        self.assertEqual((order.amount, order.quantity, order.store), (15000, 1, self.store))
        self.assertEqual(order.title, "Kasir · Tambah 1 toko")
        self.assertEqual(self.client.get(url)["Location"], f"/akun/pesanan/{order.code}/")  # satu pesanan terbuka saja
        self.admin.post(reverse("panel:pesanan-update", args=[order.pk]), {"status": "aktif", "admin_note": "", **ORDER_FORMSET_EMPTY})
        self.store.refresh_from_db()
        self.assertEqual((self.store.subscription.extra_stores, self.store.subscription.store_limit), (1, 3))
        self.assertContains(self.client.get("/akun/toko/"), "<b>1</b> / 3")
        self.assertContains(self.client.get("/akun/toko/"), "Paket Tunas 2 + tambahan 1")

    def test_renewal_includes_extra_stores(self):
        from apps.content.models import Package

        self.store.subscription.extra_stores = 2
        self.store.subscription.save()
        page = self.client.get(reverse("toko:perpanjang", args=["warungbudi"]))
        self.assertContains(page, "Rp55.000")  # 25.000 + 2 x 15.000
        self.client.post(reverse("toko:perpanjang", args=["warungbudi"]), {"package": Package.objects.get(code="tunas").pk, "new_subdomain": ""})
        order = Order.objects.get(order_type=Order.TYPE_RENEWAL)
        self.assertEqual(order.amount, 55000)
        self.assertIn("2 toko tambahan", order.price_text)

    def test_chat_page_fits_screen(self):
        conv = Conversation.objects.create(member=self.member)
        self.assertContains(self.client.get(f"/akun/chat/{conv.pk}/"), "akun-chat")


class ConsultationChatTests(SeededTestCase):
    """Pesanan jasa (Paket Rimba): tombol ke ruang obrolan konsultasi yang sama di akun & panel."""

    def setUp(self):
        super().setUp()
        self.member = make_member()
        login_member(self.client, self.member)

    def test_rimba_order_opens_linked_chat(self):
        self.client.post("/akun/pesan/rimba/")
        order = Order.objects.get()
        self.assertEqual(order.status, Order.STATUS_CONSULT)
        conv = Conversation.objects.get(order=order)
        self.assertEqual((conv.member, conv.topic), (self.member, "konsultasi"))
        self.assertIn(order.code, conv.messages.get().text)  # pesan pembuka dari HANS Project
        page = self.client.get(f"/akun/pesanan/{order.code}/")
        self.assertContains(page, "Buka obrolan konsultasi")
        self.assertContains(page, f'href="/akun/chat/{conv.pk}/"')
        self.assertNotContains(page, "Kami akan menghubungi Anda")
        chat_page = self.client.get(f"/akun/chat/{conv.pk}/")
        self.assertContains(chat_page, f"Pesanan {order.code}")
        admin = Client(HTTP_HOST="testserver")
        login_fully(admin, make_admin(with_2fa=True))
        self.assertContains(admin.get(reverse("panel:chat-list") + "?filter=semua"), order.code)
        self.assertContains(admin.get(reverse("panel:pesanan-update", args=[order.pk])), "Buka obrolan konsultasi")

    def test_old_order_without_chat_gets_one_from_button(self):
        from apps.content.models import Package

        pkg = Package.objects.get(code="rimba")
        order = Order.objects.create(member=self.member, package=pkg, package_name="Rimba", package_category="jasa",
                                     price_text=pkg.price_text, status=Order.STATUS_CONSULT)
        page = self.client.get(f"/akun/pesanan/{order.code}/")
        self.assertContains(page, 'name="aksi" value="chat"')
        r = self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "chat"})
        conv = Conversation.objects.get(order=order)
        self.assertEqual(r["Location"], f"/akun/chat/{conv.pk}/")
        self.client.post(f"/akun/pesanan/{order.code}/", {"aksi": "chat"})
        self.assertEqual(Conversation.objects.filter(order=order).count(), 1)  # tidak dobel

    def test_consultation_chat_not_counted_in_open_limit(self):
        self.client.post("/akun/pesan/rimba/")
        for text in ["Satu", "Dua", "Tiga"]:
            r = self.client.post("/akun/chat/baru/", {"topic": "umum", "text": text})
            self.assertEqual(r.status_code, 302)
        self.assertEqual(Conversation.objects.filter(member=self.member, status="terbuka").count(), 4)

    def test_store_menu_has_scroll_hint_and_grid(self):
        store = make_store(self.member)
        page = self.client.get(reverse("toko:ringkasan", args=[store.subdomain]))
        self.assertContains(page, 'class="toko-tabs scroll-hint-x"')


class OrderItemsAndVerifyTests(SeededTestCase):
    """Rincian harga manual (Paket Rimba), QR keaslian ke halaman publik, dan tombol cetak."""

    def setUp(self):
        super().setUp()
        self.member = make_member(name="Sari Wulandari")
        login_member(self.client, self.member)
        self.client.post("/akun/pesan/rimba/")
        self.order = Order.objects.get()
        self.admin = Client(HTTP_HOST="testserver")
        login_fully(self.admin, make_admin(with_2fa=True))

    def save_items(self, rows, status="bayar"):
        data = {"status": status, "admin_note": "", "rincian-TOTAL_FORMS": str(len(rows)), "rincian-INITIAL_FORMS": "0"}
        for i, (name, amount, period) in enumerate(rows):
            data.update({f"rincian-{i}-name": name, f"rincian-{i}-amount": str(amount), f"rincian-{i}-period": period,
                         f"rincian-{i}-note": ""})
        return self.admin.post(reverse("panel:pesanan-update", args=[self.order.pk]), data)

    def test_admin_types_price_lines(self):
        self.assertContains(self.admin.get(reverse("panel:pesanan-update", args=[self.order.pk])), "Rincian harga")
        r = self.save_items([("Pembuatan website", 349000, ""), ("Domain .com", 250000, "1 tahun"), ("Database", 50000, "3 bulan"), ("Konsultasi", 2000, "14 hari")])
        self.assertEqual(r.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.amount, 651000)
        page = self.client.get(f"/akun/pesanan/{self.order.code}/")
        for text in ["Domain .com", "Rp250.000", " / 1 tahun", " / 3 bulan", " / 14 hari", "Total Semua", "Rp651.000"]:
            self.assertContains(page, text)
        self.assertNotContains(page, "Tagihan pertama")
        self.assertEqual([i.name for i in self.order.items.all()], ["Pembuatan website", "Domain .com", "Database", "Konsultasi"])
        self.assertNotContains(page, "mulai Rp349.000 biaya pembuatan")
        self.assertContains(page, "Bayar sebesar <b>Rp651.000</b>")  # status Menunggu pembayaran

    def test_proof_hidden_until_payment_checked(self):
        for status in ("bayar", "dicek", "konsultasi"):
            Order.objects.filter(pk=self.order.pk).update(status=status)
            page = self.client.get(f"/akun/pesanan/{self.order.code}/")
            self.assertNotContains(page, f"/cek/{self.order.verify_token}/")
            self.assertNotContains(page, "data-print")
            self.assertContains(page, "bisa dicetak setelah pembayaran Anda kami cek")
            self.assertEqual(Client(HTTP_HOST="testserver").get(f"/cek/{self.order.verify_token}/").status_code, 404)
        Order.objects.filter(pk=self.order.pk).update(status="batal")
        public = Client(HTTP_HOST="testserver").get(f"/cek/{self.order.verify_token}/")
        self.assertContains(public, "tidak berlaku lagi")
        self.assertNotContains(public, "data-print")

    def test_qr_links_to_public_verify_page(self):
        for status in ("diproses", "selesai"):
            Order.objects.filter(pk=self.order.pk).update(status=status)
            self.assertContains(self.client.get(f"/akun/pesanan/{self.order.code}/"), f"/cek/{self.order.verify_token}/")
        Order.objects.filter(pk=self.order.pk).update(status="aktif")
        page = self.client.get(f"/akun/pesanan/{self.order.code}/")
        self.assertContains(page, "<svg")
        self.assertContains(page, "viewBox=")  # QR harus bisa mengecil mengikuti kotaknya, bukan terpotong
        self.assertContains(page, f"/cek/{self.order.verify_token}/")
        self.assertContains(page, "data-print")
        public = Client(HTTP_HOST="testserver").get(f"/cek/{self.order.verify_token}/")
        self.assertContains(public, "Pesanan terdaftar di HANS Project")
        self.assertContains(public, self.order.code)
        self.assertContains(public, "Sa** Wu******")
        self.assertNotContains(public, "Sari Wulandari")
        self.assertNotContains(public, self.member.email)
        self.assertIn("noindex", public["X-Robots-Tag"])
        self.assertEqual(Client(HTTP_HOST="testserver").get(f"/cek/{self.order.code}/").status_code, 404)  # kode pesanan saja tidak cukup
        self.assertEqual(Client(HTTP_HOST="testserver").get("/cek/kode-asal-asalan-123/").status_code, 404)

    def test_tokens_unique_per_order(self):
        self.client.post("/akun/pesan/tunas/", {"subdomain": "tokounik"})
        tokens = list(Order.objects.values_list("verify_token", flat=True))
        self.assertEqual(len(set(tokens)), len(tokens))
        self.assertTrue(all(len(t) >= 20 for t in tokens))
