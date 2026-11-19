# 05 — Keamanan (WAJIB)

Keamanan adalah prioritas. Standar di bawah ini adalah **batas minimum**. Silakan tambah perlindungan lain kalau menurut Anda perlu, tapi jangan dikurangi. Kalau ada poin yang tidak relevan dengan pilihan teknologi Anda, terapkan padanannya dan jelaskan di ringkasan akhir.

Ingat bahwa **pemilik bukan ahli keamanan**. Setelan bawaan harus sudah aman, jadi keamanan tidak boleh bergantung pada pemilik yang harus "ingat menyalakan" sesuatu.

---

## 1. Rahasia & konfigurasi
- Semua rahasia (secret key, password database, dll.) hanya ada di `.env`. **Tidak boleh ada di kode atau di git.**
- Secret key dibuat acak dan kuat secara otomatis saat instalasi.
- **Mode produksi harus menolak berjalan** kalau konfigurasinya berbahaya, misalnya debug menyala, secret key masih contoh/kosong, atau host yang diizinkan belum diisi. Tampilkan pesan error yang jelas.
- Mode debug **mati** di produksi. Halaman error tidak boleh menampilkan stack trace, path file, versi software, atau isi konfigurasi.

## 2. Database
- Aplikasi memakai **user MariaDB khusus** dengan hak akses minimum, bukan `root`.
- Semua query lewat ORM atau parameterized query. **Tidak ada SQL yang disusun dari string input pengguna.**
- Port 3307 **tidak dibuka ke internet** (jelaskan di README untuk pengaturan firewall server).

