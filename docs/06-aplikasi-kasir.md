# 06 — Aplikasi Kasir (POS) — Fase 1

Rancangan dan keputusan pemilik untuk aplikasi kasir Paket Tunas & Tumbuh.
Petunjuk pemakaian sehari-hari ada di `README.md` bagian 4 (“Aplikasi kasir”).

---

## Keputusan pemilik (17–18 November 2026)

| Topik | Keputusan |
|---|---|
| Domain & HTTPS | DNS di **Hostinger**, server memakai **Caddy** (seperti proyek SIGAP). Record `A *` → IP server. Sertifikat per toko lewat *On-Demand TLS* (tanpa plugin) |
| Port | **Satu aplikasi, satu port (8432)** untuk semua toko. Toko dikenali dari alamat (`<nama>.hansproject.app`), bukan dari port |
| Pengelolaan toko | **Semua di `hansproject.app`** (dashboard pemilik, login Google): barang, outlet, akun kasir, transaksi, laporan, pengaturan, perpanjang |
| Subdomain toko | Hanya **login kasir** di `/kasir/` (+ halaman toko sementara di `/`) |
| Akun kasir | Nama pengguna + PIN 6 angka, **dibuat oleh pemilik toko**. 1 akun per outlet |
| Aktivasi | Pelanggan memilih alamat toko saat memesan; toko dibuat otomatis saat admin mengubah pesanan menjadi **Aktif** |
| Internet | Fase awal **online saja** (tanpa mode offline) |
| Cetak struk | Fitur cetak bawaan browser, HP maupun PC |
| Penyimpanan Tunas | **1 GB** (sebelumnya 1,5 GB) |
| Masa aktif habis | 7 hari tenggang (kasir jalan + peringatan) → terkunci → **data dihapus permanen 30 hari setelah masa aktif habis**. Bayar sebelum itu = data kembali |
| Stok barang | Fase 2 |
| Halaman depan toko | Sementara: nama + alamat + “Halaman toko segera hadir”, tidak diindeks Google. Tambahan dari pemilik menyusul |
| Perpanjangan | Alur sama dengan pesanan, plus: **bisa pindah paket** dan **minta ganti alamat** (perlu persetujuan admin) |

---

## Alamat & alur permintaan

```
hansproject.app/...            → URL utama (config/urls.py): situs, /akun/, /akun/toko/<nama>/, panel
<nama>.hansproject.app/...     → URL toko (apps/pos/urls_store.py): /, /kasir/..., robots.txt
```

- `StoreHostMiddleware` memilih URL toko bila Host = `<nama>.STORE_BASE_DOMAIN`. Panel dan `/akun/` **tidak ada** di subdomain.
- `ALLOWED_HOSTS` otomatis ditambah `.STORE_BASE_DOMAIN`.
- Caddy: `on_demand_tls { ask http://127.0.0.1:8432/_tls/izin/ }`. `TlsAskMiddleware` (paling atas) menjawab 200 hanya untuk toko yang ada & belum dihapus, dan hanya untuk permintaan langsung dari 127.0.0.1 tanpa `X-Forwarded-For`. Caddy juga memblokir `/_tls/*` dari luar.
- Pengembangan: `STORE_BASE_DOMAIN=localhost` → `http://<nama>.localhost:8432`.

## Data (tabel `hp_pos_*`)

| Model | Isi |
|---|---|
| `Store` | pemilik (Member), alamat (subdomain, unik), nama, alamat & telepon struk, tulisan bawah struk, lebar kertas, paket, outlet dari paket + tambahan, status (normal/ditangguhkan), **aktif sampai**, catatan admin |
| `Outlet` | nomor (1, 2, …), nama, alamat, aktif, penghitung nomor struk |
| `Cashier` | 1 per outlet, nama pengguna (unik per toko), hash PIN, aktif, hitungan salah PIN, kunci sementara |
| `CashierSession` | sesi kasir (hash token), 7 hari diperpanjang otomatis |
| `Category`, `Product` | kategori; barang (nama, kode opsional unik per toko, harga rupiah bulat, dijual/tidak) |
| `Sale`, `SaleItem` | transaksi (nomor `outlet-urut`, kode unik dari layar kasir, subtotal, diskon Rp/%, total, dibayar, kembalian, cara bayar, status selesai/batal + alasan); salinan nama & harga barang |

`members.Order` ditambah: `order_type` (baru/perpanjang), `subdomain`, `store`, `activated_at`.

## Aturan penting

- **Isolasi toko**: dashboard mengambil toko lewat `Store.objects.owned_by(member)`, lalu semua data lewat relasi (`store.products`, `store.sales`, …). Kasir: sesi hanya berlaku bila `cashier.store` = toko dari alamat yang dibuka. Diuji di `tests/test_pos.py`.
- **Transaksi**: harga & total dihitung ulang di server dari database. Kode unik per transaksi (`client_key`) mencegah transaksi ganda saat internet putus. Nomor struk dibuat dengan kunci baris outlet (`select_for_update`).
- **Batal transaksi**: hanya pemilik, wajib alasan, data tidak dihapus, tidak dihitung di laporan.
- **Laporan**: dihitung per hari di Python (tidak bergantung tabel zona waktu MariaDB). Unduh CSV (`;`, UTF-8 BOM, aman dari *CSV injection*).
- **PIN**: 6 angka, tolak yang mudah ditebak (111111, 123456, …), hash Argon2, 5 kali salah → terkunci 15 menit, plus batas percobaan per IP. Ganti PIN / nonaktifkan = semua perangkat kasir keluar.
- **Cookie kasir** `hp_kasir`: HttpOnly, SameSite=Strict, Secure di produksi, **tanpa atribut Domain** (hanya untuk subdomain itu).
- **Masa aktif**: `Store.state()` → aktif / tenggang / terkunci / ditangguhkan / dihapus. Toko lewat batas hapus langsung dianggap tidak ada (404) walau penghapusan fisik belum berjalan.
- **Penghapusan**: `manage.py pos_bersihkan` (otomatis setelah backup malam). Toko yang perpanjangannya sedang dicek admin tidak dihapus.
- **Turun paket**: outlet terbaru di atas batas dinonaktifkan, data tetap.

## Fase berikutnya (belum dikerjakan)

- **Fase 2**: promo otomatis, halaman promosi toko + editor terbatas + tombol tampilkan daftar harga, PWA (Tumbuh), stok barang.
- **Fase 3**: pengukuran tempat simpan (1 GB / 5 GB) dan pembelian tambahan dari aplikasi.
- Kemungkinan: mode offline, foto barang, pemindai kamera.
