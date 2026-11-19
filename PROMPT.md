# Brief Proyek: Website HANS Project (hansproject.app)

Halo Claude Code. Tolong bangun website landing page + pricelist untuk bisnis saya, **HANS Project**, menggunakan **Python** dan database **MariaDB**.

Semua bahan ada di folder ini. Baca semuanya dulu sebelum mulai:

| File | Isi | Sifat |
|---|---|---|
| `docs/01-bisnis-dan-harga.md` | Paket, harga, fitur, aturan pembayaran, kebijakan data | **Fakta bisnis, wajib akurat** |
| `docs/02-brand-dan-desain.md` | Logo, warna, gaya bahasa, target pembaca | Arahan, boleh dikembangkan |
| `docs/03-ide-struktur-halaman.md` | Usulan susunan halaman publik & panel admin | **Hanya ide**, bebas diubah |
| `docs/04-teknis-dan-instalasi.md` | Lingkungan kerja, database, env, venv, batch instalasi Windows | Kebutuhan + saran |
| `docs/05-keamanan.md` | Standar keamanan website | **Kebutuhan, wajib dipenuhi** |
| `assets/logo-h.png` | Logo "H" (PNG transparan) | Pakai apa adanya |

---

## Revisi pemilik (17 November 2026) — BERLAKU DI ATAS ISI LAIN

Keputusan terbaru ini menggantikan bagian brief yang bertentangan:

