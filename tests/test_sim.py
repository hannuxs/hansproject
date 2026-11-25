"""SIM (Sistem Informasi Manajemen), bidang RT/RW/kelurahan/kecamatan: aktivasi paket, isolasi data per wilayah, surat online warga, jaringan RT/RW, OCR, halaman utama."""
from __future__ import annotations

from datetime import date, timedelta
from unittest import mock, skipUnless

from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.content.models import Package
from apps.members.models import Order
from apps.sim import ocr, ocr_foto, services
from apps.sim.models import (
    LEVEL_RT,
    LEVEL_RW,
    DokumenScan,
    KartuKeluarga,
    Penduduk,
    Pengumuman,
    Surat,
    Wilayah,
    mask_name,
    mask_nik,
)

from .helpers import SeededTestCase, login_fully, make_admin
from .test_members import PrivateMediaMixin, login_member, make_member, png_upload

NIK = "3201010101900001"


def make_wilayah(owner, level=LEVEL_RT, nomor="005", *, days=20, **kwargs) -> Wilayah:
    w = Wilayah.objects.create(
        owner=owner, level=level, nomor=nomor, kelurahan=kwargs.pop("kelurahan", "Sukamaju"),
        kecamatan="Cibinong", kota="Kabupaten Bogor", provinsi="Jawa Barat", ketua_nama="BUDI KETUA",
        package_name="SIM RT", active_until=timezone.localdate() + timedelta(days=days), **kwargs,
    )
    services.seed_jenis_surat(w)
    return w


def make_warga(w, nik=NIK, nama="SITI AMINAH", born=date(1990, 1, 1)) -> Penduduk:
    kk = KartuKeluarga.objects.create(wilayah=w, no_kk="3201010101900099", kepala_nama="AHMAD", alamat="JL. MELATI 1", rt="005", rw="003")
    return Penduduk.objects.create(wilayah=w, kk=kk, nik=nik, nama=nama, jenis_kelamin="P", tanggal_lahir=born, hubungan="Istri")


MEMBER_FIELDS = ("nama", "hubungan", "nik", "jenis_kelamin", "tempat_lahir", "tanggal_lahir", "agama", "pendidikan", "pekerjaan",
                 "golongan_darah", "status_perkawinan", "tanggal_perkawinan", "kewarganegaraan", "no_paspor", "no_kitap",
                 "nama_ayah", "nama_ibu")


def kk_post(rows, *, initial=0, extra_blank=1, **fields):
    """POST formulir KK + anggota (formset berawalan 'anggota')."""
    data = {"status": "aktif", **fields}
    rows = list(rows) + [{} for _ in range(extra_blank)]
    data.update({"anggota-TOTAL_FORMS": str(len(rows)), "anggota-INITIAL_FORMS": str(initial),
                 "anggota-MIN_NUM_FORMS": "0", "anggota-MAX_NUM_FORMS": "15"})
    for i, row in enumerate(rows):
        for key in MEMBER_FIELDS:
            data[f"anggota-{i}-{key}"] = row.get(key, "WNI" if key == "kewarganegaraan" and row else "")
        for key in ("id", "DELETE"):
            if row.get(key):
                data[f"anggota-{i}-{key}"] = row[key]
    return data


def request_data(**extra):
    data = {
        "nama": "Siti Aminah", "nik": NIK, "jenis_kelamin": "P", "tempat_lahir": "Bogor", "tanggal_lahir": "1990-01-01",
        "agama": "Islam", "status_perkawinan": "Kawin", "pekerjaan": "Pedagang", "kewarganegaraan": "WNI",
        "alamat": "Jl. Melati 1", "keperluan": "Melamar kerja", "setuju": "on", "website": "",
    }
    data.update(extra)
    return data


# ---------------------------------------------------------------------------
# OCR & aturan surat (tanpa database)
# ---------------------------------------------------------------------------
KTP_TEXT = """PROVINSI JAWA BARAT
KABUPATEN BOGOR
NIK : 32O1010101900001
Nama : SITI AMINAH
Tempat/Tgl Lahir : BOGOR, 01-01-1990
Jenis Kelamin : PEREMPUAN Gol. Darah : O
Alamat : JL. MELATI NO. 1
RT/RW : 005/003
Kel/Desa : SUKAMAJU
Kecamatan : CIBINONG
Agama : ISLAM
Status Perkawinan : KAWIN
Pekerjaan : PEDAGANG
Kewarganegaraan : WNI"""

KK_TEXT = """KARTU KELUARGA
No. 3201010101900099
Nama Kepala Keluarga : AHMAD SUBARJO
Alamat : JL. MELATI NO. 1
RT/RW : 005/003
Desa/Kelurahan : SUKAMAJU
Kecamatan : CIBINONG
Kabupaten/Kota : BOGOR
Kode Pos : 16911
Provinsi : JAWA BARAT
1 AHMAD SUBARJO 3201010101850001 LAKI-LAKI BOGOR 12-05-1985 ISLAM SLTA/SEDERAJAT WIRASWASTA
2 SITI AMINAH 3201010101900001 PEREMPUAN BOGOR 01-01-1990 ISLAM SLTA/SEDERAJAT MENGURUS RUMAH TANGGA
1 KAWIN KEPALA KELUARGA WNI
2 KAWIN ISTRI WNI"""


class OcrParserTests(SimpleTestCase):
    def test_ktp(self):
        data = ocr.parse_ktp(KTP_TEXT)
        self.assertEqual(data["nik"], NIK)  # huruf O dibaca sebagai 0
        self.assertEqual(data["nama"], "SITI AMINAH")
        self.assertEqual(data["tanggal_lahir"], "1990-01-01")
        self.assertEqual(data["tempat_lahir"], "BOGOR")
        self.assertEqual(data["jenis_kelamin"], "P")
        self.assertEqual((data["rt"], data["rw"]), ("005", "003"))
        self.assertEqual(data["agama"], "Islam")
        self.assertEqual(data["status_perkawinan"], "Kawin")

    def test_kk(self):
        data = ocr.parse_kk(KK_TEXT)
        self.assertEqual(data["no_kk"], "3201010101900099")
        self.assertEqual(data["kepala_nama"], "AHMAD SUBARJO")
        self.assertEqual(data["kode_pos"], "16911")
        self.assertEqual(len(data["anggota"]), 2)
        head, wife = data["anggota"]
        self.assertEqual((head["nik"], head["nama"], head["jenis_kelamin"], head["tanggal_lahir"]), ("3201010101850001", "AHMAD SUBARJO", "L", "1985-05-12"))
        self.assertEqual(head["hubungan"], "Kepala Keluarga")
        self.assertEqual(wife["hubungan"], "Istri")
        self.assertEqual(wife["pendidikan"], "SLTA/SEDERAJAT")

    def test_bad_dates_ignored(self):
        self.assertEqual(ocr.parse_date("31-02-1990"), "")
        self.assertEqual(ocr.parse_date("01-01-1800"), "")

    @override_settings(TESSERACT_CMD="")
    def test_missing_engine_is_reported_not_raised(self):
        with mock.patch.object(ocr, "tesseract_cmd", return_value=None), mock.patch.object(ocr_foto, "available", return_value=False):
            result = ocr.read_text(mock.Mock(), kind="kk")
        self.assertFalse(result.ok)
        self.assertFalse(result.available)

    def test_fields_text(self):
        fields, errors = services.parse_fields_text("nama_usaha | Nama usaha | wajib | teks\nmulai | Sejak | opsional | tanggal")
        self.assertEqual(errors, [])
        self.assertEqual(fields[1], {"key": "mulai", "label": "Sejak", "type": "tanggal", "required": False})
        _, errors = services.parse_fields_text("Nama Usaha | x\nnama | dobel\nok_1 | a\nok_1 | b\nx2 | a | wajib | video")
        self.assertEqual(len(errors), 4)

    def test_blocks_and_masks(self):
        parts = services.blocks("Pembuka surat.\n\nNama : Budi\nNIK : 123\n\nPenutup.")
        self.assertEqual([b.kind for b in parts], ["p", "table", "p"])
        self.assertEqual(parts[1].rows[0], ("Nama", "Budi"))
        self.assertEqual(mask_nik(NIK), "3201••••••••0001")
        self.assertEqual(mask_name("Siti Aminah"), "S*** A*****")


