# 04 — Teknis & Instalasi

Bagian **Kebutuhan** harus terpenuhi. Bagian **Saran** boleh Anda ganti kalau ada pilihan yang lebih baik. Untuk keamanan, lihat `docs/05-keamanan.md`.

---

## Kebutuhan

### Lingkungan
- **Python** dengan **virtual environment (venv)**. Semua dependensi dipasang di dalam venv, tidak ada yang dipasang global.
- Tetapkan versi Python minimum yang didukung, dan pastikan cocok di Windows.
- **MariaDB di port 3307** (bukan 3306). Host, port, nama database, user, dan password diambil dari `.env`.
  - Komputer pengembangan: MariaDB 10.11 versi ZIP (`%USERPROFILE%\sigap-mariadb`), dinyalakan dengan skrip `mariadb-dev.ps1` dari proyek SIGAP.
  - Database server produksi **sudah berisi tabel & data lain**. Semua tabel website (termasuk tabel bawaan framework) **wajib berawalan `hp_`**. Backup/restore hanya menyentuh tabel `hp_*`.
  - Gunakan charset `utf8mb4`.
  - Pilih driver database yang **mudah dipasang di Windows** tanpa perlu compiler. Cek dulu sebelum memutuskan.
- Pengembangan di komputer ini. Cek sistem operasinya, lalu buat script setup pengembangan yang sesuai.
- Produksi di **server Windows**.

### File konfigurasi
- **`.env.example`**: daftar semua variabel yang dibutuhkan, dengan nilai contoh atau placeholder dan **komentar penjelasan dalam bahasa Indonesia**. File ini masuk git.
- **`.env`**: nilai asli, **tidak boleh masuk git** (masukkan ke `.gitignore`).
- Variabel yang kemungkinan dibutuhkan (silakan sesuaikan): mode (development/production), secret key, debug, host yang diizinkan, koneksi database (host, port `3307`, nama, user, password), alamat panel admin, zona waktu (default `Asia/Makassar`), pengaturan email kalau dipakai, dan lokasi folder log dan backup.
- Konfigurasi aplikasi dipisah dengan rapi antara development dan production, tapi tetap sederhana.
- Konten yang sering diubah pemilik (harga, FAQ, username Instagram, dll.) **dikelola dari panel admin** dan tersimpan di database, bukan di file konfigurasi (lihat `docs/03`).

### Database
- Sediakan file SQL (atau script) untuk **membuat database dan user khusus aplikasi** dengan hak akses seminimal mungkin. Jangan pakai user `root`. Password berupa placeholder.
- Struktur tabel dibuat lewat **migrasi**, bukan SQL manual, supaya mudah diperbarui.
- Sediakan **data awal (seed)** sesuai `docs/01`. Seed harus aman dijalankan ulang tanpa menggandakan data.

### File batch untuk server produksi Windows

Pemilik akan memindahkan proyek ke server Windows dan menjalankan file-file ini. Buat supaya **mudah dipakai orang yang bukan ahli**: pesan dalam bahasa Indonesia yang jelas, berhenti dengan pesan yang jelas kalau ada error, dan tidak menutup jendela sebelum pesannya terbaca.

Usulan (silakan tambah, gabung, atau ganti nama):

| File | Fungsi |
|---|---|
| `install.bat` | Cek Python, buat venv, pasang dependensi, buat `.env` dari `.env.example` kalau belum ada (lalu minta pemilik mengisinya), buat secret key acak, cek koneksi ke MariaDB port 3307, jalankan migrasi dan seed, siapkan file statis, buat akun admin pertama |
| `start.bat` | Menjalankan website dalam mode produksi |
| `stop.bat` | Menghentikan website |
| `update.bat` | **Backup database dulu**, lalu pasang dependensi baru, migrasi, siapkan ulang file statis, dan restart |
| `backup.bat` | Backup database (dump MariaDB port 3307) dengan nama file bertanggal. Hapus backup lama otomatis setelah jumlah atau umur tertentu. |
| `restore.bat` | Mengembalikan database dari file backup, dengan konfirmasi sebelum menimpa |
| `service-install.bat` / `service-uninstall.bat` | Memasang website sebagai **Windows Service** supaya otomatis jalan saat server dinyalakan ulang |