1. **Semua keperluan lewat DM Instagram [@hansproject.app](https://www.instagram.com/hansproject.app).** Tidak ada saluran kontak pribadi lain (nomor telepon/chat) yang mengarah ke pemilik, di website maupun di database.
2. **Pesan & tanya lewat akun (wajib daftar/login).**
   - Tombol paket bernama **"Pesan Sekarang"**. Bila pengunjung belum login, tombol ini mengarahkan ke halaman **daftar/login** dulu.
   - Tombol **"Tanya Kami"** juga wajib login.
   - **Daftar / masuk hanya dengan akun Google** (keputusan 17 November 2026). Yang belum punya akun Google membuatnya dulu lewat Google. Data pelanggan tetap disimpan di database sendiri.
   - Setelah login pertama, pelanggan wajib melengkapi **nomor HP** dan **nama usaha**.
   - Halaman **Profil** berisi: data diri, status pesanan, pertanyaan & jawabannya, dan tombol keluar.
   - Pesanan dikelola di panel (status + catatan untuk pelanggan). Bukti bayar dikirim lewat halaman pesanan di akun pelanggan.
3. **Kontak alternatif tanpa login: DM Instagram [@hansproject.app](https://www.instagram.com/hansproject.app).** Username bisa diubah di panel.
4. **Tombol "Daftar / Masuk" dengan ikon** di header. Setelah login berganti menjadi tombol **"Profil"**.
5. **Navigasi HP memakai menu bawah** (bottom navigation), **bukan** menu burger: Beranda · Fitur · **Harga** (tombol tengah menonjol) · Jasa · Masuk/Profil.
6. **Istilah teknis tampil secara bawaan** (saklar "Tampilkan istilah teknis" menyala). Pengunjung bisa mematikannya.
7. **Gaya UI:** tema terang, gradasi warna logo, **sudut tajam** (potongan diagonal seperti pilar logo "H"), efek kaca/blur secukupnya, ringan, responsif, modern.
8. **Database produksi sudah berisi tabel & data lain.** Website wajib memakai database/tabelnya sendiri tanpa menyentuh tabel lain. Semua tabel website berawalan **`hp_`**.
9. **Label paket Tumbuh:** "Paling Direkomendasikan" (jujur, belum ada data pelanggan).
10. **Port bawaan website: 8432** (pengembangan: `http://127.0.0.1:8432`; di server Waitress juga mendengarkan di `127.0.0.1:8432` di belakang Caddy).
11. **Aplikasi kasir (18 November 2026):** semua toko di satu aplikasi & port yang sama, alamat `<nama>.hansproject.app`. Pengelolaan toko sepenuhnya di hansproject.app; subdomain hanya untuk login kasir (`/kasir/`, nama pengguna + PIN buatan pemilik). Online saja, cetak struk lewat browser, penyimpanan Tunas 1 GB, data dihapus 30 hari setelah masa aktif habis. Rincian: `docs/06-aplikasi-kasir.md`.
12. **Syarat & Ketentuan dan Kebijakan Privasi final (19 November 2026)** berdasarkan riset hukum terbaru (UU PDP 27/2022 + PP 33/2026, UU Perlindungan Konsumen, UU KUP). Setelah login Google pertama, muncul **popup** berisi tautan kedua dokumen dan satu kotak centang persetujuan; setelah disetujui tidak muncul lagi untuk akun itu (kecuali versi dokumen diubah di panel). Teks: `apps/content/legal.py`.
13. **Area akun (19 November 2026):** tombol Profil/Masuk di header (juga HP), menu bawah website berisi Bantuan. Di area akun tombol header menjadi Beranda dan menu berganti: Dashboard (monitoring semua toko & outlet + pengumuman terjadwal dari panel, tanpa tombol tutup) · Pesanan (termasuk refund) · Toko · Chat (bubble, teks/gambar, balas; admin bisa menutup → Selesai, obrolan baru terpisah, riwayat tetap ada) · Akun.

## Lingkungan kerja (fakta)

- **Bahasa pemrograman:** Python. Wajib memakai **virtual environment (venv)**.
- **Database:** MariaDB, sudah terpasang dan berjalan di **port 3307** (bukan port default 3306).
  - Komputer pengembangan: MariaDB **10.11** versi ZIP di `%USERPROFILE%\sigap-mariadb`, port 3307. Dinyalakan dengan `powershell -ExecutionPolicy Bypass -File scripts\windows\mariadb-dev.ps1` dari proyek SIGAP.
  - Server produksi: database **sudah berisi tabel dan data lain**. Lihat revisi no. 8.
- **Pengembangan:** dimulai di komputer ini (komputer tempat Anda berjalan sekarang).
- **Produksi:** nanti dipindahkan ke **server Windows**. Siapkan **file batch (.bat)** untuk instalasi dan pengoperasian di sana.
- **Domain:** hansproject.app sudah dimiliki. Urusan domain tidak perlu dipikirkan.

## Tujuan website

1. Membuat calon pelanggan **paham apa yang dijual** dalam beberapa detik, termasuk orang yang jarang pakai teknologi dan orang di daerah.
2. Membuat mereka **memilih paket yang cocok** tanpa bingung.
3. Membuat mereka **memesan lewat akun di website** (tombol "Pesan Sekarang", wajib daftar/login). Tidak ada payment gateway. Semua keperluan lewat **DM Instagram @hansproject.app** (atau menu Tanya Kami di akun).
4. Terlihat **terpercaya dan profesional**, supaya orang yang paham teknologi juga yakin.
5. **Aman.** Lihat `docs/05-keamanan.md`.
6. **Mudah saya kelola sendiri.** Harga, isi paket, FAQ, username Instagram, dan sejenisnya sebaiknya bisa saya ubah tanpa menyentuh kode, misalnya lewat panel admin yang datanya tersimpan di database.

## Kebebasan Anda

**Saya tidak ingin membatasi Anda.** Kalau Anda punya ide yang lebih baik dari segi apa pun (framework, arsitektur, desain, susunan halaman, cara menyampaikan harga, animasi, kata-kata, SEO, fitur tambahan, cara deploy di Windows), silakan pakai. Semua usulan di `docs/` hanya titik awal, bukan aturan.

Yang **tidak boleh diubah**:
- **Fakta bisnis** di `docs/01-bisnis-dan-harga.md`: harga, isi paket, batasan, dan kebijakan. Boleh ditulis ulang supaya lebih mudah dipahami, tapi maknanya harus sama. Kalau ada yang menurut Anda janggal, beri tahu saya di ringkasan akhir. Jangan diubah diam-diam.
- **Lingkungan kerja** di atas: Python, venv, MariaDB port 3307, produksi Windows.
- **Standar keamanan** di `docs/05-keamanan.md`. Boleh ditingkatkan, tidak boleh diturunkan.

Ada juga dua hal yang tolong dijaga, karena ini soal kejujuran ke pelanggan:
- **Jangan mengarang testimoni, jumlah pelanggan, rating, logo klien, atau angka statistik.** Saya belum punya data itu. Kalau perlu bagian testimoni, siapkan strukturnya (misalnya dikelola dari admin) dan biarkan tersembunyi sampai saya isi.
- Jangan menjanjikan fitur yang tidak ada di `docs/01`.

## Dua jenis pembaca, satu halaman

Pembaca website ini ada dua:
- **Orang awam:** pemilik warung, pedagang di daerah, yang tidak paham istilah seperti "GB", "subdomain", atau "PWA".
- **Orang yang paham teknologi:** ingin melihat angka dan istilah teknis.

Website harus melayani **keduanya**. `docs/01` sudah menyediakan dua versi untuk setiap poin (bahasa sederhana + detail teknis). Istilah teknis **tampil secara bawaan** dan bisa disembunyikan lewat saklar. Syaratnya: orang awam tidak kewalahan, dan orang teknis tidak merasa informasinya kurang.

## Yang saya harapkan sebagai hasil

- Website yang berjalan di komputer ini (dalam venv, terhubung ke MariaDB port 3307), dengan data awal paket, harga, dan FAQ sesuai `docs/01`.
- `.env.example` (tanpa rahasia asli) dan file konfigurasi yang jelas. File `.env` asli tidak boleh masuk git.
- **File batch untuk server produksi Windows** (instalasi, menjalankan, memperbarui, backup, dll., lihat `docs/04`).
- Script untuk setup pengembangan di komputer ini, sesuai sistem operasi komputer ini.
- `README.md` dalam bahasa Indonesia sederhana: cara menjalankan di lokal, cara mengubah konfigurasi, cara memakai panel admin, dan **panduan langkah demi langkah memindahkan ke server Windows**.
- Di akhir, berikan **ringkasan**: apa yang dibuat, keputusan penting (terutama yang berbeda dari usulan di `docs/`), langkah keamanan yang diterapkan, dan apa saja yang masih perlu saya isi (placeholder).

Kalau ada hal penting yang benar-benar tidak bisa Anda putuskan sendiri (misalnya kredensial database), tanya saya. Untuk hal kecil, ambil keputusan terbaik lalu catat di ringkasan.

Selamat bekerja!
