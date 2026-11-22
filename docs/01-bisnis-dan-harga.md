# 01 — Fakta Bisnis & Harga (WAJIB AKURAT)

Semua harga, isi paket, batasan, dan kebijakan di file ini adalah **keputusan bisnis yang sudah final**. Kata-katanya boleh dirapikan atau ditulis ulang supaya lebih mudah dipahami, tapi **maknanya tidak boleh berubah**.

Setiap poin ditulis dalam dua versi:
- **Sederhana:** untuk orang awam. Ini versi utama yang dibaca semua orang.
- **Teknis:** untuk yang paham teknologi. Sifatnya pelengkap.

Format harga: `Rp25.000`, dengan titik sebagai pemisah ribuan dan tanpa spasi setelah "Rp".

---

## Gambaran bisnis

HANS Project menjual dua jenis layanan:

1. **Aplikasi Kasir (langganan bulanan)**: Paket **TUNAS** dan **TUMBUH**.
   Aplikasinya siap pakai dan sama untuk semua pelanggan, jadi tidak dibuat ulang per pelanggan. Pelanggan memasukkan sendiri barang dan harganya.
2. **Jasa Bikin Website & Aplikasi (proyek custom)**: Paket **RIMBA**.
   Website atau aplikasi dibangun dari nol sesuai kebutuhan klien.

Nama paket bertema pertumbuhan pohon: Tunas → Tumbuh → Rimba.

> **Pembaruan 22 November 2026 — platform solusi digital.** HANS Project kini satu identitas: *penyedia solusi digital*.
> Setiap solusi berlangganan punya **Paket Tunas & Tumbuh** sendiri:
> - **Aplikasi Kasir**: Tunas & Tumbuh (isi di bawah).
> - **Sistem Informasi Manajemen (SIM)**: SIM Tunas (cocok RT/RW, baca otomatis 100 dokumen/bln, 1 GB) dan SIM Tumbuh
>   (kelurahan/kecamatan, 1.000 dokumen/bln, 5 GB, rekap unit di bawahnya, support prioritas). **Harga belum
>   ditentukan pemilik** (Rp0 = tampil "Segera diumumkan", belum bisa dipesan) — isi di panel.
> - **Tiket Online**: segera hadir, belum ada paket.
> Rimba tetap jasa terpisah (website/aplikasi/sistem informasi custom). Halaman utama hanya merangkum; detail tiap
> solusi ada di `/aplikasi-kasir/`, `/sistem-informasi-manajemen/`, `/website-aplikasi/`.

**Jangan tampilkan ketiga paket sebagai tiga kolom setara dalam satu tabel harga utama.** Tunas dan Tumbuh adalah produk yang sama dengan level berbeda, sedangkan Rimba adalah jenis layanan yang lain sama sekali. Kalau disejajarkan, pelanggan akan membandingkan hal yang tidak sebanding. Tabel perbandingan teknis (di bagian bawah file ini) boleh memuat ketiganya.

---

## 🧾 APLIKASI KASIR

Tagline: *Catat jualan, hitung uang, cetak struk. Cukup pakai HP.*

### 🌱 Paket TUNAS — Rp25.000/bulan

**Cocok untuk:** warung, usaha rumahan, jualan online, atau yang baru mulai usaha.

| Sederhana | Teknis |
|---|---|
| Masukkan barang dan harga sendiri, kapan saja | Manajemen produk & harga mandiri |
| Hitung belanja pembeli otomatis, tidak perlu kalkulator | Sistem kasir (POS) |
| Cetak struk untuk pembeli | Cetak struk (printer thermal) |
| Bisa kasih diskon dan promo | Pengaturan diskon & promo |
| Catatan jualan harian, mingguan, bulanan dibuat otomatis | Laporan & rekap penjualan otomatis |
| Toko Anda punya alamat di internet sendiri, contoh: `warungbudi.hansproject.app` | Subdomain *.hansproject.app |
| Halaman promosi toko sendiri (lihat penjelasan di bawah) | Landing page toko dengan editor terbatas |
| Tempat simpan catatan yang cukup untuk usaha kecil | Penyimpanan 1 GB |
| Untuk 2 toko, masing-masing punya alamat kasir, barang, laporan, dan akun kasir sendiri | 2 toko, 1 subdomain & 1 akun kasir per toko |
| 1 kali per bulan boleh minta ganti tampilan (logo, warna, tulisan di struk) | 1 revisi tampilan per bulan |
| Bisa tanya-tanya di jam kerja | Support (jam kerja) — *saluran: lewat akun; PERLU KONFIRMASI pemilik* |