Ketentuan batch:
- Harus tetap jalan kalau folder proyek berada di path yang **mengandung spasi**.
- **Aman dijalankan ulang** (idempotent). Misalnya, menjalankan `install.bat` dua kali tidak merusak apa pun.
- **Jangan menampilkan password** di layar atau di command line yang bisa terlihat di daftar proses. Misalnya untuk dump database, pakai file opsi yang aksesnya dibatasi.
- Perhatikan encoding supaya teks berbahasa Indonesia tampil benar di Command Prompt.

### Memindahkan dari komputer ini ke server produksi
Jelaskan di README langkah demi langkahnya, misalnya:
- File apa saja yang perlu dipindahkan. Folder venv dan `.env` **tidak ikut**, karena dibuat ulang di server.
- Cara memindahkan data database (backup di sini → restore di server), kalau diperlukan.
- Urutan menjalankan file batch di server.
- Cara mengecek bahwa website sudah berjalan dengan benar.

### Menjalankan di produksi (Windows)
- Gunakan **server aplikasi Python yang mendukung Windows** untuk produksi (catatan: Gunicorn tidak berjalan di Windows). Jangan pakai server development.
- Aplikasi Python sebaiknya hanya mendengarkan di `127.0.0.1`, lalu diakses publik lewat **reverse proxy** yang menangani **HTTPS**. Domain `.app` wajib HTTPS (sudah otomatis dipaksa oleh semua browser), jadi HTTPS bukan pilihan. Pilih reverse proxy yang cocok untuk Windows, sediakan contoh konfigurasinya, dan jelaskan di README.
- Log aplikasi ditulis ke file dengan rotasi otomatis supaya tidak memenuhi disk.

### Performa (sangat penting)
Target pengguna banyak memakai **HP Android murah** dengan **internet lambat** di daerah.
- Halaman publik harus cepat terbuka di jaringan lambat. Usahakan ukuran halaman pertama sekecil mungkin.
- Gambar dioptimalkan: format modern, ukuran responsif, lazy load.
- JavaScript seminimal mungkin. Konten utama tetap terbaca walau JavaScript gagal dimuat.
- Font tidak boleh menghambat tampilan teks.
- Manfaatkan cache: cache browser untuk file statis, dan cache data dari database seperlunya. Data jarang berubah, jadi jangan query berulang untuk setiap pengunjung kalau tidak perlu.

### Tampilan
- **Mobile-first.** Uji di lebar layar ±360 px.
- Teks cukup besar, tombol cukup besar untuk jari.
- Aksesibilitas minimal WCAG 2.1 AA.
- Tema terang.

### Pesan & tanya lewat akun
- Satu-satunya kontak: **DM Instagram @hansproject.app** (`https://www.instagram.com/hansproject.app`).
- Tombol paket **"Pesan Sekarang"** dan tombol **"Tanya Kami"** wajib login. Bila belum login, arahkan ke halaman daftar/login, lalu kembali ke tujuan semula setelah berhasil masuk.
- **Daftar / masuk hanya dengan Google** (OpenID Connect). Client ID & Client Secret disimpan di `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`), tidak pernah di kode. Data pelanggan disimpan di database sendiri (tabel `hp_member*`).
- Setelah login pertama: wajib isi nomor HP dan nama usaha. Halaman Profil: data diri, status pesanan, pertanyaan & jawaban, keluar.
- Alur paket kasir: pesan → lihat cara bayar → unggah foto bukti bayar → admin cek di panel → status Aktif. Paket Rimba: pesanan berstatus "Menunggu konsultasi".
- Foto bukti bayar adalah data **pribadi**: disimpan di folder terpisah tanpa alamat publik, hanya bisa dibuka pemiliknya dan admin.
- Kontak alternatif tanpa login: **DM Instagram** (`https://www.instagram.com/<username>`), username diatur dari panel admin.
- Halaman publik tetap di-cache sama untuk semua pengunjung. Tombol "Daftar / Masuk" ditukar menjadi "Profil" di browser (JavaScript membaca cookie penanda tanpa rahasia). Halaman `/akun/` tidak di-cache dan tidak diindeks.