## 3. HTTPS & header keamanan
- Di produksi: paksa HTTPS, aktifkan HSTS, dan pastikan cookie hanya dikirim lewat HTTPS (`Secure`, `HttpOnly`, `SameSite`).
- Kalau aplikasi berada di belakang reverse proxy, atur dengan benar header mana yang dipercaya (misalnya `X-Forwarded-Proto` / `X-Forwarded-For`), dan **hanya dari proxy tersebut**, supaya tidak bisa dipalsukan pengunjung.
- Pasang header keamanan:
  - **Content-Security-Policy** yang ketat. Hindari `unsafe-inline` / `unsafe-eval`; pakai nonce atau hash kalau memang butuh script inline.
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy`
  - `Permissions-Policy` (matikan fitur browser yang tidak dipakai)
  - Perlindungan clickjacking (`frame-ancestors` / `X-Frame-Options`)
- Jangan memuat script dari pihak ketiga kecuali benar-benar perlu. Lebih baik semua aset di-host sendiri.

## 4. Panel admin
- **Alamat panel admin bisa diatur dari `.env`**, dan nilai bawaannya bukan `/admin`.
- Password disimpan dengan hashing modern yang kuat (misalnya Argon2 atau bcrypt).
- **Batasi percobaan login**: kunci sementara atau perlambat setelah beberapa kali gagal, dan catat percobaan login di log.
- Sediakan **verifikasi dua langkah (2FA, misalnya TOTP)** untuk akun admin. Sebaiknya wajib, minimal tersedia dan dianjurkan di README.
- Sesi admin punya batas waktu tidak aktif. Logout benar-benar menghapus sesi.
- Semua form dilindungi **CSRF**.
- Panel admin diberi `noindex` dan tidak masuk sitemap.
- Akun admin pertama dibuat saat instalasi dengan password yang diketik pemilik, **bukan password bawaan**.

## 5. Input & output
- Semua input divalidasi di sisi server, termasuk input dari panel admin.
- Semua output di-escape dengan benar untuk mencegah **XSS**. Kalau ada field yang mengizinkan format teks (misalnya bold di FAQ), sanitasi dengan daftar tag yang diizinkan (allowlist).
- Endpoint publik yang menerima data (misalnya pencatat klik tombol DM Instagram) diberi **rate limiting** dan validasi, supaya tidak bisa dipakai untuk spam atau membanjiri database.

## 5b. Akun pelanggan (login dengan Google)
- Login memakai Google (OpenID Connect, authorization code + PKCE). Wajib memeriksa `state` (anti login-CSRF), `nonce`, penerbit, Client ID tujuan, masa berlaku token, dan email yang sudah diverifikasi Google. Client Secret hanya di `.env` dan tidak pernah dikirim ke browser.
- Website tidak menyimpan password pelanggan. Sesi pelanggan: token acak di cookie HttpOnly (Secure di produksi, SameSite=Lax); database hanya menyimpan hash-nya. Sesi berakhir otomatis bila tidak aktif, dan keluar benar-benar menghapus sesi (tersedia juga "keluar dari semua perangkat").
- Alamat tujuan setelah login hanya boleh di situs sendiri (cegah open redirect). Percobaan login dan kiriman pertanyaan dibatasi jumlahnya.
- Semua formulir akun memakai CSRF. Halaman akun tidak di-cache (`no-store`) dan tidak diindeks.
- Akun pelanggan **terpisah** dari akun admin. Pelanggan tidak boleh bisa membuka panel admin.
- Pelanggan hanya bisa melihat pesanan dan bukti bayar miliknya sendiri. Bukti bayar disimpan tanpa alamat publik dan diproses ulang (metadata dibuang).
- Website tidak menampilkan kontak pribadi pemilik (nomor telepon/chat). Kontak hanya DM Instagram @hansproject.app.

## 6. Upload file (gambar QRIS, foto testimoni, dll.)
- Batasi jenis file (cek isi file, bukan hanya ekstensinya) dan ukuran maksimal.
- **Tolak SVG** dan format lain yang bisa membawa script.
- Proses ulang (re-encode) gambar dan buang metadata (EXIF).
- Simpan dengan nama file acak, di folder yang tidak bisa mengeksekusi file.

## 7. Privasi
- Kumpulkan data seminimal mungkin. Jangan menyimpan alamat IP mentah pengunjung. Kalau perlu untuk rate limiting, simpan sementara atau dalam bentuk hash.
- Kebijakan privasi di website harus sesuai dengan apa yang benar-benar dikumpulkan.

## 8. Log & backup
- Log mencatat kejadian penting (error, login admin berhasil/gagal, perubahan data penting di admin) **tanpa mencatat password, secret, atau data sensitif**.
- File backup database disimpan di folder dengan akses terbatas. Jelaskan di README cara membatasi akses folder di Windows (misalnya dengan `icacls`).
- `update.bat` selalu membuat backup sebelum migrasi.

## 9. Dependensi
- Versi dependensi dikunci. Pakai versi stabil terbaru yang tidak punya celah keamanan yang diketahui.
- Jalankan pemeriksaan celah dependensi (misalnya `pip-audit`) dan analisis kode (misalnya `bandit`), lalu laporkan hasilnya di ringkasan.
- Jelaskan di README cara mengecek dan memperbarui dependensi secara berkala.

## 10. Server Windows (panduan di README)
- Jalankan service dengan **akun Windows yang hak aksesnya terbatas**, bukan Administrator.
- Batasi akses file `.env`, folder backup, dan folder log hanya untuk akun tersebut dan Administrator.
- Firewall: hanya port 80 dan 443 yang terbuka ke publik. Port aplikasi Python dan port MariaDB 3307 hanya bisa diakses dari server itu sendiri.

---

## Checklist keamanan

- [ ] Tidak ada rahasia di kode atau git, dan `.env` ada di `.gitignore`
- [ ] Mode produksi menolak berjalan dengan konfigurasi berbahaya
- [ ] User database khusus, bukan root
- [ ] HTTPS dipaksa, HSTS aktif, cookie aman
- [ ] Header keamanan terpasang, termasuk CSP yang ketat
- [ ] Alamat admin bisa diatur dan bukan `/admin`
- [ ] Pembatasan percobaan login dan 2FA untuk admin
- [ ] CSRF, validasi input, escape output
- [ ] Upload file aman
- [ ] Rate limiting di endpoint publik
- [ ] Log tanpa data sensitif
- [ ] Pemeriksaan dependensi dan analisis kode sudah dijalankan
- [ ] Jika memakai Django: `python manage.py check --deploy` tanpa peringatan penting
- [ ] Panduan pengamanan server Windows ada di README