### 🌿 Paket TUMBUH — Rp99.000/bulan ⭐ (paket yang ditonjolkan / "Paling Direkomendasikan")

> Catatan: label yang dipakai adalah **"Paling Direkomendasikan"**, karena bisnis ini baru dan belum ada data pelanggan.

**Cocok untuk:** kafe, rumah makan, toko yang punya karyawan, dan usaha yang sudah jalan.

**Semua yang ada di Paket Tunas, ditambah:**

| Sederhana | Teknis |
|---|---|
| Ada ikon aplikasi di HP, tinggal pencet seperti aplikasi biasa. Tidak perlu download dari Play Store | Progressive Web App (PWA), bisa diinstal dari browser |
| Tempat simpan catatan lebih besar | Penyimpanan 5 GB |
| Untuk sampai 10 toko atau cabang, masing-masing terpisah | 10 toko, 1 subdomain & 1 akun kasir per toko |
| Boleh minta 3 tambahan kemampuan baru di aplikasi per tahun, dikerjakan lebih dulu | 3 request fitur/modifikasi prioritas per tahun |
| Pertanyaan Anda dijawab lebih dulu | Customer service prioritas |

### ✅ Termasuk di semua paket kasir

| Sederhana | Teknis |
|---|---|
| Bisa dipakai kapan saja, siang atau malam | Online 24/7 |
| Bisa dibuka dari HP atau laptop, di mana saja, asal ada internet | Berbasis web (cloud), lintas perangkat |
| Catatan jualan tersimpan aman, tidak hilang walau HP rusak | Data tersimpan di server, bukan di perangkat |

### 🏪 Halaman Promosi Toko (Tunas & Tumbuh)

Setiap pelanggan kasir **boleh** (kalau mau) punya halaman promosi sederhana untuk tokonya, di alamat subdomain mereka.

- **Fungsinya hanya untuk promosi, bukan untuk pesan atau belanja online.** Ini harus jelas supaya pelanggan tidak salah paham.
- Yang bisa diubah sendiri oleh pelanggan **sangat terbatas**:
  - Logo toko
  - Tulisan/teks
  - Beberapa foto di halaman utama
  - Tombol **tampilkan/sembunyikan daftar harga**. Kalau diaktifkan, daftar barang dan harga dari aplikasi kasir mereka otomatis ikut tampil di halaman promosi.
- Versi sederhana: *"Toko Anda dapat halaman promosi sendiri. Bisa ganti logo, tulisan, dan foto. Daftar harga dari kasir juga bisa ikut tampil, tinggal nyalakan."*
- Versi teknis: *"Landing page toko di subdomain, editor terbatas (logo, teks, foto hero), toggle sinkronisasi katalog harga dari POS."*

### ➕ Tambahan (bisa dibeli kapan saja)

**Tambah toko/cabang: Rp15.000 per toko, per bulan**
- Berlaku untuk Tunas dan Tumbuh.
- Teknis: add-on toko (subdomain + akun kasir sendiri).
- Harganya sengaja sedikit lebih mahal daripada harga per toko di dalam paket, supaya pelanggan yang butuh banyak toko terdorong naik paket. Contoh: Tunas + 5 toko tambahan = Rp100.000, sedikit lebih mahal dari Tumbuh. Boleh ditampilkan sebagai tips "lebih hemat naik ke Tumbuh", tapi tidak wajib.