# ---------------------------------------------------------------------------
# Pesan paket SIM -> aktif -> perpanjang
# ---------------------------------------------------------------------------
class SimActivationTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        Package.objects.filter(code="sim-tunas").update(price=20000)
        self.member = make_member()
        login_member(self.client, self.member)
        self.admin = Client(HTTP_HOST="testserver")
        login_fully(self.admin, make_admin(with_2fa=True))

    def activate(self, order):
        data = {"status": "aktif", "admin_note": "", "rincian-TOTAL_FORMS": "0", "rincian-INITIAL_FORMS": "0"}
        return self.admin.post(reverse("panel:pesanan-update", args=[order.pk]), data)

    def test_not_orderable_until_owner_sets_price(self):
        Package.objects.filter(code="sim-tunas").update(price=0)  # harga belum ditentukan
        self.assertRedirects(self.client.get("/akun/pesan/sim-tunas/"), "/akun/pesan/?layanan=sim", fetch_redirect_response=False)
        self.assertFalse(Order.objects.exists())
        Package.objects.filter(code="sim-tunas").update(is_active=False)
        self.assertEqual(self.client.get("/akun/pesan/sim-tunas/").status_code, 404)

    def test_order_validates_and_activation_creates_wilayah(self):
        r = self.client.post("/akun/pesan/sim-tunas/", {"tingkat": "rt", "kota": "Bogor", "provinsi": "Jawa Barat"})
        self.assertEqual(r.status_code, 400)  # nomor & kelurahan wajib untuk RT
        r = self.client.post("/akun/pesan/sim-tunas/", {
            "tingkat": "rt", "nomor": "5", "rw": "3", "kelurahan": "Sukamaju", "kecamatan": "Cibinong",
            "kota": "Kabupaten Bogor", "provinsi": "Jawa Barat",
        })
        self.assertEqual(r.status_code, 302)
        order = Order.objects.latest("created_at")
        self.assertEqual((order.status, order.details["nomor"], order.sim_label), ("bayar", "005", "RT 005 / RW 003, Kel. Sukamaju"))
        self.assertFalse(order.needs_consultation)
        self.assertEqual(self.activate(order).status_code, 302)
        order.refresh_from_db()
        w = order.wilayah
        self.assertEqual((w.owner, w.level, w.nomor, w.rw), (self.member, "rt", "005", "003"))
        self.assertTrue(w.jenis_surat.filter(kode="domisili").exists())
        self.assertFalse(w.jenis_surat.filter(kode="ahli-waris").exists())  # hanya kelurahan/kecamatan
        self.assertContains(self.client.get(reverse("sim:ringkasan", args=[w.kode])), "RT 005 / RW 003")

        # Perpanjang: +1 bulan dari tanggal habis.
        before = w.active_until
        r = self.client.post(reverse("sim:perpanjang", args=[w.kode]), {"package": Package.objects.get(code="sim-tunas").pk})
        self.assertEqual(r.status_code, 302)
        renewal = Order.objects.filter(order_type=Order.TYPE_RENEWAL).latest("created_at")
        self.assertEqual(renewal.wilayah, w)
        self.activate(renewal)
        w.refresh_from_db()
        self.assertGreater(w.active_until, before)

    def test_panel_shows_sim_order_as_sim_not_kasir(self):
        self.client.post("/akun/pesan/sim-tunas/", {
            "tingkat": "rt", "nomor": "5", "rw": "3", "kelurahan": "Sukamaju", "kecamatan": "Cibinong",
            "kota": "Kabupaten Bogor", "provinsi": "Jawa Barat",
        })
        order = Order.objects.get()
        self.assertEqual((order.package_category, order.title), ("sim", "SIM · Paket Tunas"))
        self.assertContains(self.admin.get(reverse("panel:pesanan-list")), "SIM · Paket Tunas")
        detail = self.admin.get(reverse("panel:pesanan-update", args=[order.pk]))
        self.assertContains(detail, "Sistem Informasi Manajemen (SIM)")
        self.assertContains(detail, "Instansi diminta")
        self.assertNotContains(detail, "Alamat toko")
        member = self.admin.get(reverse("panel:pelanggan-update", args=[self.member.pk]))
        self.assertContains(member, "SIM · Paket Tunas")

    def test_panel_can_edit_sim_tumbuh_price(self):
        """SIM Tumbuh 'berisi semua isi SIM Tunas': form paket di panel harus menerima paket SIM sebagai induknya."""
        from django.forms.models import model_to_dict

        from apps.panel.forms import PackageForm

        pkg = Package.objects.get(code="sim-tumbuh")
        data = {k: ("" if v is None else v) for k, v in model_to_dict(pkg, fields=PackageForm._meta.fields).items()}
        data["price"] = 150000
        form = PackageForm(data, instance=pkg)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["includes_from"].code, "sim-tunas")
        data["includes_from"] = Package.objects.get(code="tunas").pk  # paket kasir: solusi lain
        self.assertIn("includes_from", PackageForm(data, instance=pkg).errors)
        self.assertEqual(str(pkg), "SIM · Paket Tumbuh")


