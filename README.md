# Website HANS Project (hansproject.app)

Website landing page + daftar harga HANS Project, lengkap dengan **panel pengelola** untuk mengubah harga, isi paket, FAQ, kontak Instagram, dan lainnya **tanpa menyentuh kode**, **aplikasi kasir (POS)** untuk pelanggan Paket Tunas/Tumbuh di alamat toko masing-masing (`<nama>.hansproject.app`), serta **SIM** untuk RT, RW, kelurahan/desa, dan kecamatan (data warga dari foto KK/KTP, surat online, cetak surat). Tiket online sedang disiapkan.

- Bahasa: Python 3.12+ (wajib di dalam virtual environment `.venv`)
- Framework: Django 5.2 LTS (dukungan keamanan sampai April 2028)
- Database: MariaDB (port bawaan **3307**)
- Server produksi: Windows — Waitress (server aplikasi) + Caddy (HTTPS otomatis) + Windows Service

---

## Daftar isi

1. [Isi folder](#1-isi-folder)
2. [Menjalankan di komputer pengembangan](#2-menjalankan-di-komputer-pengembangan)
3. [Mengubah konfigurasi (.env)](#3-mengubah-konfigurasi-env)
4. [Memakai panel pengelola](#4-memakai-panel-pengelola)
5. [Memindahkan ke server Windows (langkah demi langkah)](#5-memindahkan-ke-server-windows-langkah-demi-langkah)
6. [HTTPS dengan Caddy](#6-https-dengan-caddy)
7. [Mengamankan server Windows](#7-mengamankan-server-windows)
8. [Backup, restore, dan pembaruan](#8-backup-restore-dan-pembaruan)
9. [Daftar file .bat](#9-daftar-file-bat)
10. [Memeriksa & memperbarui dependensi](#10-memeriksa--memperbarui-dependensi)
11. [Masalah yang sering terjadi](#11-masalah-yang-sering-terjadi)
12. [Untuk programmer](#12-untuk-programmer)

---

## 1. Isi folder

```
hansproject/
├── install.bat, start.bat, stop.bat, ...   ← file batch (lihat bagian 9)
├── .env.example        ← contoh konfigurasi (salin jadi .env)
├── manage.py           ← perintah Django
├── apps/
│   ├── core/           ← keamanan, awalan tabel hp_, log, backup/restore, format teks, upload gambar
│   ├── accounts/       ← akun admin, 2FA, pembatasan percobaan login
│   ├── content/        ← data situs: paket, harga, FAQ, pengaturan, data awal
│   ├── web/            ← halaman publik, SEO, pencatat klik tombol kontak
│   ├── members/        ← akun pelanggan: masuk dengan Google, pesanan, bukti bayar, tanya
│   ├── pos/            ← aplikasi kasir: langganan, toko (1 toko = 1 subdomain = 1 akun kasir), barang, transaksi, laporan
│   └── panel/          ← panel pengelola (CRUD generik)
├── config/             ← setelan (development / production / test)
├── templates/          ← tampilan HTML
├── static/             ← CSS, JavaScript, font, gambar (sudah dioptimalkan)
├── deploy/             ← contoh Caddyfile, templat Windows Service, SQL manual
├── requirements/       ← daftar dependensi (versi + hash terkunci)
├── scripts/            ← alat bantu (.env, database, service, aset gambar)
├── tests/              ← tes otomatis
└── docs/, assets/      ← brief proyek & logo asli
```

Folder yang **dibuat otomatis** dan tidak perlu disalin antar komputer: `.venv`, `staticfiles`, `logs`, `run`, `tools`. Folder `media` (gambar upload), `private` (foto bukti bayar pelanggan, **rahasia**), dan `backups` berisi data — ikut dipindahkan bila perlu.

---

## 2. Menjalankan di komputer pengembangan

Kebutuhan: Python 3.12 atau lebih baru, dan MariaDB yang sudah berjalan.

1. Klik dua kali **`setup-dev.bat`**. File ini akan:
   - membuat `.venv` dan memasang dependensi,
   - membuat `.env` (mode development) — Anda ditanya **port MariaDB**,
   - membuat **database baru** `hansproject_web` dan **user khusus** `hansproject_app` dengan password acak. Untuk ini Anda diminta user & password **admin MariaDB (misalnya root) satu kali saja**. Password root **tidak disimpan**.
   - membuat tabel, mengisi data awal, lalu meminta Anda membuat akun admin panel.
2. Klik dua kali **`run-dev.bat`**, lalu buka <http://127.0.0.1:8432/>.
3. Alamat panel ditampilkan di akhir `setup-dev.bat` (juga tertulis di `.env` pada `ADMIN_URL_PATH`).

Tes otomatis: `test.bat`. Pemeriksaan keamanan: `cek-keamanan.bat`.

---

## 3. Mengubah konfigurasi (.env)

Semua setelan teknis ada di file **`.env`** (buka dengan Notepad). Setiap baris sudah diberi penjelasan. Yang paling sering diubah:

| Setelan | Arti |
|---|---|
| `ALLOWED_HOSTS` | Nama domain website, dipisah koma |
| `SITE_URL` | Alamat utama, harus `https://...` di produksi |
| `ADMIN_URL_PATH` | Bagian alamat panel. Contoh `kelola-a1b2c3d4e5f6` → `https://hansproject.app/kelola-a1b2c3d4e5f6/` |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Koneksi MariaDB |
| `MARIADB_BIN_DIR` | Folder program MariaDB, untuk backup (kosongkan = dicari otomatis) |
| `ADMIN_SESSION_MINUTES` | Admin otomatis keluar setelah sekian menit tidak aktif |
| `ADMIN_REQUIRE_2FA` | Kode Authenticator saat masuk panel. **Server produksi selalu wajib** (setelan ini diabaikan). Komputer pengembangan: bawaan `false` (cukup password); isi `true` untuk mencoba alur 2FA |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Kunci login Google untuk pelanggan (lihat bagian di bawah). Client Secret itu **rahasia** |
| `SERVER_PORT` | Port website di komputer ini. Bawaan **8432** |
| `STORE_BASE_DOMAIN` | Domain alamat toko kasir: `<nama>.hansproject.app`. Semua subdomain toko otomatis diizinkan. Di komputer pengembangan kosongkan (otomatis `localhost`) |
| `TESSERACT_CMD` | SIM: lokasi `tesseract.exe` untuk membaca teks foto KK/KTP. Kosongkan bila terpasang di `C:\Program Files\Tesseract-OCR\` |
| `TESSERACT_LANG` | Bahasa OCR, bawaan `ind+eng` (data bahasa yang belum terpasang otomatis dilewati) |
| `OCR_DEVICE` | Pembaca foto KK/KTP: `auto` (bawaan, GPU NVIDIA bila paket GPU terpasang) atau `cpu` |
| `TESSERACT_DATA_DIR` | Folder data bahasa OCR. Kosongkan: memakai `tools\tessdata` (diisi `pasang-ocr.bat`) |

Setelah mengubah `.env`, **jalankan ulang website** (stop lalu start, atau restart service).

**Pengaman otomatis:** di mode `production`, website **menolak berjalan** dan menampilkan pesan jelas bila setelannya berbahaya (DEBUG menyala, SECRET_KEY lemah, domain kosong, alamat panel mudah ditebak, user database `root`, dll.).

> Harga, paket, FAQ, username Instagram, dan isi website lainnya **tidak** diatur di `.env`, melainkan di panel pengelola.

### Login Google untuk pelanggan (Daftar / Masuk)

Pelanggan daftar & masuk **hanya dengan akun Google** (tanpa password baru). Google hanya memastikan identitas; **semua data pelanggan disimpan di database Anda sendiri** (tabel `hp_member*`). Gratis.

Cara membuat kuncinya (sekali saja), di <https://console.cloud.google.com>:
1. Buat project, misalnya “HANS Project”.
2. **Google Auth Platform → Branding**: nama aplikasi, email dukungan, halaman utama `https://hansproject.app`, Kebijakan Privasi `https://hansproject.app/kebijakan-privasi/`, Syarat & Ketentuan `https://hansproject.app/syarat-ketentuan/`, domain `hansproject.app`.
3. **Audience**: pilih *External*, lalu **Publish app** (selama masih *Testing*, hanya email penguji yang bisa masuk).
4. **Clients → Create client → Web application**. Isi **Authorized redirect URIs** dengan:
   - `https://hansproject.app/akun/google/callback/` (server)
   - `http://127.0.0.1:8432/akun/google/callback/` (komputer pengembangan)
5. Salin **Client ID** dan **Client Secret** ke `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`), lalu jalankan ulang website.

Penting:
- Alamat kembali dibuat dari `SITE_URL` + `/akun/google/callback/`, jadi `SITE_URL` harus **sama persis** dengan yang didaftarkan (termasuk `http`/`https` dan port). Di komputer pengembangan buka website lewat `http://127.0.0.1:8432` (bila dibuka lewat `localhost`, website otomatis pindah ke `127.0.0.1`).
- Google **tidak mengizinkan** alamat IP jaringan lokal (misalnya `192.168.x.x`), jadi login Google tidak bisa dicoba dari HP lewat Wi-Fi ke komputer pengembangan. Coba di browser komputer, atau nanti di server dengan domain asli.
- Bila kunci belum diisi, halaman masuk menampilkan “sedang disiapkan” dan website tetap berjalan normal.

### Persetujuan Syarat & Ketentuan dan Kebijakan Privasi

Setelah masuk dengan Google untuk **pertama kali**, pelanggan melihat **popup** berisi tautan ke Syarat & Ketentuan dan Kebijakan Privasi, plus satu kotak centang: *“Saya berusia minimal 18 tahun, menyetujui Syarat & Ketentuan, dan sudah membaca Kebijakan Privasi.”* Sebelum dicentang, semua halaman akun (termasuk dashboard toko) tertahan di popup ini. Pilihan lainnya hanya “Tidak setuju, keluar”.

- Setelah setuju, popup **tidak muncul lagi** untuk akun itu. Akun Google lain yang baru mendaftar akan melihatnya juga.
- Yang disimpan sebagai bukti: tanggal versi dokumen yang disetujui dan waktunya (kolom `terms_version`, `terms_accepted_at`).
- Bila isi S&K / Kebijakan Privasi Anda ubah **secara penting**, ubah juga **“versi Syarat & Ketentuan dan Kebijakan Privasi”** di **Pengaturan Umum**. Semua pelanggan akan diminta menyetujui ulang saat masuk berikutnya. Perubahan kecil (salah ketik) tidak perlu mengubah versi.
- Kotak centang sengaja dirumuskan sebagai **persetujuan S&K** + **pernyataan sudah membaca Kebijakan Privasi**, bukan “persetujuan pemrosesan data”. Data pelanggan diproses berdasarkan **pelaksanaan perjanjian** dan **kewajiban hukum** (UU PDP Pasal 20), sehingga tidak bergantung pada persetujuan yang digabung dengan S&K (yang dianggap ambigu oleh PP 33/2026).

---

## 4. Memakai panel pengelola

### Masuk pertama kali
1. Buka alamat panel (lihat `ADMIN_URL_PATH`). Alamat ini sengaja tidak mudah ditebak — **rahasiakan**.
2. Masuk dengan nama pengguna & password yang dibuat saat instalasi.
3. Anda **wajib mengaktifkan verifikasi dua langkah (2FA)**: pasang aplikasi *Google Authenticator*, *Microsoft Authenticator*, atau *Aegis* di HP, pindai kode QR yang tampil, lalu ketik kode 6 angkanya.
4. Setelah itu, setiap masuk butuh password **dan** kode dari HP.

### Yang bisa diubah

| Menu | Isi |
|---|---|
| **Beranda Panel** | Daftar hal yang masih perlu diisi, jumlah klik tombol DM Instagram, perubahan terakhir |
| **Paket & Harga** | Nama, harga, label sorotan, urutan, poin isi paket (versi sederhana + teknis), catatan penting |
| **Biaya Tambahan** | Tambah toko/cabang dan tambah tempat simpan |
| **Termasuk di Semua Paket** | Keunggulan semua paket kasir |
| **Tabel Detail Teknis** | Tabel perbandingan untuk pembaca yang paham teknologi |
| **Pertanyaan (FAQ)** | Tambah, ubah, hapus, geser urutan |
| **Testimoni** | Hanya untuk testimoni asli. Baru tampil bila diaktifkan di Pengaturan Umum |
| **Halaman Legal** | Syarat & Ketentuan dan Kebijakan Privasi (versi final 19 November 2026). Teks sumbernya juga ada di `apps/content/legal.py` |
| **Pesanan** | Pesanan dari tombol “Pesan Sekarang” dan perpanjangan: data pelanggan, foto bukti bayar, ubah status, dan **catatan untuk pelanggan** (tampil di halaman pesanannya). Pesanan kasir yang diubah menjadi **Aktif** otomatis membuat / memperpanjang toko |
| **Toko (Aplikasi Kasir)** | Semua toko pelanggan: nama, alamat (subdomain), aktif/nonaktif, plus data **langganannya** (paket, masa aktif, toko tambahan yang dibeli, tangguhkan, catatan untuk pemilik). Data langganan berlaku untuk semua toko di langganan itu. |
| **Refund** | Pengajuan pengembalian dana dari pesanan yang sudah dibayar lalu dibatalkan: rekening tujuan, nominal (bisa diubah untuk pengembalian sebagian), status, catatan, dan **bukti transfer** (wajib saat status *Sudah ditransfer*) |
| **Chat Pelanggan** | Obrolan dari menu **Chat** di akun pelanggan: balas dengan teks/gambar, balas pesan tertentu, dan **Tandai selesai & tutup obrolan**. Saringan *Perlu dibalas* menampilkan obrolan yang menunggu balasan |
| **Pengumuman Pelanggan** | Pengumuman di Dashboard akun pelanggan: judul, isi, jenis (Informasi/Penting/Promo), **jadwal mulai & berhenti**, dan saklar *aktif* untuk mematikan seketika. Pelanggan tidak bisa menutupnya. Bila tidak ada pengumuman aktif, ruangnya tidak tampil |
| **Daftar Pelanggan** | Akun yang masuk dengan Google. Bisa dinonaktifkan (diblokir) atau dihapus atas permintaan pelanggan |
| **Pengaturan Umum** | Username Instagram (untuk DM), email, jam kerja, media sosial, rekening & QRIS, judul utama, pengumuman, SEO, **versi S&K / Kebijakan Privasi** |
| **Keamanan Akun** | Ganti password, status 2FA |
| **Riwayat Perubahan** | Siapa mengubah apa dan kapan |

Tips:
- **Urutan**: pakai tombol panah ↑ ↓ di daftar.
- **Menyembunyikan** tanpa menghapus: matikan saklar “Tampilkan”.
- **Alur pesanan paket kasir**: pelanggan tekan **Pesan Sekarang** → masuk dengan Google (sekali isi nomor HP & nama usaha) → konfirmasi → lihat cara bayar → kirim foto bukti bayar → status “Bukti bayar sedang dicek”. Anda cek di menu **Pesanan**, lalu ubah status menjadi **Aktif** (misalnya sambil menulis link aplikasi di catatan). Status yang tersedia: Menunggu pembayaran, Bukti bayar sedang dicek, Menunggu konsultasi, Sedang diproses, Aktif, Selesai, Dibatalkan.
- **Paket Rimba** (jasa): pesanan langsung berstatus **Menunggu konsultasi** (tanpa langkah bayar). Hubungi pelanggan lewat nomor HP di data pesanannya.
- **Info rekening & QRIS** di halaman pesanan hanya tampil bila “tampilkan info rekening” di Pengaturan Umum dinyalakan. Bila mati, pelanggan diminta menunggu info pembayaran di **catatan untuk pelanggan** pada pesanannya.
- **Kontak**: semua keperluan lewat **DM Instagram @hansproject.app** (username diatur di Pengaturan Umum). Pelanggan yang sudah masuk juga bisa memakai menu **Chat** (tombol “Tanya Kami” di website membuka chat baru).
- **Istilah teknis** tampil secara bawaan. Pengunjung bisa menyembunyikannya lewat saklar “Tampilkan istilah teknis”.
- **Judul utama**: kata `{harga_mulai}` otomatis menjadi harga paket kasir termurah (misalnya “Rp25 ribu”).
- **Format teks** di FAQ & halaman legal: `**tebal**`, baris diawali `- ` untuk daftar, `## Judul` untuk sub-judul, `[teks](https://...)` untuk tautan. HTML tidak diizinkan (demi keamanan).
- **Gambar QRIS**: JPG/PNG/WebP, maksimal 3 MB. Gambar otomatis diproses ulang dan data tersembunyi (EXIF) dibuang.
- Perubahan langsung tampil di website (cache otomatis diperbarui).

### Area akun pelanggan

Setelah masuk, pelanggan berada di **area akun** dengan menu sendiri: menu atas di layar lebar, menu bawah di HP. Tombol di header berubah menjadi **Beranda** untuk kembali ke website. Di website, tombol **Profil** (atau **Daftar / Masuk**) ada di header, juga di HP; menu bawah website berisi Beranda · Solusi · Harga · Cara mulai · Bantuan.

**Website = penyedia solusi digital.** Halaman utama sengaja ringkas: pembuka, kartu **Solusi** (Aplikasi Kasir, Sistem Informasi Manajemen/SIM, Website & Aplikasi, Tiket Online *segera hadir*), **Harga** dengan tab per solusi (Kasir & SIM masing-masing Paket Tunas & Tumbuh; Rimba disebut singkat), Cara mulai, FAQ umum, dan ajakan. Penjelasan lengkap ada di halaman tiap solusi: `/aplikasi-kasir/` (fitur, halaman promosi toko, harga + tambahan + kalkulator, tabel teknis, FAQ kasir), `/sistem-informasi-manajemen/` (bidang SIM, fitur, harga, tabel teknis, FAQ SIM), dan `/website-aplikasi/` (Paket Rimba). FAQ di panel diberi **Tampil di**: Umum (halaman utama) atau salah satu solusi. Paket berlangganan berharga **Rp0** tampil *Segera diumumkan* dengan tombol *Tanya harga* dan belum bisa dipesan.

| Menu akun | Isi |
|---|---|
| **Dashboard** (halaman pertama) | Pengumuman dari panel (bila ada), hal yang perlu perhatian (balasan chat baru, surat warga menunggu, masa aktif kasir/SIM hampir habis, belum ada akun kasir, pesanan & refund berjalan), lalu ringkasan **setiap layanan** yang dimiliki (Kasir: penjualan hari ini & bulan ini; SIM: surat menunggu & instansi; Website & Aplikasi: proyek berjalan). Belum punya layanan = pilihan semua solusi |
| **Pesanan** | Pesanan berjalan, riwayat, dan status **refund** |
| **Layanan** (tombol tengah) | Semua solusi milik pelanggan di satu tempat: **Aplikasi Kasir** (→ Toko saya: grafik 14 hari, terlaris, transaksi terbaru, toko per langganan), **SIM** (→ Instansi saya), **Website & Aplikasi** (proyek), pesanan yang sedang diproses, dan Tiket Online (segera). Solusi baru cukup ditambah di sini, tidak menambah tombol menu |
| **Chat** | (Pesanan jasa seperti Paket Rimba otomatis punya **obrolan konsultasi** yang terikat ke pesanannya: tombol *Buka obrolan konsultasi* di halaman pesanan; obrolan yang sama muncul di Chat Pelanggan panel dengan kode pesanannya, dan tidak dihitung batas 3 obrolan aktif.) Obrolan dengan HANS Project: gelembung pesan, kirim teks/gambar, balas pesan tertentu. Obrolan yang ditutup admin menjadi **Selesai** (tidak bisa dibalas, tetap ada di riwayat); keperluan baru = obrolan baru. Maksimal 3 obrolan aktif |
| **Akun** | Data diri, keluar (juga dari semua perangkat), dan waktu persetujuan S&K |

**Toko & langganan:** **1 toko = 1 subdomain = 1 akun kasir.** Setiap toko punya alamat kasir sendiri (`<nama>.hansproject.app/kasir`), barang & kategori, transaksi, laporan, dan pengaturan struk sendiri; toko-toko tidak berbagi data. Akun kasir (nama pengguna + PIN dari pemilik) boleh masuk di **banyak perangkat sekaligus**; pemilik bisa melihat jumlah perangkat yang masuk dan mengeluarkan semuanya. Satu **langganan** (satu pesanan paket) berisi beberapa toko sesuai paket (Tunas 2, Tumbuh 10) ditambah toko tambahan yang dibeli; masa aktif & perpanjangan berlaku untuk semua toko di langganan itu.

**Halaman toko:** setiap toko punya halaman promosi di `<nama>.hansproject.app/` yang diatur pemilik di menu **Halaman toko**: pilih **1 dari 4 template** (Sederhana, Etalase, Menu Kafe, Berani), pilih **satu warna** (palet lengkap untuk latar, tombol, tulisan, label, dan bagian gelap diracik otomatis di server dengan kontras WCAG; pemilik tidak melihatnya), isi kalimat singkat, tentang toko, jam buka, telepon, Instagram, link Google Maps, logo & foto sampul, daftar harga (opsional), dan **barang unggulan** (maks. 6, dari data barang atau gambar lain). Semua perubahan adalah **draf**: pemilik melihat **pratinjau** (bisa mencoba template lain dan tampilan HP) lalu menekan **Terbitkan**. Pengunjung hanya melihat versi terbit; halaman terbit boleh muncul di Google, halaman kasir tidak. Halaman tidak tampil saat toko nonaktif/terkunci/ditangguhkan.

**Langkah memulai toko:** panduan 4 langkah (isi barang → buat akun kasir → buka kasir di HP/laptop → terbitkan halaman toko) tampil di atas menu tab di **semua** menu toko, dengan tombol langkah berikutnya, dan hilang sendiri setelah semuanya selesai.

**Tambah toko:** menu **Toko** menampilkan toko per langganan beserta jumlahnya, misalnya **1 / 3** (Paket Tunas 2 + tambahan 1). Tombol **Tambah toko** membuka halaman khusus: bila kuota masih ada, pelanggan langsung membuat toko baru (nama, **alamat kasir/subdomain baru** yang langsung aktif, dan akun kasirnya). Toko bisa **dinonaktifkan** di Pengaturan untuk membebaskan kuota (data tetap ada); bila penuh, pelanggan bisa **membeli toko tambahan** (harga dari Biaya Tambahan → Tambah toko/cabang) atau naik paket. Pembelian toko tambahan menjadi pesanan jenis *Tambahan toko*; saat Anda ubah menjadi **Aktif**, kuota langsung bertambah. Toko tambahan ikut dihitung di setiap perpanjangan (contoh: Tunas + 2 toko = Rp25.000 + 2 × Rp15.000 = Rp55.000/bulan). Tombol **Pesan layanan** di akun membuka pemesanan dua langkah: pilih solusi (Kasir, SIM, Website & Aplikasi), lalu pilih paketnya.

**Rincian harga per pesanan:** di panel → Pesanan → ubah, bagian **Rincian harga**, Anda bisa mengetik baris harga sendiri berisi nama, harga, periode (diketik bebas, mis. "1 tahun", "3 bulan", "14 hari"; kosongkan bila sekali bayar), dan keterangan. Contoh: Pembuatan website Rp349.000 (periode kosong), Domain Rp250.000 / 1 tahun, Database Rp150.000 / 3 bulan. Bila diisi, rincian ini menggantikan teks harga paket di halaman pesanan pelanggan, dan **Total Semua** (nominal yang dibayar & dasar refund) = jumlah semua baris. Cocok untuk Paket Rimba: setelah konsultasi, isi rincian lalu ubah status menjadi *Menunggu pembayaran*.

**Bukti pesanan & QR keaslian:** baru muncul (dan bisa dicetak) setelah pembayaran Anda cek dan status pesanan diubah ke **Sedang diproses**, **Aktif**, atau **Selesai**. Setiap pesanan punya kode QR menuju halaman publik `/cek/<kode-acak>/` (sebelum dicek: tidak ditemukan; bila pesanan dibatalkan: tertulis *tidak berlaku lagi*) yang menampilkan kode, layanan, status, tanggal, rincian harga, dan nama pemesan yang disamarkan (tidak diindeks Google). Tombol **Cetak** di halaman pesanan mencetak bukti pesanan rapi (tanpa menu & tombol) memakai fitur cetak bawaan browser.

**Refund:** pelanggan bisa membatalkan pesanan yang **sudah dibayar tetapi belum aktif**; Anda juga bisa membatalkan pesanan apa pun di panel (misalnya karena kesalahan kita). Pesanan yang sudah dibayar lalu dibatalkan menampilkan formulir **Ajukan refund** (rekening atas nama pelanggan). Proses di menu **Refund**: transfer, unggah bukti, ubah status. Nominal awal = harga saat dipesan; ubah bila pengembalian sebagian (per hari).

### Aplikasi kasir (toko pelanggan)

Satu aplikasi melayani semua toko, di port yang sama (8432). Toko dikenali dari alamatnya, bukan dari port.

| Alamat | Untuk siapa | Isi |
|---|---|---|
| `hansproject.app/akun/toko/<nama>/` | **Pemilik toko** (login Google) | Ringkasan, Barang & kategori, Kasir (akun & perangkat yang masuk), Halaman toko (template, warna, barang unggulan, pratinjau, terbitkan), Transaksi (batalkan transaksi), Laporan (unduh CSV/Excel), Pengaturan struk & status toko, Perpanjang |
| `<nama>.hansproject.app/kasir/` | **Kasir** (nama pengguna + PIN 6 angka buatan pemilik) | Layar kasir, cetak struk, riwayat hari ini |
| `<nama>.hansproject.app/` | Umum | **Halaman toko** yang diterbitkan pemilik (boleh muncul di Google); sebelum terbit: “segera hadir” (tidak diindeks) |

**Alur:**
1. Pelanggan memesan Paket Tunas/Tumbuh dan memilih **alamat toko** (3–30 huruf kecil/angka/minus; nama seperti `www`, `admin`, `kasir` ditolak; nama yang sedang dipesan orang lain juga dikunci).
2. Setelah bukti bayar dicek, ubah status pesanan menjadi **Aktif** → langganan + toko pertama otomatis dibuat (alamat sesuai pesanan, aktif 1 bulan, kuota toko sesuai paket). Toko berikutnya dibuat pelanggan sendiri dari sisa kuota.
3. Pemilik membuat barang dan akun kasir di dashboard tokonya, lalu kasir masuk di `<nama>.hansproject.app/kasir/`.
4. **Perpanjang**: pemilik menekan *Perpanjang* di dashboard toko → pesanan perpanjangan (bisa **pindah paket** dan **minta ganti alamat**). Saat Anda mengubahnya menjadi **Aktif**, masa aktif bertambah 1 bulan (dari tanggal habis, atau dari hari ini bila sudah lewat). Ganti alamat hanya terjadi bila Anda mencentang **“Setujui ganti alamat toko”**. Perpanjangan berlaku untuk **semua toko** di langganan itu; ganti alamat hanya untuk toko tempat perpanjangan dibuat. Turun paket: toko terbaru di atas batas dinonaktifkan (datanya tetap).

**Masa aktif habis:**
- 7 hari pertama: **masa tenggang**, kasir tetap jalan dengan peringatan.
- Setelah itu kasir **terkunci**; pemilik masih bisa melihat & mengunduh laporan.
- **30 hari setelah masa aktif habis, data toko dihapus permanen** (dijalankan otomatis setiap malam oleh backup terjadwal, lihat bagian 8). Bila diperpanjang sebelum itu, semua data kembali seperti semula. Perpanjangan yang bukti bayarnya sedang Anda cek tidak ikut dihapus.

**Lainnya:**
- Toko tambahan yang dibeli pelanggan bertambah otomatis saat pesanan *Tambahan toko* diaktifkan; bisa juga diubah manual (**toko tambahan (dibeli)**) di menu Toko.
- Uang disimpan dalam rupiah bulat. Harga & total selalu dihitung ulang di server; tombol Bayar yang terkirim dua kali (internet lambat) tetap tercatat satu transaksi.
- Struk dicetak dengan fitur cetak bawaan browser (HP maupun komputer), kertas 58 mm atau 80 mm (diatur pemilik toko).
- Cara bayar di kasir (Tunai/QRIS/Transfer) hanya dicatat, tidak tersambung ke bank.
- Komputer pengembangan: buka toko di `http://<nama>.localhost:8432/kasir/` (Chrome/Edge/Firefox langsung mengenali `*.localhost`).

Rincian rancangan: `docs/06-aplikasi-kasir.md`.

### Sistem Informasi Manajemen / SIM (bidang pertama: RT, RW, Kelurahan/Desa, Kecamatan)

SIM adalah solusi umum untuk instansi dan organisasi; bidang lain (kesehatan, pendidikan, organisasi) disiapkan menyusul. Di akun pelanggan satu unit disebut **instansi** (di kode: model `Wilayah`).

| Alamat | Untuk siapa | Isi |
|---|---|---|
| `hansproject.app/akun/sim/<kode>/` | **Pengurus wilayah** (login Google) | Ringkasan & cari warga, Data warga (KK & anggota mengikuti format KK Dukcapil, unduh CSV; tombol **Scan KK/KTP** di dalamnya: foto → formulir KK + anggota terisi otomatis), Surat (masuk, buat, terbitkan, cetak, hapus), Format surat (ubah isi & kolom), Pengumuman, Jaringan (gabung ke RW/kelurahan, terima RT, surat “diketahui”), Pengaturan kop surat, Perpanjang |
| `hansproject.app/w/<kode>/` | **Warga** (tanpa login) | Pengumuman, ajukan surat online, lacak surat |
| `hansproject.app/surat/lacak/<kode-lacak>/` | Warga pemohon | Status surat; cetak sendiri bila pengurus mengizinkan |
| `hansproject.app/surat/cek/<kode>/` | Siapa saja (dari QR di surat) | Cek keaslian surat (nama tersamar) |

**Paket:** sama seperti kasir, SIM punya **Paket Tunas** (cocok RT/RW, baca otomatis 100 dokumen/bulan, 1 GB) dan **Paket Tumbuh** (kelurahan/kecamatan, 1.000 dokumen/bulan, 5 GB, rekap unit di bawahnya, support prioritas). Keduanya sudah tampil di website dengan harga **Rp0 = "Segera diumumkan"** (belum bisa dipesan, tombolnya *Tanya harga*). Isi harganya di panel (*Paket & Harga*); setelah itu langsung bisa dipesan. Batas baca otomatis per bulan diatur di kolom **batas scan dokumen per bulan** pada paket dan benar-benar diterapkan di menu Scan.

**Alur:** pengurus memesan paket SIM dan mengisi data instansinya → setelah bukti bayar dicek, ubah pesanan menjadi **Aktif** → wilayah + 12 format surat bawaan otomatis dibuat (kelurahan/kecamatan juga mendapat format ahli waris). Masa aktif, tenggang 7 hari, terkunci, dan penghapusan 30 hari **sama seperti aplikasi kasir**. Saat terkunci, pengajuan surat online ditutup.

**Membaca foto KK/KTP (OCR):** berjalan di server sendiri (foto tidak dikirim ke pihak lain). Memakai **GPU NVIDIA** bila ada (lebih cepat), selain itu CPU.
- Mesin utama: **PaddleOCR PP-OCRv4** (model deep learning, lewat RapidOCR + ONNX Runtime) dengan **OpenCV**: kuat untuk foto HP (fotokopi, cahaya tidak rata, miring/perspektif, foto diputar 90° atau terbalik). Model ikut di dalam paket.
- Cadangan & pemeriksa spasi antarkata: **Tesseract** (bila hasil PaddleOCR kurang lengkap, misalnya hasil scan beresolusi kecil, hasil yang paling lengkap yang dipakai).

1. Jalankan **`pasang-ocr.bat`** (sekali saja): memasang paket `requirements\ocr.txt` (dikunci versi & sidik SHA-256; bila ada kartu NVIDIA otomatis `ocr-gpu.txt` = ONNX Runtime GPU + CUDA 12 + cuDNN sebagai paket pip, tanpa CUDA Toolkit, unduhan ±1,5 GB, butuh driver NVIDIA 528+; bila GPU tidak bisa dipakai, otomatis kembali ke CPU), Tesseract lewat winget, dan data bahasa Indonesia ke `tools\tessdata` (juga diperiksa sidiknya). Lalu jalankan ulang website.
2. Bila Tesseract dipasang di tempat lain, isi `TESSERACT_CMD` di `.env`.
3. `update.bat` ikut memperbarui paket pembaca foto bila sudah terpasang. Tanpa mesin pembaca, foto tetap tersimpan dan formulir diisi manual sambil melihat gambarnya.

KK dibaca mengikuti **struktur tabel KK Dukcapil** (sudut tabel dicari, perspektif diluruskan, garis baris & kolom dideteksi, setiap teks dipasangkan ke selnya; sel penting yang kosong dibaca ulang) dan hasilnya **langsung mengisi formulir KK beserta semua anggota** (biasanya 7–15 detik). Pengurus mencocokkan dengan gambar di sebelahnya, membetulkan bila perlu, lalu menekan Simpan; data tidak pernah tersimpan tanpa diperiksa. Nama kepala keluarga tidak diketik: otomatis dari anggota yang hubungannya *Kepala Keluarga*. Hasil terbaik: foto seluruh lembar KK, terang dan tajam (boleh tegak atau mendatar). Hanya satu dokumen dibaca pada satu waktu supaya server tetap ringan.

**Privasi:** data warga hanya bisa dibuka pengurus wilayah itu sendiri. Wilayah di atasnya (RW/kelurahan/kecamatan) hanya melihat **angka rekap** dan surat yang dikirim untuk “diketahui”. Panel pengelola juga **tidak** menampilkan data warga. Foto KK/KTP, tanda tangan, dan cap disimpan di folder pribadi tanpa alamat publik.

Rincian rancangan: `docs/07-sim-wilayah.md`.

### Lupa password / HP hilang
- Ganti password: jalankan `buat-admin.bat` di server, ketik nama pengguna yang sama.
- HP Authenticator hilang: jalankan `reset-2fa.bat` di server. Saat masuk berikutnya Anda diminta memindai QR baru.

---

## 5. Memindahkan ke server Windows (langkah demi langkah)

### A. Siapkan server
1. Pasang **Python 3.12+** dari python.org. Saat instalasi:
   - centang **Add python.exe to PATH**,
   - pilih **Customize installation → Install for all users** (penting: Windows Service tidak bisa membaca Python yang terpasang di folder pengguna).
2. Pastikan **MariaDB** berjalan di port **3307**. Disarankan di `my.ini` MariaDB: `bind-address=127.0.0.1`.
3. Arahkan DNS `hansproject.app` dan `www.hansproject.app` ke IP server.

### B. Salin file proyek
Salin seluruh folder proyek ke server, misalnya `C:\hansproject` (path dengan spasi juga boleh), **kecuali**:
`.venv`, `.env`, `staticfiles`, `logs`, `run`, `tools`, `__pycache__`.
`.venv` dan `.env` dibuat ulang di server.

### C. Pindahkan data (bila sudah ada perubahan di komputer pengembangan)
1. Di komputer pengembangan: jalankan `backup.bat`. File muncul di folder `backups\`.
2. Salin file `hansproject-....sql.gz` itu ke folder `backups\` di server.
3. Lanjutkan langkah D. Setelah instalasi selesai, jalankan `restore.bat` dan ketik nama file tersebut.
4. Gambar upload (QRIS, foto testimoni): salin folder `media\`. Foto bukti bayar pelanggan: salin folder `private\`.

### D. Instalasi di server
1. Klik dua kali **`install.bat`**. Ikuti pertanyaannya:
   - Database: pilih **[1]** untuk membuat database + user khusus otomatis (diminta password root MariaDB satu kali), atau **[2]** bila user database sudah disiapkan.
   - Database yang sudah berisi tabel/data lain **aman**: semua tabel website memakai awalan `hp_` dan tidak ada yang dihapus.
   - Buat akun admin (password minimal 12 karakter).
2. Catat **alamat panel** yang tampil di akhir.
3. Coba jalankan `start.bat`, lalu di browser server buka <http://127.0.0.1:8432/sehat/> — harus tampil `ok`. Tutup jendela start.bat bila sudah.

### E. Jalankan otomatis & HTTPS
1. Siapkan Caddy (bagian 6).
2. Klik kanan **`service-install.bat` → Run as administrator**. Website (dan Caddy, bila ada) dipasang sebagai Windows Service yang otomatis jalan saat server dinyalakan ulang.
3. Klik kanan **`backup-jadwal.bat` → Run as administrator** untuk backup database otomatis setiap hari.

### F. Cek hasil
- Buka `https://hansproject.app` → halaman tampil, gembok HTTPS ada.
- Buka `services.msc` → service **HANS Project - Website** dan **HANS Project - Caddy (HTTPS)** berstatus *Running*.
- Masuk panel, aktifkan 2FA, lalu isi data yang masih contoh (lihat “Perlu diisi” di Beranda Panel).
- Cek header keamanan di <https://securityheaders.com> (opsional).

---

## 6. HTTPS dengan Caddy

Domain `.app` **wajib HTTPS**. Caddy mengurus sertifikat Let's Encrypt secara otomatis.

1. Unduh Caddy untuk Windows (amd64) dari <https://caddyserver.com/download>.
2. Simpan sebagai `tools\caddy\caddy.exe` di folder proyek.
3. Salin `deploy\caddy\Caddyfile.example` menjadi `deploy\caddy\Caddyfile` (atau biarkan, `service-install.bat` menyalinnya otomatis). Isi email Anda di baris `email` (opsional).
4. Pastikan port **80** dan **443** terbuka ke internet dan DNS sudah mengarah ke server. Di **Hostinger** (Domain → DNS), buat record **A** untuk `@`, `www`, **dan `*`** (bintang = semua alamat toko) ke IP publik server.
5. Jalankan `service-install.bat` (Run as administrator).

**Alamat toko** (`*.hansproject.app`): Caddy membuat sertifikat HTTPS per toko saat alamatnya **pertama kali dibuka** (*On-Demand TLS*), memakai `caddy.exe` biasa tanpa plugin dan tanpa API key Hostinger. Sebelum membuat sertifikat, Caddy bertanya ke website (`http://127.0.0.1:8432/_tls/izin/`) apakah toko itu ada; alamat ngawur ditolak. Let's Encrypt membatasi sekitar 50 sertifikat baru per minggu untuk satu domain, cukup untuk ±50 toko baru per minggu. Bila `SERVER_PORT` diubah, ubah juga port di baris `ask` Caddyfile.

Website (Waitress) hanya mendengarkan di `127.0.0.1:8432`. Hanya Caddy di server yang sama yang dipercaya untuk header `X-Forwarded-For`/`X-Forwarded-Proto` (`TRUSTED_PROXY=127.0.0.1`), jadi pengunjung tidak bisa memalsukannya.

> Memakai IIS atau nginx? Bisa juga: arahkan reverse proxy ke `http://127.0.0.1:8432`, kirim header `X-Forwarded-Proto` dan `X-Forwarded-For`, dan pastikan HTTPS aktif.

---

## 7. Mengamankan server Windows

**Akun service berhak terbatas.** `service-install.bat` menjalankan website dengan akun virtual Windows `NT SERVICE\hansproject-web` (bukan Administrator, tanpa password) dan mengatur izin folder:

| Folder/file | Izin |
|---|---|
| Folder proyek | Akun service: baca saja |
| `logs`, `run`, `media`, `staticfiles` | Akun service: baca & tulis |
| `media`, `private` | Akun service: tidak boleh menjalankan file |
| `private` (bukti bayar) | Hanya akun service, Administrator, SYSTEM |
| `.env` | Hanya akun service (baca), Administrator, SYSTEM |
| `backups` | Hanya Administrator & SYSTEM |

Bila perlu mengatur manual (Command Prompt sebagai Administrator, dari folder proyek):

```bat
icacls .env /inheritance:r /grant:r "NT SERVICE\hansproject-web:R" *S-1-5-32-544:F *S-1-5-18:F
icacls backups /inheritance:r /grant:r *S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F
```
(`*S-1-5-32-544` = grup Administrators, `*S-1-5-18` = SYSTEM; berlaku di Windows bahasa apa pun.)

**Firewall** — hanya port 80 dan 443 yang terbuka ke publik (Command Prompt sebagai Administrator):

```bat
netsh advfirewall firewall add rule name="HANS HTTP" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="HANS HTTPS" dir=in action=allow protocol=TCP localport=443
netsh advfirewall firewall add rule name="Blok MariaDB dari luar" dir=in action=block protocol=TCP localport=3307
netsh advfirewall firewall add rule name="Blok Waitress dari luar" dir=in action=block protocol=TCP localport=8432
```
Koneksi dari server itu sendiri (127.0.0.1) tidak terpengaruh aturan blokir ini. Tambahkan juga `bind-address=127.0.0.1` di `my.ini` MariaDB.

Lainnya:
- Pakai password Administrator Windows yang kuat dan aktifkan Windows Update.
- Jangan pernah membagikan file `.env` atau isi folder `backups`.
- Bila mengaktifkan log akses di Caddy (berisi IP pengunjung), perbarui Kebijakan Privasi.

---

## 8. Backup, restore, dan pembaruan

- **`backup.bat`** — backup tabel website (`hp_*`) ke `backups\hansproject-TANGGAL-JAM.sql.gz`. Backup lama otomatis dihapus (`BACKUP_KEEP` file terbaru disimpan, dan yang lebih tua dari `BACKUP_MAX_DAYS` hari dihapus). Password database tidak pernah tampil di layar atau di daftar proses.
- **`backup-jadwal.bat`** — backup otomatis setiap hari (Task Scheduler). Setelah backup berhasil, `backup.bat` juga menjalankan `bersihkan_data`, yaitu menghapus permanen data yang sudah lewat masa simpan menurut Kebijakan Privasi: toko kasir yang tidak diperpanjang lebih dari 30 hari, pesanan & bukti bayar yang lebih tua dari 10 tahun, dan sesi login kedaluwarsa. Salinan di file backup ikut hilang sendiri saat backup lama dirotasi (paling lama `BACKUP_MAX_DAYS` = 60 hari).
- **Menghapus akun pelanggan** (atas permintaannya) di menu Daftar Pelanggan: akun, obrolan chat, pesanan yang belum dibayar, dan tokonya ikut terhapus. Pesanan yang **sudah dibayar** (termasuk yang dibatalkan lalu di-refund) beserta bukti bayar dan data refund-nya tetap disimpan 10 tahun untuk catatan pajak (UU KUP Pasal 28 ayat 11), dengan nama, email, HP, dan nama usaha pemesan disalin ke pesanan.
- **`restore.bat`** — mengembalikan dari file backup. Ada konfirmasi (ketik `YA`), dan kondisi sekarang otomatis di-backup dulu. Hanya tabel `hp_*` yang ditimpa; file backup yang mencoba menyentuh tabel lain **ditolak**.
- **Foto bukti bayar** (folder `private`) tidak ikut `backup.bat` (yang hanya berisi database). Salin folder `private` secara berkala ke tempat aman bila perlu.
- **`update.bat`** — untuk versi baru: salin file proyek baru (jangan timpa `.env`, `media`, `private`, `backups`), lalu jalankan. Urutannya: **backup dulu** → hentikan website → pasang dependensi → migrasi → file statis → cek keamanan → nyalakan lagi.

---

## 9. Daftar file .bat

| File | Fungsi | Perlu Administrator? |
|---|---|---|
| `install.bat` | Instalasi/perbaikan di server (aman diulang) | Tidak |
| `start.bat` | Menjalankan website (atau menyalakan service) | Tidak* |
| `stop.bat` | Menghentikan website | Tidak* |
| `update.bat` | Pembaruan versi (selalu backup dulu) | Tidak* |
| `backup.bat` | Backup database sekarang | Tidak |
| `restore.bat` | Kembalikan database dari backup | Tidak* |
| `backup-jadwal.bat` | Jadwal backup harian | Ya |
| `service-install.bat` | Pasang Windows Service (website + Caddy) | Ya |
| `service-uninstall.bat` | Lepas Windows Service (data tidak dihapus) | Ya |
| `buat-admin.bat` | Buat admin baru / ganti password | Tidak |
| `reset-2fa.bat` | Reset 2FA admin (HP hilang) | Tidak |
| `setup-dev.bat`, `run-dev.bat` | Komputer pengembangan | Tidak |
| `test.bat`, `cek-keamanan.bat` | Tes otomatis & pemeriksaan keamanan | Tidak |

\* Perlu Administrator bila website dipasang sebagai Windows Service.

Semua file batch: pesan berbahasa Indonesia, berhenti dengan pesan jelas bila ada error, jendela tidak langsung tertutup, aman di folder yang namanya mengandung spasi.

---

## 10. Memeriksa & memperbarui dependensi

Semua versi dikunci beserta **hash**-nya di `requirements\base.txt` (produksi) dan `requirements\dev.txt` (pengembangan), sehingga paket yang dipasang tidak bisa diganti diam-diam.

Disarankan **setiap bulan** di komputer pengembangan:
1. `cek-keamanan.bat` — menjalankan `pip-audit` (celah keamanan dependensi), `bandit` (analisis kode), dan `check --deploy`.
2. Untuk memperbarui:
   ```bat
   .venv\Scripts\pip-compile --upgrade --generate-hashes --allow-unsafe --strip-extras requirements\base.in -o requirements\base.txt
   .venv\Scripts\pip-compile --upgrade --generate-hashes --allow-unsafe --strip-extras requirements\dev.in -o requirements\dev.txt
   ```
   lalu `setup-dev.bat`, `test.bat`, dan bila lulus, bawa ke server dengan `update.bat`.
3. Django 5.2 adalah versi LTS (didukung sampai April 2028). Sebelum itu, rencanakan naik ke LTS berikutnya.

---

## 11. Masalah yang sering terjadi

| Gejala | Penyelesaian |
|---|---|
| “Mode produksi DITOLAK berjalan…” | Baca daftar masalahnya, perbaiki di `.env`. |
| “Tidak bisa terhubung ke database” | Cek MariaDB menyala, `DB_PORT` benar (3307), user & password di `.env`. Jalankan `install.bat` lagi dan pilih [1]. |
| Website tampil tanpa tampilan (CSS hilang) | Jalankan `update.bat` atau `.venv\Scripts\python manage.py collectstatic --noinput`. |
| “Terlalu banyak percobaan gagal” saat login | Tunggu 15 menit (pengaman otomatis). |
| Kode 2FA selalu salah | Pastikan jam & zona waktu HP dan server benar (otomatis). |
| Google menampilkan “redirect_uri_mismatch” | Alamat di **Authorized redirect URIs** belum sama persis dengan `SITE_URL` + `/akun/google/callback/`. Cek `http`/`https`, port, dan garis miring di akhir. |
| Masuk dengan Google “sedang gagal” | Lihat `logs\security.log`. Biasanya Client Secret salah, atau jam server tidak tepat. |
| `mariadb-dump` tidak ditemukan saat backup | Isi `MARIADB_BIN_DIR` di `.env`, contoh `C:\Program Files\MariaDB 11.4\bin`. |
| Alamat toko (`nama.hansproject.app`) tidak bisa dibuka / sertifikat gagal | Cek record DNS `*` di Hostinger, port 443 terbuka, dan tokonya memang ada & belum dihapus (lihat menu Toko). Lihat log Caddy. |
| Kasir “Nama pengguna atau PIN salah” terus | Pemilik toko membuat PIN baru di menu **Kasir** tokonya. Setelah 5 kali salah, akun kasir terkunci 15 menit. |
| Service tidak mau jalan | Lihat `logs\service\` dan `logs\app.log`. Pastikan Python terpasang “for all users”. |

Log aplikasi: `logs\app.log` (umum) dan `logs\security.log` (login & perubahan di panel), dengan rotasi otomatis (maks. 5 MB × 10 file). Password dan token tidak pernah dicatat.

---

## 12. Untuk programmer

**Arsitektur singkat**
- `apps/core/dbprefix.py` — semua tabel (termasuk `auth_*`, `django_session`, `django_migrations`) otomatis berawalan `hp_`, supaya aman berbagi database dengan aplikasi lain. **Jangan ubah `DB_TABLE_PREFIX` setelah migrasi pertama.**
- `apps/content/services.py` — seluruh konten dibaca sekali menjadi `Snapshot` dan di-cache; halaman publik juga di-cache sebagai HTML. Cache dihapus otomatis oleh `signals.py` saat data berubah.
- `apps/panel/crud.py` + `registry.py` — CRUD generik. Menambah jenis data baru cukup: buat model + `ModelForm`, lalu daftarkan satu `Section(...)` di `registry.py`. Daftar, tambah, ubah, hapus, geser urutan, formset, dan riwayat perubahan otomatis tersedia.
- `apps/core/textformat.py` — format teks sederhana yang aman (escape + allowlist `nh3`).
- `apps/core/images.py` — validasi & re-encode upload gambar.
- `apps/members/` — akun pelanggan, **terpisah** dari akun admin. `google.py`: OpenID Connect (authorization code + PKCE, state, nonce) tanpa library tambahan. `auth.py`: sesi pelanggan (cookie `hp_akun` berisi token acak, database hanya menyimpan hash SHA-256). Halaman publik tetap di-cache sama untuk semua orang; tombol “Daftar / Masuk” ditukar menjadi “Profil” oleh `site.js` lewat cookie penanda `hp_masuk=1` (tanpa rahasia). Bukti bayar disimpan di `PRIVATE_MEDIA_ROOT` tanpa alamat publik.
- `apps/members/chat.py`, `navigation.py`, `charts.py` — logika chat (dipakai akun & panel), menu area akun (dengan jumlah chat belum dibaca), dan geometri grafik SVG Dashboard (tanpa style inline karena CSP ketat). `static/js/chat.js` mengirim pesan tanpa memuat ulang dan mengambil pesan baru berkala (8 detik, hanya saat tab terlihat); tanpa JavaScript chat tetap jalan sebagai formulir biasa.
- `apps/pos/` — aplikasi kasir. `middleware.py`: `StoreHostMiddleware` memilih URL toko (`urls_store.py`) bila alamatnya `<nama>.STORE_BASE_DOMAIN`, sehingga panel & `/akun/` tidak ada di subdomain; `TlsAskMiddleware` menjawab Caddy. `services.py` berisi aturan bisnis (aktivasi, transaksi, laporan, penghapusan). Semua data disaring per toko lewat relasi `store.*`. Kasir punya sesi sendiri (`cashier_auth.py`, cookie `hp_kasir` tanpa atribut Domain, PIN Argon2).
- `apps/sim/` — SIM. `models.py`: `Wilayah` (unit + langganan + kode halaman warga + kode undangan + `parent`), `KartuKeluarga`, `Penduduk`, `DokumenScan`, `JenisSurat`, `Surat`, `Pengumuman` (tabel `hp_sim_*`). Pengurus mengambil wilayah lewat `Wilayah.objects.owned_by(member)` di `views_owner.wilayah_view`, lalu semua data lewat relasi wilayah. `views_public.py`: halaman warga tanpa login (kode lacak 24 karakter acak, rate limit per IP-hash, honeypot). `ocr.py`: Tesseract lewat `subprocess` (argumen list, tanpa shell, batas waktu, 1 proses sekaligus) + parser draf KK/KTP. `services.py`: aktivasi, nomor surat (dikunci `select_for_update`), isi surat (`{isian}` diisi lewat `templating.fill`, bukan `str.format`), jaringan, statistik, penghapusan. `printing.py` + `templates/sim/cetak.html` + `static/css/surat.css`: cetak A4 dari browser dengan QR keaslian.
- Template memakai komponen di `templates/components/` dan tag `{% icon %}`, filter `|rupiah`, `|rupiah_short`, `|md` (dimuat otomatis).
- CSS: `static/css/base.css` (token desain + komponen bersama), `site.css` (situs), `panel.css` (panel), `akun.css` + `toko.css` (akun & dashboard toko), `kasir.css` + `struk.css` (subdomain toko). Tanpa framework CSS, tanpa JavaScript pihak ketiga. Tidak ada `style=""` atau `<script>` inline (CSP ketat).

**Perintah berguna** (`.venv\Scripts\python manage.py ...`):
`serve`, `cek_db`, `cek_konten`, `seed_konten [--lengkapi]`, `backup_db`, `restore_db`, `buat_admin`, `reset_2fa`, `bersihkan_data` (termasuk wilayah SIM yang habis > 30 hari), `pos_bersihkan [--cek]`.

**Membuat ulang aset gambar** dari `assets/logo-h.png`: `.venv\Scripts\python scripts\build_assets.py`.