**Tambah tempat simpan (kalau sudah penuh)**: berlaku untuk semua paket.

| Tambahan | Harga/bulan |
|---|---|
| +1 GB | Rp10.000 |
| +5 GB | Rp35.000 |
| +10 GB | Rp60.000 |

---

## 🛠️ JASA BIKIN WEBSITE & APLIKASI

### 🌳 Paket RIMBA — mulai Rp349.000 (biaya pembuatan), lalu Rp200.000/bulan

**Cocok untuk:** usaha yang ingin punya website atau aplikasi sendiri, usaha dengan banyak cabang, perusahaan, atau siapa saja yang punya ide aplikasi.

| Sederhana | Teknis |
|---|---|
| Kami buatkan website atau aplikasi khusus untuk usaha Anda, sesuai keinginan | Custom development dari nol |
| Aplikasi bisa tayang di Play Store (HP Android) dan App Store (iPhone) | Aplikasi Android & iOS + publikasi ke store |
| Alamat website bebas pilih, contoh: `tokobudi.com` | Custom domain (.com, .id, .co.id, dll.) |
| Isi dan tampilan bebas, sesuai kesepakatan | Menu & fitur custom sesuai kontrak |
| Bisa ditambah fitur pintar, seperti balas chat pembeli otomatis | Integrasi model AI sederhana (chatbot, rekomendasi, dll.) |
| Tempat simpan paling besar | Penyimpanan 10 GB |
| Ada orang khusus yang mengurus kebutuhan Anda | Dedicated support |

Catatan yang wajib tampil:
- *Harga pembuatan tergantung seberapa rumit permintaan Anda. Konsultasi dulu, gratis.*
- *Biaya bulanan Rp200.000 untuk menjaga website/aplikasi tetap jalan, dirawat, dan dibantu kalau ada masalah.* (Teknis: hosting, maintenance & support.)
- *Biaya pendaftaran akun Play Store dan App Store ditanggung klien.* (Teknis: Google Play Developer sekali bayar, Apple Developer Program tahunan.)

Jasa pembuatan website (company profile, toko online, dll.) masuk ke paket ini. Tidak ada paket "website saja" yang terpisah.

---

## 📋 Tabel Detail Teknis (untuk pembaca yang paham teknologi)

| | Tunas | Tumbuh | Rimba |
|---|---|---|---|
| Harga | Rp25.000/bln | Rp99.000/bln | Mulai Rp349.000 + Rp200.000/bln |
| Jenis | Aplikasi kasir (POS) | Aplikasi kasir (POS) | Custom development |
| Penyimpanan | 1 GB | 5 GB | 10 GB |
| Jumlah toko | 2 | 10 | Sesuai kebutuhan |
| Akun kasir | 1 per toko, bisa di banyak perangkat | 1 per toko, bisa di banyak perangkat | Sesuai kebutuhan |
| Alamat web | Subdomain | Subdomain | Custom domain |
| Halaman promosi toko | Ya (editor terbatas) | Ya (editor terbatas) | Custom penuh |
| Aplikasi HP | – | PWA | Android & iOS (Play Store / App Store) |
| Modifikasi | 1 revisi tampilan/bln | 3 request fitur prioritas/thn | Bebas sesuai kontrak |
| Support | Jam kerja | Prioritas | Dedicated |
| Tambah toko | Rp15.000/toko/bln | Rp15.000/toko/bln | – |
| Tambah penyimpanan | Mulai Rp10.000/bln | Mulai Rp10.000/bln | Mulai Rp10.000/bln |

---

## 💳 Cara Daftar & Bayar