# ---------------------------------------------------------------------------
# Isolasi data: pengurus lain tidak bisa membuka wilayah/warga orang lain
# ---------------------------------------------------------------------------
class IsolationTests(PrivateMediaMixin, SeededTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_member()
        self.w = make_wilayah(self.owner)
        self.person = make_warga(self.w)
        self.other = make_member(sub="sub-2", email="lain@gmail.com")
        self.w2 = make_wilayah(self.other, nomor="006")

    def test_other_member_gets_404(self):
        login_member(self.client, self.other)
        for name, args in [("sim:ringkasan", []), ("sim:warga", []), ("sim:kk", [self.person.kk_id]), ("sim:warga-unduh", [])]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=[self.w.kode, *args])).status_code, 404)
        # Kode wilayah sendiri + nomor KK wilayah lain: tetap 404.
        self.assertEqual(self.client.get(reverse("sim:kk", args=[self.w2.kode, self.person.kk_id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("sim:kk-hapus", args=[self.w2.kode, self.person.kk_id])).status_code, 404)
        self.assertTrue(KartuKeluarga.objects.filter(pk=self.person.kk_id).exists())

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("sim:ringkasan", args=[self.w.kode]))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/akun/masuk/", r["Location"])

    def test_csv_export_is_formula_safe(self):
        Penduduk.objects.filter(pk=self.person.pk).update(pekerjaan="=HYPERLINK(1)")
        login_member(self.client, self.owner)
        r = self.client.get(reverse("sim:warga-unduh", args=[self.w.kode]))
        body = r.content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK(1)", body)
        self.assertEqual(r["Cache-Control"], "no-store, max-age=0")

    def test_search(self):
        login_member(self.client, self.owner)
        self.assertContains(self.client.get(reverse("sim:ringkasan", args=[self.w.kode]), {"q": "siti"}), "SITI AMINAH")
        self.assertContains(self.client.get(reverse("sim:ringkasan", args=[self.w.kode]), {"q": "3201"}), "SITI AMINAH")


# ---------------------------------------------------------------------------
# Warga mengajukan surat (tanpa login) -> pengurus menerbitkan -> lacak & cek keaslian
# ---------------------------------------------------------------------------
class PublicLetterTests(PrivateMediaMixin, SeededTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_member()
        self.w = make_wilayah(self.owner)
        self.person = make_warga(self.w)

    def submit(self, jenis="domisili", **extra):
        data = request_data(x_alamat_domisili="Jl. Melati 1", x_sejak="Januari 2020", **extra)
        return self.client.post(reverse("warga:ajukan", args=[self.w.kode, jenis]), data)

    def test_full_flow(self):
        page = self.client.get(self.w.public_path)
        self.assertContains(page, "Surat Keterangan Domisili")
        self.assertEqual(page["X-Robots-Tag"], "noindex, nofollow")
        r = self.submit()
        self.assertEqual(r.status_code, 302)
        s = Surat.objects.get()
        self.assertEqual((s.nama, s.nik, s.penduduk, s.status), ("SITI AMINAH", NIK, self.person, "diajukan"))
        lacak = self.client.get(r["Location"])
        self.assertContains(lacak, s.lacak_token)
        self.assertContains(lacak, "3201••••••••0001")
        self.assertNotContains(lacak, NIK)

        login_member(self.client, self.owner)
        r = self.client.post(reverse("sim:surat-detail", args=[self.w.kode, s.pk]), {**request_data(), "x_alamat_domisili": "Jl. Melati 1", "x_sejak": "2020", "aksi": "terbit"})
        self.assertEqual(r.status_code, 302)
        s.refresh_from_db()
        year = timezone.localdate().year
        self.assertTrue(s.nomor.startswith("001/SKD/RT005/"))
        self.assertTrue(s.nomor.endswith(str(year)))
        self.assertIn("Jl. Melati 1", s.isi)
        printed = self.client.get(reverse("sim:surat-cetak", args=[self.w.kode, s.pk]))
        self.assertContains(printed, "SURAT KETERANGAN DOMISILI")
        self.assertContains(printed, "RUKUN TETANGGA 005")
        self.assertContains(printed, "qr-svg")

        # Warga: status terbit, tapi cetak sendiri hanya bila diizinkan pengurus.
        anon = Client(HTTP_HOST="testserver")
        self.assertContains(anon.get(s.lacak_path), "Surat sudah terbit")
        self.assertEqual(anon.get(reverse("warga:lacak-cetak", args=[s.lacak_token])).status_code, 404)
        Wilayah.objects.filter(pk=self.w.pk).update(warga_boleh_cetak=True)
        self.assertContains(anon.get(reverse("warga:lacak-cetak", args=[s.lacak_token])), s.nomor)
        cek = anon.get(s.verify_path)
        self.assertContains(cek, s.nomor)
        self.assertContains(cek, "S*** A*****")
        self.assertNotContains(cek, NIK)

        # Nomor berikutnya naik.
        s2 = services.create_request(self.w, s.jenis, {"nama": "B", "nik": ""}, source=Surat.SOURCE_DIRECT)
        self.assertTrue(services.issue(s2).nomor.startswith("002/"))

    def test_validation_honeypot_and_unknown_nik(self):
        self.assertEqual(self.submit(nik="123").status_code, 400)
        self.assertEqual(self.submit(setuju="").status_code, 400)
        self.assertEqual(self.submit(website="http://spam").status_code, 400)
        self.assertEqual(Surat.objects.count(), 0)
        self.submit(nik="3201010101900002")
        self.assertIsNone(Surat.objects.get().penduduk)  # tidak cocok: pengurus diberi tanda

    def test_rate_limited(self):
        for _ in range(5):
            self.submit()
        self.assertEqual(self.submit().status_code, 429)

    def test_unknown_tokens_and_offline_letters(self):
        self.assertEqual(self.client.get(reverse("warga:lacak", args=["x" * 24])).status_code, 404)
        self.assertEqual(self.client.get("/surat/cek/bukan!token!valid/").status_code, 404)
        jenis = self.w.jenis_surat.get(kode="domisili")
        jenis.online = False
        jenis.save()
        self.assertEqual(self.submit().status_code, 404)

    def test_locked_wilayah_closes_public_requests_and_edits(self):
        Wilayah.objects.filter(pk=self.w.pk).update(active_until=timezone.localdate() - timedelta(days=10))
        self.assertContains(self.client.get(self.w.public_path), "sedang tidak aktif")
        self.assertEqual(self.submit().status_code, 404)
        login_member(self.client, self.owner)
        r = self.client.post(reverse("sim:kk-baru", args=[self.w.kode]), {"kepala_nama": "X", "status": "aktif"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("ok=terkunci", r["Location"])


# ---------------------------------------------------------------------------
# Jaringan RT -> RW: bergabung dengan kode, surat "diketahui", tanpa akses data warga
# ---------------------------------------------------------------------------
class NetworkTests(PrivateMediaMixin, SeededTestCase):
    def setUp(self):
        super().setUp()
        self.rt_owner = make_member()
        self.rw_owner = make_member(sub="sub-rw", email="rw@gmail.com")
        self.rt = make_wilayah(self.rt_owner, nomor="005", rw="")
        self.rw = make_wilayah(self.rw_owner, level=LEVEL_RW, nomor="003")
        self.person = make_warga(self.rt)

    def test_join_ack_and_isolation(self):
        login_member(self.client, self.rt_owner)
        bad = self.client.post(reverse("sim:jaringan", args=[self.rt.kode]), {"aksi": "gabung", "kode": "SALAHKODE1"})
        self.assertEqual(bad.status_code, 400)
        self.client.post(reverse("sim:jaringan", args=[self.rt.kode]), {"aksi": "gabung", "kode": self.rw.join_code.lower()})
        self.rt.refresh_from_db()
        self.assertEqual(self.rt.join_request, self.rw)

        rw_client = Client(HTTP_HOST="testserver")
        login_member(rw_client, self.rw_owner)
        rw_client.post(reverse("sim:jaringan", args=[self.rw.kode]), {"aksi": "terima", "wilayah": self.rt.pk})
        self.rt.refresh_from_db()
        self.assertEqual((self.rt.parent, self.rt.rw), (self.rw, "003"))

        jenis = self.rt.jenis_surat.get(kode="pengantar")
        self.assertTrue(jenis.butuh_mengetahui)
        s = services.issue(services.create_request(self.rt, jenis, {"nama": "SITI", "nik": NIK, "keperluan": "SKCK"}, source=Surat.SOURCE_DIRECT))
        self.assertEqual((s.mengetahui, s.mengetahui_wilayah), (Surat.ACK_WAITING, self.rw))
        self.assertContains(rw_client.get(reverse("sim:jaringan", args=[self.rw.kode])), "Surat Pengantar")
        rw_client.post(reverse("sim:ketahui", args=[self.rw.kode, s.pk]), {"aksi": "ketahui", "catatan": ""})
        s.refresh_from_db()
        self.assertEqual((s.mengetahui, s.mengetahui_nama), (Surat.ACK_DONE, "BUDI KETUA"))
        printed = self.client.get(reverse("sim:surat-cetak", args=[self.rt.kode, s.pk]))
        self.assertContains(printed, "Mengetahui")

        # RW hanya melihat rekap; data warga RT tetap tertutup.
        overview = rw_client.get(reverse("sim:ringkasan", args=[self.rw.kode]))
        self.assertContains(overview, "Rekap wilayah di bawah Anda")
        self.assertNotContains(overview, "SITI AMINAH")
        self.assertEqual(rw_client.get(reverse("sim:kk", args=[self.rw.kode, self.person.kk_id])).status_code, 404)
        self.assertEqual(rw_client.get(reverse("sim:ringkasan", args=[self.rt.kode])).status_code, 404)

    def test_level_rules(self):
        other_rt = make_wilayah(make_member(sub="sub-3", email="c@gmail.com"), nomor="007")
        with self.assertRaises(services.NetworkError):
            services.request_join(self.rt, other_rt.join_code)  # RT tidak bisa bergabung ke RT

    def test_parent_announcement_shown_on_child_page(self):
        self.rt.parent = self.rw
        self.rt.save()
        Pengumuman.objects.create(wilayah=self.rw, judul="Kerja bakti RW", isi="Minggu pagi", teruskan=True)
        Pengumuman.objects.create(wilayah=self.rw, judul="Rapat pengurus RW", isi="Internal", teruskan=False)
        page = self.client.get(self.rt.public_path)
        self.assertContains(page, "Kerja bakti RW")
        self.assertNotContains(page, "Rapat pengurus RW")


# ---------------------------------------------------------------------------
# Scan KK -> data KK (OCR belum terpasang di server tes)
# ---------------------------------------------------------------------------
class ScanTests(PrivateMediaMixin, SeededTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_member()
        self.w = make_wilayah(self.owner)
        login_member(self.client, self.owner)

    @mock.patch.object(ocr_foto, "available", return_value=False)
    @mock.patch.object(ocr, "tesseract_cmd", return_value=None)
    def test_upload_then_create_kk(self, _cmd, _foto):
        r = self.client.post(reverse("sim:scan", args=[self.w.kode]), {"jenis": "kk", "judul": "KK Ahmad", "gambar": png_upload("kk.png")})
        self.assertEqual(r.status_code, 302)
        doc = DokumenScan.objects.get()
        self.assertEqual(doc.ocr_status, DokumenScan.OCR_UNAVAILABLE)
        self.assertTrue(doc.gambar.name.startswith("sim/scan/"))
        image = self.client.get(reverse("sim:scan-gambar", args=[self.w.kode, doc.pk]))
        self.assertEqual(image["Cache-Control"], "no-store, max-age=0")
        url = reverse("sim:scan-detail", args=[self.w.kode, doc.pk])
        page = self.client.get(url)
        self.assertNotContains(page, "Teks hasil baca")  # teks mentah OCR tidak ditampilkan lagi
        self.assertNotContains(page, 'name="kepala_nama"')  # nama kepala keluarga tidak diketik
        rows = [
            {"nama": "Ahmad", "nik": "3201010101850001", "jenis_kelamin": "L", "tanggal_lahir": "1985-05-12", "hubungan": "Anak"},
            {"nama": "Siti", "nik": "123"},
        ]
        r = self.client.post(url, kk_post(rows, aksi="simpan-kk", no_kk="3201010101900099", alamat="Jl. Melati"))
        self.assertContains(r, "NIK harus 16 angka", status_code=400)
        rows[1]["nik"] = ""
        r = self.client.post(url, kk_post(rows, aksi="simpan-kk", no_kk="3201010101900099", alamat="Jl. Melati"))
        self.assertContains(r, "Kepala Keluarga", status_code=400)  # belum ada kepala keluarga
        self.assertFalse(KartuKeluarga.objects.exists())
        rows[0]["hubungan"] = "Kepala Keluarga"
        r = self.client.post(url, kk_post(rows, aksi="simpan-kk", no_kk="3201010101900099", alamat="Jl. Melati"))
        self.assertEqual(r.status_code, 302)
        kk = KartuKeluarga.objects.get()
        self.assertEqual((kk.no_kk, kk.kepala_nama, kk.alamat), ("3201010101900099", "AHMAD", "JL. MELATI"))
        people = list(kk.anggota.order_by("urutan"))
        self.assertEqual([(p.nama, p.nik, p.urutan) for p in people], [("AHMAD", "3201010101850001", 1), ("SITI", "", 2)])
        doc.refresh_from_db()
        self.assertEqual(doc.kk, kk)
        self.assertContains(self.client.get(url), "Sudah disimpan sebagai")

    def test_scan_result_fills_kk_form(self):
        hasil = {
            "no_kk": "6501050409200002", "alamat": "JL. MAWAR NO 4", "rt": "006", "rw": "003", "kode_pos": "77212",
            "kelurahan": "TANJUNG SELOR HILIR", "kecamatan": "TANJUNG SELOR", "kota": "BULUNGAN", "provinsi": "KALIMANTAN UTARA",
            "tanggal_dikeluarkan": "2025-06-25", "kepala_nama": "RINA CONTOH",
            "anggota": [
                {"nama": "RINA CONTOH", "nik": "6404074205840002", "jenis_kelamin": "P", "tempat_lahir": "LONG LASAN",
                 "tanggal_lahir": "1984-05-02", "agama": "Islam", "pendidikan": "DIPLOMA IV/STRATA I", "pekerjaan": "KARYAWAN HONORER",
                 "golongan_darah": "O", "status_perkawinan": "Cerai Tercatat", "tanggal_perkawinan": "2025-05-07",
                 "hubungan": "Kepala Keluarga", "kewarganegaraan": "WNI", "nama_ayah": "AHEL", "nama_ibu": "PAULINA"},
                {"nama": "BAYU CONTOH", "nik": "6404072301050001", "jenis_kelamin": "L", "tempat_lahir": "KENDARI",
                 "tanggal_lahir": "2005-01-23", "agama": "Islam", "pendidikan": "SLTA/SEDERAJAT", "pekerjaan": "BELUM/TIDAK BEKERJA",
                 "golongan_darah": "TIDAK TAHU", "status_perkawinan": "Belum Kawin", "hubungan": "Anak", "kewarganegaraan": "WNI",
                 "nama_ayah": "NURDIN", "nama_ibu": "RINA CONTOH"},
            ],
        }
        result = ocr.OcrResult(True, text="(hasil)", data=hasil)
        with mock.patch.object(ocr, "read_text", return_value=result):
            self.client.post(reverse("sim:scan", args=[self.w.kode]), {"jenis": "kk", "gambar": png_upload("kk.png")})
        doc = DokumenScan.objects.get()
        url = reverse("sim:scan-detail", args=[self.w.kode, doc.pk])
        page = self.client.get(url)
        for text in ('value="6501050409200002"', 'value="RINA CONTOH"', 'value="BAYU CONTOH"', 'value="DIPLOMA IV/STRATA I"',
                     'value="2025-06-25"', "terisi otomatis", "2 anggota"):
            self.assertContains(page, text)
        # Pengurus langsung menekan Simpan tanpa mengubah apa pun: semua baris hasil scan ikut tersimpan.
        rows = [dict(m) for m in hasil["anggota"]]
        keys = {k: hasil[k] for k in ("no_kk", "alamat", "rt", "rw", "kode_pos", "kelurahan", "kecamatan", "kota", "provinsi",
                                      "tanggal_dikeluarkan")}
        r = self.client.post(url, kk_post(rows, aksi="simpan-kk", **keys))
        self.assertEqual(r.status_code, 302)
        kk = KartuKeluarga.objects.get()
        self.assertEqual((kk.kepala_nama, kk.kota, str(kk.tanggal_dikeluarkan)), ("RINA CONTOH", "BULUNGAN", "2025-06-25"))
        head = kk.anggota.get(hubungan="Kepala Keluarga")
        self.assertEqual((head.status_perkawinan, str(head.tanggal_perkawinan), head.golongan_darah), ("Cerai Tercatat", "2025-05-07", "O"))
        self.assertEqual(kk.anggota.get(nama="BAYU CONTOH").golongan_darah, "TIDAK TAHU")

    def test_ktp_scan_adds_member_to_chosen_kk(self):
        kk = KartuKeluarga.objects.create(wilayah=self.w, no_kk="3201010101900099", alamat="JL. MELATI 1")
        hasil = {"nik": NIK, "nama": "SITI AMINAH", "jenis_kelamin": "P", "tempat_lahir": "BOGOR", "tanggal_lahir": "1990-01-01",
                 "agama": "Islam", "status_perkawinan": "Kawin", "pekerjaan": "PEDAGANG", "kewarganegaraan": "WNI"}
        with mock.patch.object(ocr, "read_text", return_value=ocr.OcrResult(True, text="x", data=hasil)):
            self.client.post(reverse("sim:scan", args=[self.w.kode]), {"jenis": "ktp", "gambar": png_upload("ktp.png")})
        doc = DokumenScan.objects.get()
        url = reverse("sim:scan-detail", args=[self.w.kode, doc.pk])
        self.assertContains(self.client.get(url), 'value="SITI AMINAH"')
        data = {"aksi": "simpan-ktp", "kk": kk.pk, **hasil, "hubungan": "Kepala Keluarga"}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        person = Penduduk.objects.get(nik=NIK)
        self.assertEqual((person.kk, person.nama, person.status), (kk, "SITI AMINAH", "aktif"))
        kk.refresh_from_db()
        self.assertEqual(kk.kepala_nama, "SITI AMINAH")
        doc.refresh_from_db()
        self.assertEqual((doc.penduduk, doc.kk), (person, kk))

    @mock.patch.object(ocr_foto, "available", return_value=False)
    @mock.patch.object(ocr, "tesseract_cmd", return_value=None)
    def test_monthly_scan_quota_from_package(self, _cmd, _foto):
        pkg = Package.objects.get(code="sim-tunas")
        Package.objects.filter(pk=pkg.pk).update(scan_limit=1)
        Wilayah.objects.filter(pk=self.w.pk).update(package=pkg, package_name=pkg.name)
        url = reverse("sim:scan", args=[self.w.kode])
        self.assertContains(self.client.get(url), "0 / 1")
        self.assertEqual(self.client.post(url, {"jenis": "kk", "gambar": png_upload("a.png")}).status_code, 302)
        r = self.client.post(url, {"jenis": "kk", "gambar": png_upload("b.png")})
        self.assertContains(r, "sudah habis bulan ini", status_code=400)
        self.assertEqual(DokumenScan.objects.count(), 1)
        Package.objects.filter(pk=pkg.pk).update(scan_limit=None)  # tanpa batas
        self.assertEqual(self.client.post(url, {"jenis": "kk", "gambar": png_upload("c.png")}).status_code, 302)

    def test_rejects_non_image_and_other_owner(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        r = self.client.post(reverse("sim:scan", args=[self.w.kode]), {"jenis": "kk", "gambar": SimpleUploadedFile("x.svg", b"<svg/>", "image/svg+xml")})
        self.assertEqual(r.status_code, 400)
        doc = DokumenScan.objects.create(wilayah=self.w, gambar="sim/scan/x.webp")
        other = make_member(sub="sub-9", email="x@gmail.com")
        w2 = make_wilayah(other, nomor="009")
        login_member(self.client, other)
        self.assertEqual(self.client.get(reverse("sim:scan-gambar", args=[w2.kode, doc.pk])).status_code, 404)


# ---------------------------------------------------------------------------
# Halaman utama, panel, pembersihan data
# ---------------------------------------------------------------------------
class PlatformTests(SeededTestCase):
    def test_home_presents_all_solutions(self):
        r = self.client.get("/")
        for text in ['id="solusi"', 'id="harga"', "Aplikasi Kasir", "Sistem Informasi Manajemen", "Website &amp; Aplikasi",
                     "Tiket Online", "Segera hadir", "Segera diumumkan"]:
            self.assertContains(r, text)
        self.assertNotContains(r, "SIM Wilayah")
        self.assertEqual(r.content.decode().count("<h1"), 1)
        self.assertNotContains(r, "/akun/pesan/sim-tunas/")  # harga SIM belum ditentukan -> belum bisa dipesan
        page = self.client.get("/sistem-informasi-manajemen/")
        self.assertEqual(page.content.decode().count("<h1"), 1)
        for text in ["Sistem Informasi Manajemen (SIM)", "Pemerintahan &amp; kemasyarakatan", "Kesehatan", "Pendidikan",
                     "Paket Tunas", "Paket Tumbuh", "Data warga di SIM aman?"]:
            self.assertContains(page, text)

    def test_home_shows_sim_prices_when_active(self):
        from django.core.cache import cache

        Package.objects.filter(code="sim-tunas").update(price=20000)
        cache.clear()
        for path in ("/", "/sistem-informasi-manajemen/"):
            r = self.client.get(path)
            self.assertContains(r, "/akun/pesan/sim-tunas/")
            self.assertContains(r, "Rp20.000")

    def test_robots_hides_warga_pages(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /w/", body)
        self.assertIn("Disallow: /surat/", body)

    def test_panel_lists_wilayah_without_resident_data(self):
        w = make_wilayah(make_member())
        make_warga(w)
        admin = Client(HTTP_HOST="testserver")
        login_fully(admin, make_admin(with_2fa=True))
        page = admin.get(reverse("panel:wilayah-list"))
        self.assertContains(page, "RT 005")
        self.assertNotContains(page, "SITI AMINAH")

    def test_expired_wilayah_deleted_after_30_days(self):
        w = make_wilayah(make_member(), days=-31)
        make_warga(w)
        keep = make_wilayah(make_member(sub="sub-k", email="k@gmail.com"), nomor="008", days=-20)
        self.assertEqual(len(services.delete_expired_wilayah()), 1)
        self.assertFalse(Wilayah.objects.filter(pk=w.pk).exists())
        self.assertFalse(Penduduk.objects.exists())
        self.assertTrue(Wilayah.objects.filter(pk=keep.pk).exists())


class PageSmokeTests(PrivateMediaMixin, SeededTestCase):
    """Setiap halaman pengurus & warga terbuka tanpa error (template, konteks, tautan)."""

    def test_all_pages_render(self):
        owner = make_member()
        w = make_wilayah(owner, level=LEVEL_RW, nomor="003")
        rt = make_wilayah(make_member(sub="sub-rt", email="rt@gmail.com"), nomor="005", join_request=w)
        person = make_warga(w)
        jenis = w.jenis_surat.get(kode="usaha")
        s = services.create_request(w, jenis, {"nama": "SITI", "nik": NIK, "x_nama_usaha": "Warung"}, source=Surat.SOURCE_ONLINE)
        issued = services.issue(services.create_request(w, jenis, {"nama": "BUDI", "nik": ""}, source=Surat.SOURCE_DIRECT))
        doc = DokumenScan.objects.create(wilayah=w, gambar="sim/scan/x.webp", hasil=ocr.parse_kk(KK_TEXT), ocr_status=DokumenScan.OCR_DONE)
        note = Pengumuman.objects.create(wilayah=w, judul="Kerja bakti", isi="Minggu", teruskan=True)
        child_letter = services.create_request(rt, rt.jenis_surat.get(kode="pengantar"), {"nama": "ANI", "nik": ""}, source=Surat.SOURCE_DIRECT)
        rt.parent, rt.join_request = w, None
        rt.save()
        child_letter = services.issue(child_letter)
        login_member(self.client, owner)
        k = w.kode
        pages = [
            reverse("sim:daftar"), reverse("sim:ringkasan", args=[k]), reverse("sim:ringkasan", args=[k]) + "?q=siti",
            reverse("sim:warga", args=[k]), reverse("sim:kk-baru", args=[k]), reverse("sim:kk", args=[k, person.kk_id]),
            reverse("sim:kk-ubah", args=[k, person.kk_id]), reverse("sim:anggota-baru", args=[k, person.kk_id]),
            reverse("sim:anggota-ubah", args=[k, person.pk]), reverse("sim:scan", args=[k]), reverse("sim:scan-detail", args=[k, doc.pk]),
            reverse("sim:surat", args=[k]), reverse("sim:surat", args=[k]) + "?filter=semua",
            reverse("sim:surat-pilih", args=[k]) + f"?penduduk={person.pk}", reverse("sim:surat-baru", args=[k, "usaha"]) + f"?penduduk={person.pk}",
            reverse("sim:surat-detail", args=[k, s.pk]), reverse("sim:surat-detail", args=[k, issued.pk]),
            reverse("sim:surat-cetak", args=[k, s.pk]), reverse("sim:surat-cetak", args=[k, issued.pk]),
            reverse("sim:format", args=[k]), reverse("sim:format-baru", args=[k]), reverse("sim:format-ubah", args=[k, jenis.pk]),
            reverse("sim:format-contoh", args=[k, jenis.pk]), reverse("sim:pengumuman", args=[k]),
            reverse("sim:pengumuman-ubah", args=[k, note.pk]), reverse("sim:jaringan", args=[k]),
            reverse("sim:ketahui", args=[k, child_letter.pk]), reverse("sim:ketahui", args=[k, child_letter.pk]) + "?cetak=1",
            reverse("sim:pengaturan", args=[k]), reverse("sim:perpanjang", args=[k]), reverse("akun:pesan-pilih"),
        ]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        anon = Client(HTTP_HOST="testserver")
        for url in [w.public_path, rt.public_path, reverse("warga:ajukan", args=[k, "usaha"]), reverse("warga:lacak-cari"),
                    s.lacak_path, issued.lacak_path, issued.verify_path]:
            with self.subTest(url=url):
                self.assertEqual(anon.get(url).status_code, 200)
        # Halaman pesan paket SIM (formulir data wilayah).
        Package.objects.filter(code="sim-tumbuh").update(is_active=True, price=35000)
        self.assertContains(self.client.get("/akun/pesan/sim-tumbuh/"), "Data instansi")


# ---------------------------------------------------------------------------
# Data warga: KK + anggota, kepala keluarga otomatis
# ---------------------------------------------------------------------------
class DataWargaTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_member()
        self.w = make_wilayah(self.owner)
        login_member(self.client, self.owner)

    def test_scan_moved_into_data_warga(self):
        page = self.client.get(reverse("sim:warga", args=[self.w.kode]))
        html = page.content.decode()
        nav = html[html.index('class="toko-tabs'):]
        nav = nav[: nav.index("</nav>")]
        self.assertNotIn("Scan KK/KTP", nav)  # bukan tab sendiri lagi
        self.assertIn("Data warga", nav)
        self.assertContains(page, "Scan KK/KTP")  # tombol di dalam tab Data warga
        self.assertNotContains(page, "Dari foto KK")
        scan = self.client.get(reverse("sim:scan", args=[self.w.kode])).content.decode()
        tabs = scan[scan.index('class="toko-tabs'):]
        active = tabs.split('aria-current="page">')[1][:300]
        self.assertIn("Data warga", active)  # halaman scan tetap di tab Data warga

    def test_new_kk_form_prefills_area_and_first_row_is_head(self):
        page = self.client.get(reverse("sim:kk-baru", args=[self.w.kode]))
        self.assertNotContains(page, 'name="kepala_nama"')
        self.assertContains(page, 'value="SUKAMAJU"')  # kelurahan dari data wilayah
        self.assertContains(page, 'value="005"')  # RT
        self.assertContains(page, '<option value="Kepala Keluarga" selected>')

    def test_head_rules_and_duplicate_nik(self):
        other = make_warga(self.w)  # NIK sudah terdaftar di KK lain
        url = reverse("sim:kk-baru", args=[self.w.kode])
        rows = [{"nama": "budi", "hubungan": "Kepala Keluarga"}, {"nama": "ani", "hubungan": "Kepala Keluarga"}]
        self.assertContains(self.client.post(url, kk_post(rows)), "Hanya satu anggota", status_code=400)
        rows[1]["hubungan"] = "Istri"
        rows[1]["nik"] = other.nik
        self.assertContains(self.client.post(url, kk_post(rows)), "sudah terdaftar atas nama SITI AMINAH", status_code=400)
        rows[1]["nik"] = "3201010101900077"
        rows.append({"nama": "cici", "nik": "3201010101900077"})
        self.assertContains(self.client.post(url, kk_post(rows)), "sama dengan anggota lain", status_code=400)
        rows.pop()
        r = self.client.post(url, kk_post(rows))
        self.assertEqual(r.status_code, 302)
        kk = KartuKeluarga.objects.get(kepala_nama="BUDI")
        self.assertEqual(kk.anggota.count(), 2)

    def test_edit_kk_changes_head_and_removes_member(self):
        kk = KartuKeluarga.objects.create(wilayah=self.w, kepala_nama="AHMAD")
        a = Penduduk.objects.create(wilayah=self.w, kk=kk, nama="AHMAD", hubungan="Kepala Keluarga", urutan=1)
        b = Penduduk.objects.create(wilayah=self.w, kk=kk, nama="SITI", hubungan="Istri", urutan=2)
        url = reverse("sim:kk-ubah", args=[self.w.kode, kk.pk])
        self.assertContains(self.client.get(url), "Kepala keluarga: <b")
        rows = [{"id": a.pk, "nama": "AHMAD", "hubungan": "Lainnya", "DELETE": "on"},
                {"id": b.pk, "nama": "SITI", "hubungan": "Kepala Keluarga"}]
        r = self.client.post(url, kk_post(rows, initial=2))
        self.assertEqual(r.status_code, 302)
        kk.refresh_from_db()
        self.assertEqual(kk.kepala_nama, "SITI")
        self.assertFalse(Penduduk.objects.filter(pk=a.pk).exists())

    def test_single_member_form_keeps_one_head(self):
        person = make_warga(self.w)  # SITI, Istri di KK AHMAD (tanpa kepala keluarga)
        kk = person.kk
        url = reverse("sim:anggota-baru", args=[self.w.kode, kk.pk])
        data = {"nama": "Ahmad", "hubungan": "Kepala Keluarga", "kewarganegaraan": "WNI", "status": "aktif", "urutan": "1"}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        kk.refresh_from_db()
        self.assertEqual(kk.kepala_nama, "AHMAD")
        data["nama"] = "Joko"
        self.assertContains(self.client.post(url, data), "sudah punya kepala keluarga (AHMAD)", status_code=400)
        head = kk.anggota.get(nama="AHMAD")
        self.client.post(reverse("sim:anggota-hapus", args=[self.w.kode, head.pk]))
        kk.refresh_from_db()
        self.assertEqual(kk.kepala_nama, "")
        self.assertContains(self.client.get(reverse("sim:kk", args=[self.w.kode, kk.pk])), "Belum ada kepala keluarga")


class SuratDeleteTests(SeededTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_member()
        self.w = make_wilayah(self.owner)
        login_member(self.client, self.owner)

    def make_issued(self):
        jenis = self.w.jenis_surat.get(kode="domisili")
        s = services.create_request(self.w, jenis, {"nama": "Siti", "nik": NIK, "keperluan": "Tes"}, source=Surat.SOURCE_DIRECT)
        return services.issue(s)

    def test_delete_issued_letter_and_number_not_reused(self):
        first = self.make_issued()
        self.assertEqual(first.nomor_urut, 1)
        cek = reverse("warga:cek", args=[first.verify_token])
        self.assertEqual(self.client.get(cek).status_code, 200)
        url = reverse("sim:surat-detail", args=[self.w.kode, first.pk])
        self.assertContains(self.client.get(url), "Hapus surat ini")
        r = self.client.post(url, {"aksi": "hapus"})
        self.assertRedirects(r, reverse("sim:surat", args=[self.w.kode]) + "?filter=semua&ok=surat-hapus", fetch_redirect_response=False)
        self.assertFalse(Surat.objects.filter(pk=first.pk).exists())
        self.assertEqual(self.client.get(cek).status_code, 404)  # QR surat yang dihapus tidak berlaku
        second = self.make_issued()
        self.assertEqual(second.nomor_urut, 2)  # nomor 1 tidak dipakai ulang

    def test_pending_request_cannot_be_deleted(self):
        jenis = self.w.jenis_surat.get(kode="domisili")
        s = services.create_request(self.w, jenis, {"nama": "Siti", "nik": NIK, "keperluan": "Tes"}, source=Surat.SOURCE_ONLINE)
        url = reverse("sim:surat-detail", args=[self.w.kode, s.pk])
        self.assertNotContains(self.client.get(url), "Hapus surat ini")
        self.client.post(url, {"aksi": "hapus"})
        self.assertTrue(Surat.objects.filter(pk=s.pk).exists())


# ---------------------------------------------------------------------------
# Pembaca KK: fungsi murni & deteksi tabel (tanpa Tesseract)
# ---------------------------------------------------------------------------
class KkReaderTests(SimpleTestCase):
    def test_head_lines_with_two_columns_and_noise(self):
        data = ocr.parse_head_lines([
            "Sw aes Nama Kepala Keluarga :BUDI SANTOSO Desa/Kelurahan : SUKA MAJU",
            "Ye Ai Alamat 1 JL. MAWAR NO 4 Kecamatan : CIBINONG",
            "RT/RW : 006/003 Kabupaten/Kota : BOGOR",
            "REPUBLIK INDONESIA Kode Pos : 16911 Provinsi : JAWA BARAT Dn |",
            "Dikeluarkan Tanggal: [ 25-06-2025 |",
        ])
        self.assertEqual(data["kepala_nama"], "BUDI SANTOSO")
        self.assertEqual((data["kelurahan"], data["kecamatan"], data["kota"], data["provinsi"]),
                         ("SUKA MAJU", "CIBINONG", "BOGOR", "JAWA BARAT"))
        self.assertEqual((data["alamat"], data["rt"], data["rw"], data["kode_pos"]), ("JL. MAWAR NO 4", "006", "003", "16911"))
        self.assertEqual(data["tanggal_dikeluarkan"], "2025-06-25")

    def test_value_normalization(self):
        self.assertEqual(ocr._normalize("pendidikan", "SLTA'SEDERAJAT"), "SLTA/SEDERAJAT")
        self.assertEqual(ocr._normalize("pendidikan", "TIOAX/BELUM SEKOLAH"), "TIDAK/BELUM SEKOLAH")
        self.assertEqual(ocr._normalize("pekerjaan", "PELAJARIMAHASISWA"), "PELAJAR/MAHASISWA")
        self.assertEqual(ocr._normalize("jenis_kelamin", "LAKH AKI"), "L")
        self.assertEqual(ocr._normalize("status_perkawinan", "CERAI TERCATAT"), "Cerai Tercatat")
        self.assertEqual(ocr._normalize("hubungan", "KEPALA KELUARGA"), "Kepala Keluarga")
        self.assertEqual(ocr._normalize("golongan_darah", "TIDAK TAHU"), "TIDAK TAHU")
        self.assertEqual(ocr._normalize("golongan_darah", "0"), "O")
        self.assertEqual(ocr._normalize("nama_ibu", "BUDI SANTOSO sat"), "BUDI SANTOSO")
        self.assertEqual(ocr._normalize("nama", "-"), "")
        self.assertEqual(ocr.parse_date("23012005"), "2005-01-23")
        self.assertEqual(ocr._vote("tanggal_lahir", [["02-05-1984"], ["02-05-1924"], ["02-05-1984"]]), ["1984-05-02"])
        self.assertEqual(ocr._vote("tanggal_lahir", [["1405-2004"], ["100-20"], ["x"]]), [""])

    def test_kk_number_region_fix_and_head(self):
        self.assertEqual(ocr._region_fix("1501050409200002", ["6501055107170001"]), "6501050409200002")
        self.assertEqual(ocr._region_fix("6501050409200002", ["3201010101900001"]), "6501050409200002")
        data = ocr.finish_kk({"kepala_nama": "BUDI SANTOSO", "anggota": [{"nama": "BUDI SANTOS", "hubungan": ""}, {"nama": "ANI"}]})
        self.assertEqual(data["anggota"][0]["hubungan"], "Kepala Keluarga")

    def test_detects_kk_tables_from_lines(self):
        from PIL import Image, ImageDraw

        img = Image.new("L", (2000, 1300), 255)
        draw = ImageDraw.Draw(img)
        widths_a = [40, 400, 190, 100, 220, 110, 130, 290, 290, 120]  # No + 9 kolom (KK 2020+)
        widths_b = [40, 190, 120, 230, 180, 150, 150, 400, 430]  # No + 8 kolom

        def table(top, widths, rows=12, height=40):
            x0, x1 = 50, 50 + sum(widths)
            for r in range(rows + 1):
                draw.rectangle((x0, top + r * height, x1, top + r * height + 2), fill=0)
            x = x0
            for w_ in [0] + widths:
                x += w_
                draw.rectangle((x, top, x + 2, top + rows * height + 2), fill=0)
            for r in range(rows):  # isian huruf di tiap sel supaya mirip KK
                draw.text((x0 + 60, top + r * height + 14), "AHMAD 1111", fill=0)
            return top + rows * height

        end = table(200, widths_a)
        table(end + 30, widths_b)
        h_lines, rows = ocr._table_rows(ocr._ink(img))
        groups = ocr._groups(rows, img.width)
        self.assertEqual([len(g[0].cols) for g in groups], [10, 9])
        self.assertEqual([len(g) for g in groups], [12, 12])
        self.assertIn(len(groups[0][0].cols) - 1, ocr.TABLE_A)
        self.assertIn(len(groups[1][0].cols) - 1, ocr.TABLE_B)


@skipUnless(ocr.is_available() and ocr.has_indonesian(), "Tesseract + data bahasa ind belum terpasang")
class KkReaderTesseractTests(SimpleTestCase):
    """Ujung ke ujung dengan Tesseract sungguhan pada KK sintetis (data palsu, digambar oleh tes)."""

    def make_kk(self, path):
        from pathlib import Path

        from django.conf import settings
        from PIL import Image, ImageDraw, ImageFont

        font_path = Path(settings.BASE_DIR) / "scripts" / "fonts" / "PlusJakartaSans-var.ttf"
        small, head, big = (ImageFont.truetype(str(font_path), size) for size in (17, 22, 44))
        img = Image.new("L", (2400, 1700), 255)
        d = ImageDraw.Draw(img)
        d.text((900, 40), "KARTU KELUARGA", font=big, fill=0)
        d.text((880, 100), "No. 3201010101900099", font=big, fill=0)
        heads = [("Nama Kepala Keluarga", "BUDI SANTOSO", "Desa/Kelurahan", "SUKAMAJU"),
                 ("Alamat", "JL. MELATI NO 1", "Kecamatan", "CIBINONG"),
                 ("RT/RW", "005/003", "Kabupaten/Kota", "BOGOR"),
                 ("Kode Pos", "16911", "Provinsi", "JAWA BARAT")]
        for i, (l1, v1, l2, v2) in enumerate(heads):
            y = 180 + i * 34
            d.text((300, y), l1, font=head, fill=0)
            d.text((560, y), ": " + v1, font=head, fill=0)
            d.text((1400, y), l2, font=head, fill=0)
            d.text((1620, y), ": " + v2, font=head, fill=0)
        widths_a = [50, 430, 260, 150, 220, 160, 130, 320, 300, 160]
        widths_b = [50, 260, 170, 300, 200, 170, 170, 430, 430]
        rows_a = [["1", "BUDI SANTOSO", "3201011205850001", "LAKI-LAKI", "BOGOR", "12-05-1985", "ISLAM", "SLTA/SEDERAJAT", "WIRASWASTA", "A"],
                  ["2", "SITI AMINAH", "3201014101900002", "PEREMPUAN", "BANDUNG", "01-01-1990", "ISLAM", "DIPLOMA IV/STRATA I", "GURU", "O"],
                  ["3", "RIZKY PRATAMA", "3201011503150003", "LAKI-LAKI", "BOGOR", "15-03-2015", "ISLAM", "TIDAK/BELUM SEKOLAH", "BELUM/TIDAK BEKERJA", "TIDAK TAHU"]]
        rows_b = [["1", "KAWIN TERCATAT", "20-06-2012", "KEPALA KELUARGA", "WNI", "-", "-", "SLAMET", "SUMIATI"],
                  ["2", "KAWIN TERCATAT", "20-06-2012", "ISTRI", "WNI", "-", "-", "HASAN", "AMINAH"],
                  ["3", "BELUM KAWIN", "-", "ANAK", "WNI", "-", "-", "BUDI SANTOSO", "SITI AMINAH"]]

        def table(top, widths, header, rows, height=40):
            x0 = 60
            lines = [top, top + 60, top + 90] + [top + 90 + (r + 1) * height for r in range(10)]
            for y in lines:
                d.rectangle((x0, y, x0 + sum(widths), y + 2), fill=0)
            x = x0
            for w_ in [0] + widths:
                x += w_
                d.rectangle((x, top, x + 2, lines[-1] + 2), fill=0)
            xs = [x0 + sum(widths[:i]) for i in range(len(widths))]
            for i, text in enumerate(header):
                d.text((xs[i] + 8, top + 18), text, font=small, fill=0)
                d.text((xs[i] + 8, top + 64), f"({i})" if i else "", font=small, fill=0)
            for r in range(10):
                values = rows[r] if r < len(rows) else [str(r + 1)] + ["-"] * (len(widths) - 1)
                for i, text in enumerate(values):
                    d.text((xs[i] + 8, top + 90 + r * height + 10), text, font=small, fill=0)
            return lines[-1]

        end = table(330, widths_a, ["No", "Nama Lengkap", "NIK", "Jenis Kelamin", "Tempat Lahir", "Tanggal Lahir", "Agama",
                                    "Pendidikan", "Jenis Pekerjaan", "Golongan Darah"], rows_a)
        end = table(end + 20, widths_b, ["No", "Status Perkawinan", "Tgl Perkawinan", "Status Hubungan", "Kewarganegaraan",
                                         "No. Paspor", "No. KITAP", "Ayah", "Ibu"], rows_b)
        d.text((120, end + 40), "Dikeluarkan Tanggal: 25-06-2025", font=head, fill=0)
        img.rotate(0.8, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255).save(path)

    def test_reads_synthetic_kk(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/kk.png"
            self.make_kk(path)
            result = ocr._read_structured(ocr.tesseract_cmd(), path, tmp)
        self.assertIsNotNone(result)
        data = ocr.finish_kk(result[0])
        self.assertEqual(data["kepala_nama"], "BUDI SANTOSO")
        self.assertEqual((data.get("kelurahan"), data.get("rt"), data.get("rw")), ("SUKAMAJU", "005", "003"))
        self.assertEqual(data.get("tanggal_dikeluarkan"), "2025-06-25")
        members = data["anggota"]
        self.assertEqual([m["nama"] for m in members], ["BUDI SANTOSO", "SITI AMINAH", "RIZKY PRATAMA"])
        self.assertEqual([m["nik"] for m in members], ["3201011205850001", "3201014101900002", "3201011503150003"])
        self.assertEqual([m["hubungan"] for m in members], ["Kepala Keluarga", "Istri", "Anak"])
        self.assertEqual(members[1]["tanggal_lahir"], "1990-01-01")
        self.assertEqual(members[1]["pendidikan"], "DIPLOMA IV/STRATA I")
        self.assertEqual(members[2]["golongan_darah"], "TIDAK TAHU")
        self.assertEqual(members[0]["status_perkawinan"], "Kawin Tercatat")


class PhotoReaderUnitTests(SimpleTestCase):
    """Pemulihan spasi & pencocokan ejaan untuk pembaca foto (tanpa mesin OCR)."""

    def test_split_joined_words(self):
        vocab = set(ocr_foto.COMMON_WORDS) | {"HAIRUL", "MULYATI"}
        self.assertEqual(ocr_foto.split_joined("HAIRULFITRI", vocab), "HAIRUL FITRI")
        self.assertEqual(ocr_foto.split_joined("SITIAMINAH", vocab), "SITI AMINAH")
        self.assertEqual(ocr_foto.split_joined("RAHMADABDULLAH", vocab), "RAHMAD ABDULLAH")
        self.assertEqual(ocr_foto.split_joined("SYUKURH", vocab), "SYUKUR H")  # inisial di akhir
        self.assertEqual(ocr_foto.split_joined("FITRIA", vocab), "FITRIA")  # nama asli, bukan FITRI + A
        self.assertEqual(ocr_foto.split_joined("NURDIN", vocab), "NURDIN")  # tidak dipecah jadi NUR DIN
        self.assertEqual(ocr_foto.split_joined("ALESHA", vocab), "ALESHA")

    def test_fixer_uses_spaced_text_from_same_document(self):
        boxes = [ocr_foto.Box("MULYATI HAMIDAH", 0, 0, 10, 5, 1.0), ocr_foto.Box(":JL.MANGGIS 1", 0, 0, 10, 5, 1.0)]
        fix = ocr_foto._fixer(boxes)
        self.assertEqual(fix("nama_ibu", "MULYATIHAMIDAH"), "MULYATI HAMIDAH")
        self.assertEqual(fix("head", "Alamat :JL.MANGGIS 1"), "Alamat :JL. MANGGIS 1")

    def test_dictionary_values_ignore_missing_spaces(self):
        self.assertEqual(ocr._normalize("status_perkawinan", "BELUMKAWIN"), "Belum Kawin")
        self.assertEqual(ocr._normalize("status_perkawinan", "KAWINBELUMTERCATAT"), "Kawin Belum Tercatat")
        self.assertEqual(ocr._normalize("hubungan", "KEPALAKELUARGA"), "Kepala Keluarga")
        self.assertEqual(ocr._normalize("pendidikan", "TIDAK/BELUMSEKOLAH"), "TIDAK/BELUM SEKOLAH")
        self.assertEqual(ocr._normalize("pekerjaan", "MENGURUSRUMAHTANGGA"), "MENGURUS RUMAH TANGGA")
        self.assertEqual(ocr._normalize("golongan_darah", "TIDAKTAHU"), "TIDAK TAHU")
        self.assertEqual(ocr.parse_head_lines(["No.b 6404053103080024"])["no_kk"], "6404053103080024")


@skipUnless(ocr_foto.available(), "PaddleOCR (rapidocr-onnxruntime) belum terpasang")
class PhotoReaderTests(SimpleTestCase):
    """Foto KK sintetis (data palsu) yang diputar 90° dan miring perspektif, seperti difoto dengan HP."""

    def test_reads_rotated_perspective_photo(self):
        import tempfile

        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            flat = f"{tmp}/kk.png"
            KkReaderTesseractTests().make_kk(flat)
            img = cv2.imread(flat)
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)  # difoto tegak
            h, w = img.shape[:2]
            canvas = np.full((h + 200, w + 200, 3), 200, np.uint8)  # alas meja di sekeliling
            src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
            dst = np.float32([[130, 90], [w + 120, 60], [w + 160, h + 150], [60, h + 120]])
            canvas = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w + 200, h + 200),
                                         dst=canvas, borderMode=cv2.BORDER_TRANSPARENT)
            path = f"{tmp}/foto.jpg"
            cv2.imwrite(path, canvas, [cv2.IMWRITE_JPEG_QUALITY, 85])
            data, _ = ocr_foto.read_kk(path)
        data = ocr.finish_kk(data)
        self.assertEqual(data["no_kk"], "3201010101900099")
        self.assertEqual(data["kepala_nama"], "BUDI SANTOSO")
        self.assertEqual((data.get("kelurahan"), data.get("rt"), data.get("rw")), ("SUKAMAJU", "005", "003"))
        members = data["anggota"]
        self.assertEqual([m["nama"] for m in members], ["BUDI SANTOSO", "SITI AMINAH", "RIZKY PRATAMA"])
        self.assertEqual([m["nik"] for m in members], ["3201011205850001", "3201014101900002", "3201011503150003"])
        self.assertEqual([m["hubungan"] for m in members], ["Kepala Keluarga", "Istri", "Anak"])
        self.assertEqual(members[1]["tanggal_lahir"], "1990-01-01")
        self.assertEqual(members[0]["status_perkawinan"], "Kawin Tercatat")
