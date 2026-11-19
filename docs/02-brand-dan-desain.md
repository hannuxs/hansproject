# 02 — Brand & Arahan Desain

Isi file ini adalah **arahan**, bukan aturan kaku. Kalau Anda punya pendekatan desain yang lebih baik, silakan dipakai.

## Identitas

- **Nama brand:** HANS Project (penulisan: "HANS Project", HANS huruf kapital semua)
- **Domain:** hansproject.app
- **Bahasa website:** Bahasa Indonesia
- **Tema:** **terang (light mode)**. Ini permintaan pemilik. Tidak perlu dark mode.

## Logo

File: `assets/logo-h.png`. Ikon huruf "H" saja, PNG transparan, persegi 710×710.

Ciri logo: huruf "H" bergaya 3D dengan gradasi kuning keemasan → oranye → merah, dililit pita bertuliskan simbol matematika (π, |x+y|, ±), grafik batang naik, bola oranye mengkilap, dan kilauan bintang kecil.

**Cara pakai logo:**
- Logo yang dipakai **hanya ikon "H" ini**.
- Tulisan **"HANS Project"** di samping logo (navbar, footer, dll.) **dibuat sebagai teks biasa**, bukan gambar. **Warna dan gayanya bebas**, silakan pilih yang paling serasi dengan logo dan desain. Contoh arah: "HANS" tebal dengan warna/gradasi dari logo, "Project" lebih tipis dengan warna netral. Tapi ini hanya contoh.
- Ikon "H" juga dipakai untuk favicon, ikon PWA/apple-touch-icon, dan gambar Open Graph.

Catatan:
- File logo cukup besar (±500 KB). Tolong optimalkan (WebP/AVIF, beberapa ukuran sesuai kebutuhan tampilan) supaya website tetap ringan.
- Di ukuran sangat kecil (favicon 16–32 px), detail logo seperti tulisan di pita tidak akan terbaca. Itu wajar. Pastikan bentuk "H"-nya tetap jelas.
- Jangan mengubah bentuk atau warna logo itu sendiri.

## Warna (diambil dari logo)

Usulan palet. Silakan disesuaikan.

| Peran | Warna | Catatan |
|---|---|---|
| Emas / kuning | `#FFC21A` | Aksen, sorotan, latar badge. **Jangan untuk teks di atas putih** (kontras hanya 1,6:1). |
| Oranye terang | `#FF9A1F` | Gradasi, dekorasi |
| Oranye utama | `#F26B0F` | Warna khas brand, gradasi, elemen besar. Kontras di atas putih hanya 3:1, jadi **tidak cukup untuk teks kecil**. |
| Oranye tua | `#C2410C` | Aman untuk teks/tombol di atas putih (kontras 5,2:1) |
| Merah | `#B3260F` | Aksen kuat, aman untuk teks (6,6:1) |
| Merah marun | `#6E120B` | Judul atau teks tegas (12:1). Teks marun di atas latar emas juga terbaca baik (7,4:1). |
| Coklat sangat gelap | `#3B1A12` | Alternatif warna teks utama yang lebih hangat dari hitam |
| Abu teks sekunder | `#57534E` | Teks pendukung dan detail teknis (7,6:1) |
| Perak | `#D0D0D0` / `#E0E0E0` | Garis, border, latar netral |
| Latar | `#FFFFFF` / krem `#FFFBF5` | Latar terang yang hangat |

Gradasi khas logo (emas → oranye → merah) bagus untuk elemen yang ingin ditonjolkan, misalnya kartu Paket Tumbuh, tombol utama, atau hero. Gunakan secukupnya supaya tidak terlalu ramai.

**Kontras penting.** Banyak target pengguna memakai HP murah dengan layar redup, sering di luar ruangan. Pastikan semua teks terbaca jelas (minimal standar WCAG AA).

## Gaya bahasa

- **Seperti ngobrol dengan pemilik warung**: ramah, sopan, sederhana. Pakai "Anda".
- Kalimat pendek. Satu kalimat satu ide.
- **Hindari istilah teknis di teks utama.** Istilah teknis hanya muncul sebagai detail pelengkap (lihat `docs/01`).
- Hindari bahasa Inggris kalau ada padanan yang umum dipahami. Contoh: pakai "Daftar" bukan "Sign up", "Harga" bukan "Pricing". Istilah yang sudah umum seperti "QRIS", "HP", "Instagram", dan "online" boleh dipakai.
- Jangan pakai klaim berlebihan ("terbaik se-Indonesia", "#1"). Pakai klaim yang bisa dipertanggungjawabkan.
- Harga murah adalah kekuatan utama. Tonjolkan dengan jelas, misalnya "Mulai Rp25 ribu sebulan".

## Target pembaca

1. **Pemilik usaha kecil di daerah**: warung, toko kelontong, penjual makanan, jualan online. Banyak yang belum pernah pakai aplikasi kasir dan mungkin masih mencatat di buku. Memakai HP Android kelas bawah, internet kadang lambat. Butuh rasa aman: "ini gampang", "ini murah", "ada yang bisa ditanya".
2. **Pemilik kafe, rumah makan, toko dengan karyawan**: sudah lebih paham teknologi, peduli soal banyak cabang dan laporan.
3. **Calon klien jasa custom**: usaha yang lebih besar, perusahaan, atau orang dengan ide aplikasi. Biasanya membandingkan beberapa vendor dan ingin melihat detail teknis.

## Kesan yang ingin dibangun

Hangat, bersemangat, terpercaya, dan dekat. Website tidak boleh terlihat seperti template generik. Warna logo yang berani (emas, oranye, merah) adalah modal untuk tampil beda, tapi tetap terasa bersih dan mudah dibaca.

## Gaya UI (keputusan pemilik)

- Tema terang, **gradasi** warna logo (emas → oranye → merah), **sudut tajam** dengan potongan diagonal (meniru pilar logo "H"), dan **efek kaca/blur** secukupnya.
- Ringan dan responsif di semua perangkat. Kode terstruktur dan komponennya bisa dipakai ulang.
- **HP: menu bawah (bottom navigation), bukan menu burger.** Isinya Beranda · Fitur · **Harga** (tombol tengah menonjol) · Jasa · Masuk/Profil. Item aktif mengikuti bagian yang sedang dilihat.
- Tombol **"Daftar / Masuk" selalu dengan ikon**.

## Visual

- **Jangan pakai foto stok orang** atau gambar dari internet yang hak ciptanya tidak jelas.
- Mockup tampilan aplikasi kasir (di HP, struk, laporan) bisa dibuat sendiri dengan HTML/CSS/SVG. Ini sangat membantu orang awam membayangkan produknya.
- Ikon: gunakan set ikon open-source yang konsisten, atau buat sendiri.