- **Tidak ada payment gateway dan tidak ada pembayaran online.**
- Pendaftaran dan pemesanan lewat **akun di website** (wajib daftar/login). Semua keperluan lain lewat **DM Instagram @hansproject.app**.
- Alurnya:
  1. Pilih paket, lalu tekan **"Pesan Sekarang"**.
  2. Daftar atau masuk **dengan akun Google** (bila belum login, otomatis diarahkan ke halaman daftar/login). Login pertama: isi nomor HP dan nama usaha.
  3. Bayar lewat transfer bank atau scan QRIS.
  4. Unggah foto bukti bayar di halaman pesanan (di akun). *Diterapkan sebagai usulan; pemilik boleh mengubah.*
  5. Admin mengecek bukti bayar di panel, lalu status pesanan menjadi **Aktif**. Pelanggan melihat statusnya di halaman Profil.
- Paket Rimba: setelah dipesan, statusnya **Menunggu konsultasi** (kebutuhan dibahas dulu sebelum pembayaran).
- Kontak alternatif tanpa login: **DM Instagram @hansproject.app**.
- Rekening dan QRIS belum ada. Isi data awalnya dengan placeholder yang mudah dikenali, supaya nanti bisa diganti pemilik lewat panel admin.

---

## ⏳ Kebijakan Telat Bayar & Data

| Waktu sejak jatuh tempo | Yang terjadi |
|---|---|
| Hari 1–7 (masa tenggang) | Aplikasi masih bisa dipakai. Pelanggan masih bisa download/menyimpan catatan jualannya sendiri. |
| Hari 8 sampai ±1 bulan | Aplikasi berhenti sementara (dinonaktifkan). Kalau pelanggan membayar, aplikasi aktif lagi dan **semua data masih utuh**. |
| Setelah ±1 bulan tidak aktif | Semua data **dihapus permanen** dan tidak bisa dikembalikan. |

Versi sederhana untuk FAQ:
- **Telat 1–7 hari:** aplikasi masih bisa dipakai. Kalau mau berhenti, catatan jualan masih bisa Anda simpan ke HP atau laptop.
- **Telat 8 hari sampai 1 bulan:** aplikasi berhenti sementara. Begitu Anda bayar, aplikasi jalan lagi dan semua catatan masih lengkap.
- **Lewat dari itu:** semua catatan dihapus dan tidak bisa dikembalikan.

---

## ❓ Bahan FAQ (boleh ditambah, dirapikan, atau diurutkan ulang)

- **Bayarnya bagaimana?** Transfer atau scan QRIS, lalu kirim foto bukti bayar *(caranya perlu dikonfirmasi pemilik)*. Aplikasi langsung diaktifkan.
- **Bagaimana cara pesan?** Pilih paket, tekan "Pesan Sekarang", lalu daftar atau masuk ke akun Anda.
- **Karyawan saya perlu akun sendiri?** Tidak perlu. Setiap toko punya 1 akun, dan siapa pun yang jaga toko bisa memakainya.
- **Kalau tempat simpan saya penuh bagaimana?** Kami kabari sebelum penuh *(lewat akun; perlu dikonfirmasi pemilik)*. Anda bisa beli tambahan tempat simpan atau naik paket.
- **Kalau saya telat bayar bagaimana?** (lihat kebijakan di atas)
- **Apa bedanya "ganti tampilan" dan "tambahan kemampuan baru"?**
  - Ganti tampilan: mengubah yang sudah ada, misalnya logo, warna, atau tulisan di struk.
  - Tambahan kemampuan baru: menambah sesuatu yang belum ada, misalnya fitur catat utang pelanggan.
- **Apakah halaman promosi toko bisa dipakai untuk terima pesanan online?** Tidak. Halaman ini hanya untuk promosi: menampilkan logo, tulisan, foto, dan (kalau mau) daftar harga.
- **Apakah aplikasi Paket Tumbuh ada di Play Store?** Tidak perlu download dari Play Store. Aplikasinya dipasang langsung dari browser HP, lalu muncul ikonnya di layar seperti aplikasi biasa. Aplikasi yang tayang di Play Store/App Store ada di Paket Rimba.
- **Bisa pindah paket?** *(Kebijakan belum ditentukan. Kalau Anda menambahkan pertanyaan ini, tulis jawabannya sebagai placeholder dan sebutkan di ringkasan akhir.)*