### SEO & berbagi link
- `lang="id"`, title dan meta description yang relevan untuk pencarian Indonesia (misalnya "aplikasi kasir murah", "aplikasi kasir UMKM", "jasa pembuatan website").
- Open Graph & Twitter card. Gambar OG dibuat dari logo "H" dan warna brand.
- Favicon, apple-touch-icon, dan web manifest.
- Structured data (schema.org) yang sesuai, misalnya Organization dan Product/Offer.
- `sitemap.xml` dan `robots.txt`. Panel admin tidak boleh terindeks.

### Kualitas
- Dependensi **dikunci versinya** (pinned). Pisahkan dependensi produksi dan pengembangan.
- Ada **tes otomatis** untuk hal penting, misalnya: harga tampil sesuai data, kontak hanya DM Instagram, tombol pesan/tanya mewajibkan login, panel admin tidak bisa diakses tanpa login, header keamanan terpasang, dan halaman error tidak membocorkan informasi.
- Struktur kode rapi dan mudah dipahami programmer lain.

---

## Saran (boleh diganti)

- **Framework:** **Django** cocok di sini. Sudah ada panel admin, ORM dan migrasi, autentikasi, dan banyak perlindungan keamanan bawaan (CSRF, XSS, clickjacking, SQL injection), serta perintah `check --deploy`. Kalau Anda punya alasan kuat memilih yang lain (Flask, FastAPI, dll.), silakan, asalkan standar keamanan di `docs/05` tetap terpenuhi.
- **Server produksi Windows:** misalnya Waitress.
- **File statis:** misalnya WhiteNoise, atau dilayani langsung oleh reverse proxy.
- **Reverse proxy + HTTPS di Windows:** misalnya Caddy (HTTPS otomatis), IIS + URL Rewrite/ARR, atau nginx.
- **Windows Service:** misalnya NSSM, WinSW, atau cara lain yang andal.
- **Styling:** bebas. Kalau memakai Tailwind CSS, pastikan hasil build CSS kecil dan proses build tidak menyulitkan instalasi di server Windows (misalnya CSS hasil build ikut disertakan, supaya server tidak perlu Node.js).

---

## Checklist sebelum selesai

- [ ] Semua harga dan isi paket sama persis dengan `docs/01` (data seed)
- [ ] Website jalan di komputer ini dalam venv, terhubung ke MariaDB port 3307
- [ ] `.env.example` lengkap dengan komentar, dan `.env` tidak masuk git
- [ ] Semua file batch sudah ada, dengan pesan yang jelas, dan aman dijalankan ulang
- [ ] README berisi panduan pengembangan, panel admin, dan **pemindahan ke server Windows**
- [ ] Kontak hanya DM Instagram; tombol "Pesan Sekarang"/"Tanya Kami" mewajibkan login; DM Instagram tersedia
- [ ] Tampilan rapi di HP (±360 px), tablet, dan desktop; HP memakai menu bawah
- [ ] Teks utama mudah dipahami orang awam, detail teknis tetap tersedia
- [ ] Tidak ada testimoni atau angka palsu
- [ ] Semua tes lulus
- [ ] Checklist keamanan di `docs/05` terpenuhi
- [ ] Ringkasan akhir: keputusan penting, perbedaan dari usulan, langkah keamanan, dan daftar placeholder
