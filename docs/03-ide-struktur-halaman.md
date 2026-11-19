# 03 — Ide Struktur Halaman (BEBAS DIUBAH)

Ini hanya **usulan awal** agar Anda punya gambaran. Silakan ubah urutan, gabungkan, hapus, tambah bagian baru, atau buat susunan yang sama sekali berbeda kalau menurut Anda lebih efektif untuk tujuan website (lihat `PROMPT.md`).

## Halaman

- `/`: landing page utama (semua bagian di bawah)
- `/syarat-ketentuan`: syarat & ketentuan (berisi aturan paket, telat bayar, penghapusan data, dll. dari `docs/01`)
- `/kebijakan-privasi`: kebijakan privasi sederhana
- Halaman 404 yang ramah

Isi halaman legal cukup berupa draf yang masuk akal berdasarkan `docs/01`. Beri tanda jelas bahwa draf ini perlu ditinjau pemilik sebelum dipakai resmi.

Kalau menurut Anda lebih baik ada halaman terpisah (misalnya `/kasir` dan `/jasa`), silakan.

## Usulan bagian di landing page

1. **Navigasi**: logo "H" + teks "HANS Project", menu singkat, tombol **"Daftar / Masuk"** (berikon), yang berganti menjadi **"Profil"** setelah login. Di HP: **menu bawah** (Beranda · Fitur · Harga · Jasa · Masuk/Profil), bukan menu burger.
2. **Hero**: pesan utama dalam satu kalimat yang langsung dipahami pemilik warung. Contoh arah: *"Aplikasi kasir mulai Rp25 ribu sebulan"* + tagline *"Catat jualan, hitung uang, cetak struk. Cukup pakai HP."* Tombol: lihat harga + **"Tanya Kami"** (wajib login) + tautan **DM Instagram @hansproject.app**. Visual: mockup HP berisi tampilan kasir.
3. **Masalah yang dikenali**: misalnya *"Masih catat jualan di buku? Sering salah hitung? Tidak tahu untung berapa bulan ini?"*, lalu solusinya.
4. **Apa yang bisa dilakukan aplikasi kasir**: fitur dalam bahasa sederhana, dengan ikon. Detail teknis sebagai pelengkap.
5. **Halaman promosi toko**: tunjukkan bahwa toko pelanggan bisa punya halaman sendiri (contoh mockup `warungbudi.hansproject.app`). Tegaskan: untuk promosi, bukan pesan online.
6. **Harga paket kasir**: Tunas & Tumbuh, dengan Tumbuh ditonjolkan. Termasuk "semua paket sudah termasuk" dan tambahan (toko & tempat simpan).
7. **Jasa bikin website & aplikasi**: Paket Rimba sebagai layanan tersendiri, dengan ajakan konsultasi gratis.
8. **Detail teknis**: tabel perbandingan lengkap untuk yang paham teknologi. Bisa dibuat buka-tutup supaya tidak membebani orang awam.
9. **Cara daftar**: langkah-langkah bergambar dari pilih paket sampai aplikasi aktif.
10. **Pertanyaan yang sering ditanya (FAQ)**: buka-tutup (accordion).
11. **Ajakan terakhir**: satu kalimat penutup + tombol lihat harga + "Daftar / Masuk" + tautan DM Instagram.
12. **Footer**: logo, kontak, link halaman legal, hak cipta.

Kontak hanya **DM Instagram @hansproject.app** (tidak ada tombol chat melayang). Tombol paket = **"Pesan Sekarang"** (wajib login).

## Panel admin (untuk pemilik)

Tujuannya: pemilik bisa mengelola isi website tanpa menyentuh kode. Pemilik bukan programmer berpengalaman, jadi buat panelnya sederhana dan berbahasa Indonesia.

Usulan yang bisa dikelola dari admin:
- **Paket & harga**: nama, harga, label (misalnya "Paling Direkomendasikan"), urutan, dan daftar poin (versi sederhana + versi teknis)
- **Harga tambahan**: tambah toko, tambah tempat simpan
- **FAQ**: tambah, ubah, hapus, atur urutan
- **Pengaturan umum**: username Instagram (untuk DM), email, jam kerja support, link sosial media, info rekening/QRIS (termasuk upload gambar QRIS)
- **Testimoni**: siapkan, tapi tampil di website hanya kalau diaktifkan dan sudah ada isinya
- **Teks hero / pengumuman** (misalnya promo sementara), kalau menurut Anda berguna

Data awal (seed) diisi otomatis sesuai `docs/01`, supaya website langsung lengkap setelah instalasi.

Ide data pendukung (opsional):
- Hitung berapa kali tombol kontak (DM Instagram) diklik. Nanti juga tombol "Pesan Sekarang" per paket, untuk melihat paket mana yang paling diminati. Simpan tanpa data pribadi pengunjung. Jangan simpan alamat IP mentah.

Alamat panel admin **jangan memakai alamat yang mudah ditebak** seperti `/admin`. Buat bisa diatur lewat `.env` (lihat `docs/05-keamanan.md`).

## Ide tambahan (opsional, terserah Anda)

- Kalkulator kecil: "Berapa toko yang Anda punya?" → menyarankan paket yang paling hemat (memanfaatkan aturan tambah toko Rp15.000).
- Demo interaktif kasir sederhana di halaman (pura-pura tambah barang → total → struk), supaya orang awam bisa "mencoba" tanpa mendaftar.
- Bagian testimoni yang disiapkan tapi disembunyikan sampai pemilik punya testimoni asli.
