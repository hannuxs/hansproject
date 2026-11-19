"""Teks final Syarat & Ketentuan dan Kebijakan Privasi (versi 19 November 2026).

Dasar hukum yang diperiksa (semuanya masih berlaku per November 2026):
- UU 27/2022 Pelindungan Data Pribadi (+ Putusan MK 151/PUU-XXII/2024) dan
  PP 33/2026 (aturan pelaksana, berlaku 16 Januari 2027).
- UU 8/1999 Perlindungan Konsumen, terutama larangan klausula baku (Pasal 18).
- UU 28/2007 KUP Pasal 28 ayat (11): catatan & dokumen dasar disimpan 10 tahun.
- UU ITE & PP 71/2019 (penyelenggara sistem elektronik), PP 80/2019 (PMSE).
- Google API Services User Data Policy (login Google).

Teks ini disalin ke database saat instalasi (seed) dan oleh migrasi
content/0005. Setelah itu pemilik mengubahnya lewat panel (Halaman Legal).
Bila isinya berubah penting, ubah juga "versi Syarat & Ketentuan" di Pengaturan
Umum supaya semua pelanggan diminta menyetujui ulang.
"""
from __future__ import annotations

TERMS_TITLE = "Syarat & Ketentuan"
PRIVACY_TITLE = "Kebijakan Privasi"

TERMS_BODY = """Syarat & Ketentuan ini adalah perjanjian antara **HANS Project** ("kami") dan Anda sebagai pengguna layanan di hansproject.app ("Anda"). Ketentuan ini berlaku untuk website hansproject.app, akun pelanggan, **Aplikasi Kasir** (Paket Tunas dan Paket Tumbuh, termasuk alamat toko seperti namatoko.hansproject.app), dan **Jasa Bikin Website & Aplikasi** (Paket Rimba).

Perjanjian ini berlaku sejak Anda mencentang persetujuan saat pertama kali masuk ke akun. Cara kami memakai dan melindungi data diatur dalam [Kebijakan Privasi](/kebijakan-privasi/) yang menjadi bagian dari ketentuan ini.

## 1. Siapa yang boleh memakai layanan
- Anda berusia minimal 18 tahun dan cakap melakukan perbuatan hukum.
- Bila Anda mendaftar atas nama usaha, Anda menyatakan berwenang mewakili usaha tersebut.
- Data diri yang Anda isi (nama, nomor HP, nama usaha) benar dan Anda perbarui bila berubah.

## 2. Akun Anda
- Daftar dan masuk hanya dengan akun Google. Kami tidak pernah menerima atau menyimpan password Google Anda.
- Jaga keamanan akun Google Anda. Semua kegiatan lewat akun Anda menjadi tanggung jawab Anda, kecuali terjadi karena kesalahan kami.
- Akun tidak boleh dipindahtangankan, dijual, atau dipakai bersama orang lain tanpa persetujuan kami.
- Bila Anda menduga akun disalahgunakan, segera kabari kami lewat DM Instagram.

## 3. Layanan kami
### Aplikasi Kasir (Paket Tunas & Paket Tumbuh)
- Aplikasi kasir siap pakai dengan langganan bulanan. Aplikasinya sama untuk semua pelanggan.
- Isi dan batas setiap paket (jumlah outlet, tempat simpan, akun kasir per outlet, revisi tampilan, permintaan fitur) mengikuti yang tercantum di website saat Anda memesan.
- Setiap toko mendapat **alamat toko** (contoh: warungbudi.hansproject.app) yang Anda pilih saat memesan. Alamat ini adalah bagian dari domain HANS Project. Anda berhak memakainya selama berlangganan. Kami bisa menolak nama yang menyesatkan, melanggar hak orang lain, atau tidak pantas.
- **Akun kasir** (nama pengguna dan PIN) dibuat oleh pemilik toko. Pemilik toko bertanggung jawab atas siapa yang diberi akun kasir dan atas semua transaksi yang dicatat dengan akun tersebut.
- Aplikasi membutuhkan koneksi internet. Perangkat (HP, laptop, printer) dan koneksi internet disediakan sendiri oleh Anda.
- Cara bayar yang dicatat di kasir (Tunai, QRIS, Transfer) hanya catatan. Kami tidak menerima, menyimpan, atau menyalurkan uang hasil penjualan toko Anda.
- Struk dicetak lewat fitur cetak bawaan browser.

### Jasa Bikin Website & Aplikasi (Paket Rimba)
- Konsultasi awal gratis.
- Ruang lingkup, fitur, biaya pembuatan, jadwal, cara pembayaran, revisi, dan kepemilikan hasil kerja dituangkan dalam **kesepakatan tertulis** tersendiri. Bila ada yang berbeda, kesepakatan tertulis itu yang berlaku.
- Biaya bulanan untuk menjaga website/aplikasi tetap jalan, dirawat, dan dibantu kalau ada masalah mengikuti harga di website saat kesepakatan dibuat.
- Biaya pendaftaran akun Play Store (Google Play Developer) dan App Store (Apple Developer Program) ditanggung klien.

## 4. Harga, pesanan, dan pembayaran
- Harga dalam Rupiah sesuai yang tercantum di website saat Anda memesan. Harga itu tercatat di pesanan Anda.
- Alur pesanan: pilih paket, tekan **Pesan Sekarang**, bayar lewat transfer bank atau scan QRIS, kirim foto bukti bayar di halaman pesanan, lalu kami cek dan aktifkan.
- Bayar hanya ke rekening atau QRIS yang tampil di halaman pesanan Anda, atau yang kami tulis di **Catatan dari kami** pada pesanan tersebut. Kami tidak pernah meminta pembayaran ke rekening lain lewat pesan pribadi.
- Biaya transfer antarbank (bila ada) ditanggung pengirim.
- Tidak ada penarikan otomatis dan tidak ada perpanjangan otomatis. Langganan hanya bertambah bila Anda membuat pesanan perpanjangan dan membayarnya.
- Perubahan harga diumumkan di website paling lambat 14 hari sebelum berlaku, dan hanya berlaku untuk perpanjangan berikutnya. Masa aktif yang sudah Anda bayar tidak terpengaruh.

## 5. Masa aktif, perpanjangan, dan pindah paket
- Setiap pembayaran Aplikasi Kasir berlaku 1 bulan sejak diaktifkan.
- Perpanjangan menambah 1 bulan dari tanggal masa aktif habis. Bila masa aktif sudah habis, dihitung dari tanggal pembayaran perpanjangan dikonfirmasi.
- Anda bisa **pindah paket** saat memperpanjang. Bila pindah ke paket dengan jumlah outlet lebih sedikit, outlet terbaru di atas batas dinonaktifkan. Datanya tetap ada.
- **Ganti alamat toko** bisa diajukan saat memperpanjang dan perlu persetujuan kami. Setelah diganti, alamat lama tidak bisa dibuka lagi.
- Tambahan outlet atau tempat simpan bisa dibeli dengan biaya bulanan sesuai daftar harga di website.

## 6. Bila langganan tidak diperpanjang
- **Hari ke-1 sampai ke-7** setelah masa aktif habis: masa tenggang. Kasir masih bisa dipakai, dengan peringatan.
- **Setelah hari ke-7**: kasir terkunci. Pemilik toko masih bisa melihat dan mengunduh laporan.
- **30 hari setelah masa aktif habis**: semua data toko (barang, outlet, akun kasir, transaksi) **dihapus permanen dan tidak bisa dikembalikan**.
- Bila Anda memperpanjang sebelum data dihapus, semua data kembali seperti semula.
- Unduh laporan Anda sebelum data dihapus bila Anda ingin menyimpannya.

## 7. Pembatalan dan pengembalian dana
- **Belum bayar**: pesanan bisa dibatalkan kapan saja di halaman pesanan.
- **Sudah bayar tetapi belum diaktifkan**: Anda bisa membatalkan dan uang dikembalikan penuh.
- **Cara mengajukan refund**: setelah pesanan yang sudah dibayar dibatalkan (oleh Anda atau oleh kami), buka pesanan itu di menu **Pesanan**, lalu isi rekening tujuan atas nama Anda di bagian **Refund**. Status dan bukti transfer refund tampil di halaman yang sama.
- **Kelebihan bayar** atau **salah bayar**: selisihnya kami kembalikan.
- **Sudah aktif**: Anda bisa berhenti kapan saja dengan tidak memperpanjang. Aplikasi tetap bisa dipakai sampai masa aktif habis. Sisa masa aktif dikembalikan secara proporsional (dihitung per hari) bila:
  - layanan tidak bisa dipakai karena kesalahan kami dan tidak kami perbaiki dalam 3 x 24 jam setelah Anda melapor;
  - kami menghentikan layanan bukan karena kesalahan Anda; atau
  - Anda tidak setuju dengan perubahan Syarat & Ketentuan yang mulai berlaku sebelum masa aktif Anda habis (lihat bagian 15).
- Permintaan pengembalian dana lain kami tanggapi sesuai peraturan perlindungan konsumen. Ketentuan ini tidak mengurangi hak Anda menurut Undang-Undang Perlindungan Konsumen.
- Pengembalian dana dikirim lewat transfer ke rekening atas nama Anda, paling lambat 7 hari kerja setelah disetujui.
- Pembatalan dan pengembalian dana Paket Rimba mengikuti kesepakatan tertulisnya.

## 8. Data toko Anda
- Data yang Anda masukkan ke Aplikasi Kasir (barang, harga, outlet, akun kasir, transaksi, laporan, pengaturan struk) adalah **milik Anda**.
- Untuk data tersebut, Anda adalah **pengendali data** dan kami adalah **prosesor data**. Kami memprosesnya hanya untuk menjalankan aplikasi sesuai pemakaian Anda, sesuai ketentuan ini dan Kebijakan Privasi.
- Kami tidak menjual data toko Anda, tidak memakainya untuk iklan, dan tidak membukanya kecuali untuk membantu permintaan Anda, menjaga keamanan sistem, atau memenuhi kewajiban hukum.
- Petugas kami yang bisa mengakses sistem wajib menjaga kerahasiaan data.
- Kami tidak memakai pihak lain untuk memproses data toko Anda. Bila kelak berubah, kami beri tahu Anda lebih dulu.
- Kami membantu Anda bila ada permintaan dari orang yang datanya tercatat di toko Anda, dan memberi tahu Anda tanpa ditunda bila terjadi kebocoran data toko Anda.
- Anda bertanggung jawab atas kebenaran dan keabsahan data yang Anda masukkan. Jangan menyimpan data pribadi pembeli di aplikasi kasir. Bila Anda memasukkan data pribadi orang lain, misalnya nama karyawan sebagai nama pengguna kasir, Anda wajib punya dasar yang sah untuk itu.
- Laporan bisa Anda unduh kapan saja selama data belum dihapus.
- Di akhir langganan, data toko dihapus sesuai bagian 6.

## 9. Pemakaian yang dilarang
Anda dilarang memakai layanan untuk:
- menjual atau mencatat barang/jasa yang melanggar hukum, penipuan, atau pencucian uang;
- menyerang, menguji celah keamanan tanpa izin tertulis dari kami, membebani sistem secara berlebihan, atau mengambil data secara otomatis (scraping);
- menyebarkan program jahat, menyamar menjadi pihak lain, atau menjual kembali akses ke layanan;
- memakai nama toko, alamat toko, logo, atau isi yang melanggar hak orang lain, menyesatkan, atau tidak pantas;
- memproses data pribadi orang lain secara melanggar hukum.

## 10. Ketersediaan layanan dan gangguan
- Kami berusaha agar layanan bisa dipakai 24 jam setiap hari, tetapi tidak ada sistem yang bebas gangguan.
- Perawatan sistem yang sudah direncanakan kami umumkan lebih dulu bila memungkinkan.
- Bila Aplikasi Kasir tidak bisa dipakai lebih dari 24 jam berturut-turut karena kesalahan sistem kami, masa aktif toko Anda kami tambah sesuai lamanya gangguan (dibulatkan ke atas menjadi hari penuh).
- Gangguan karena perangkat atau internet Anda, atau karena layanan pihak lain (misalnya Google atau bank), di luar kendali kami.
- Keadaan kahar (bencana alam, gangguan listrik atau internet yang meluas, kebijakan pemerintah, serangan yang di luar kemampuan wajar untuk dicegah): kami tidak bertanggung jawab atas keterlambatan karena hal tersebut, tetapi kami tetap berusaha memulihkan layanan secepatnya dan memberi kabar.

## 11. Keamanan
- Kami menjaga keamanan sistem antara lain dengan HTTPS, penyimpanan PIN dan token login dalam bentuk acak (hash), verifikasi dua langkah untuk pengelola, dan backup rutin.
- Anda wajib merahasiakan akun Google Anda dan PIN kasir, serta segera memberi tahu kami bila ada yang mencurigakan.

## 12. Hak kekayaan intelektual
- Aplikasi, tampilan, kode, dan merek HANS Project milik kami. Selama berlangganan, Anda mendapat izin terbatas untuk memakainya bagi usaha Anda. Izin ini tidak eksklusif dan tidak bisa dipindahtangankan.
- Data, logo, dan isi milik Anda tetap milik Anda. Anda mengizinkan kami menampilkannya hanya untuk menjalankan layanan, misalnya di struk atau halaman toko Anda.
- Kepemilikan hasil kerja Paket Rimba mengikuti kesepakatan tertulisnya.

## 13. Tanggung jawab
- Kami bertanggung jawab atas kerugian yang langsung disebabkan oleh kesalahan atau kelalaian kami dalam memberikan layanan.
- Kami tidak bertanggung jawab atas kerugian karena kesalahan pemakaian di pihak Anda (misalnya salah input harga, selisih uang kas, atau PIN yang dibagikan), perangkat atau internet Anda, atau layanan pihak lain.
- Ganti rugi dari kami paling banyak sebesar biaya yang Anda bayar untuk layanan terkait dalam 3 bulan terakhir sebelum kejadian. Batas ini tidak berlaku bila kerugian terjadi karena kesengajaan atau kelalaian berat kami.
- Tidak ada ketentuan di sini yang menghapus atau mengurangi hak Anda menurut Undang-Undang Perlindungan Konsumen, Undang-Undang Pelindungan Data Pribadi, atau peraturan lain yang berlaku.

## 14. Penangguhan dan penghentian
- Kami bisa menangguhkan akun atau toko bila ada pemakaian yang dilarang, ancaman keamanan, atau perintah hukum. Untuk pelanggaran yang tidak membahayakan, kami beri tahu Anda dulu dan beri waktu 7 hari untuk memperbaikinya. Untuk ancaman serius atau kegiatan melanggar hukum, penangguhan bisa langsung dilakukan, lalu kami beri tahu Anda.
- Anda bisa berhenti kapan saja dan meminta akun Anda dihapus lewat DM Instagram. Penghapusan mengikuti Kebijakan Privasi.
- Bila kami menghentikan suatu layanan seluruhnya, kami umumkan paling lambat 30 hari sebelumnya. Anda punya waktu untuk mengunduh data, dan sisa masa aktif dikembalikan secara proporsional.

## 15. Perubahan Syarat & Ketentuan
- Ketentuan ini bisa berubah, misalnya karena perubahan layanan atau peraturan. Perubahan diumumkan di website dan di akun Anda paling lambat 14 hari sebelum berlaku, kecuali peraturan mewajibkan lebih cepat.
- Untuk perubahan penting, Anda akan diminta menyetujui ulang saat masuk berikutnya.
- Perubahan tidak mengikat masa aktif yang sudah Anda bayar tanpa persetujuan Anda. Bila Anda tidak setuju, Anda bisa berhenti dan mendapat pengembalian sisa masa aktif secara proporsional.

## 16. Hukum yang berlaku dan penyelesaian masalah
- Ketentuan ini tunduk pada hukum Republik Indonesia dan dibuat dalam Bahasa Indonesia.
- Bila ada masalah, hubungi kami dulu. Kami tanggapi paling lambat 3 hari kerja dan berusaha menyelesaikannya secara musyawarah dalam 30 hari.
- Bila tidak selesai, Anda bisa menempuh penyelesaian melalui Badan Penyelesaian Sengketa Konsumen (BPSK) atau pengadilan negeri yang berwenang sesuai peraturan yang berlaku.

## 17. Kontak
- Semua keperluan: **DM Instagram [@hansproject.app](https://www.instagram.com/hansproject.app)**.
- Bila sudah punya akun, Anda juga bisa memakai menu **Chat** di akun Anda. Obrolan yang sudah kami tandai selesai tidak bisa dibalas lagi, tetapi tetap tersimpan di riwayat; untuk keperluan baru, buka obrolan baru.
- Waspadai akun yang mengatasnamakan HANS Project. Akun Instagram resmi kami hanya @hansproject.app."""

PRIVACY_BODY = """Kebijakan Privasi ini menjelaskan data pribadi apa yang kami kumpulkan, untuk apa, berapa lama disimpan, dan apa saja hak Anda. Kebijakan ini disusun mengikuti Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi beserta peraturan pelaksananya.

**HANS Project** ("kami") adalah **pengendali data** untuk data pengunjung website dan data akun pelanggan di hansproject.app. Untuk data yang dimasukkan pemilik toko ke Aplikasi Kasir, kami adalah **prosesor data** yang bekerja atas nama pemilik toko (lihat bagian 10).

## 1. Ringkasnya
- Kami hanya mengumpulkan data yang dibutuhkan untuk menjalankan layanan.
- Tidak ada cookie pelacak, alat analitik pihak lain, atau iklan.
- Kami tidak menjual atau menyewakan data Anda.
- Data toko di Aplikasi Kasir adalah milik pemilik toko.
- Anda bisa meminta salinan, perbaikan, atau penghapusan data lewat DM Instagram @hansproject.app.

## 2. Data yang kami kumpulkan
### Saat Anda membuka website (tanpa akun)
- Alamat IP Anda dipakai server untuk mengirim halaman dan menjaga keamanan. Alamat IP **tidak disimpan apa adanya**. Untuk pembatasan percobaan dan catatan keamanan, IP diubah menjadi kode acak satu arah yang kuncinya berganti setiap hari.
- Klik tombol "DM Instagram" dihitung hanya sebagai angka per hari, tanpa data siapa yang mengklik.
- Pilihan "Tampilkan istilah teknis" disimpan di browser Anda sendiri dan tidak dikirim ke kami.

### Saat Anda punya akun
- **Dari Google**, setelah Anda menyetujuinya di halaman Google: ID akun Google, alamat email, status verifikasi email, dan nama. Password Google Anda tidak pernah kami terima. Foto profil Google tidak kami simpan.
- **Dari Anda**: nomor HP dan nama usaha. Nama juga bisa Anda ubah.
- **Pesanan**: paket, harga, status, alamat toko yang dipilih, catatan dari kami, dan foto bukti bayar. Saat diunggah, foto diproses ulang sehingga data tersembunyi di dalamnya (misalnya lokasi dan merek kamera) terhapus.
- **Chat**: pesan dan gambar yang Anda kirim lewat menu Chat, beserta balasan kami. Gambar diproses ulang sehingga data tersembunyi di dalamnya terhapus, dan disimpan secara pribadi tanpa alamat publik.
- **Refund**: nama bank atau dompet digital, nomor rekening, dan nama pemilik rekening yang Anda isi saat mengajukan pengembalian dana, beserta bukti transfer dari kami.
- **Bukti persetujuan**: tanggal versi Syarat & Ketentuan yang Anda setujui dan waktunya.
- **Sesi login**: kode login dan waktu terakhir aktif. Kode login disimpan dalam bentuk acak (hash).

### Saat Anda memakai Aplikasi Kasir
- **Data toko**: nama dan alamat toko, pengaturan struk, barang, harga, kategori, outlet, akun kasir (nama pengguna dan PIN yang disimpan dalam bentuk acak), dan transaksi (barang, jumlah, total, diskon, cara bayar, nama pengguna kasir, dan waktu).
- **Login kasir**: kode sesi, waktu terakhir aktif, dan jumlah PIN salah untuk penguncian sementara.
- Aplikasi kasir tidak meminta data pribadi pembeli di toko.

## 3. Untuk apa dan apa dasarnya
- **Membuat dan menjalankan akun, memproses pesanan dan refund, mengaktifkan dan menjalankan Aplikasi Kasir, menampilkan pengumuman layanan di Dashboard, serta melayani chat Anda.** Dasarnya: pelaksanaan perjanjian dengan Anda (Syarat & Ketentuan).
- **Menyimpan catatan pesanan, bukti bayar, dan data refund.** Dasarnya: kewajiban hukum pencatatan untuk perpajakan.
- **Menjaga keamanan sistem**, misalnya membatasi percobaan login, mencatat kejadian keamanan dengan IP yang sudah disamarkan, dan mencegah penyalahgunaan. Dasarnya: kewajiban hukum penyelenggara sistem elektronik untuk menjaga sistemnya aman, dan kepentingan yang sah dengan data seminimal mungkin.
- **Memenuhi permintaan hak Anda, menyelesaikan sengketa, dan mematuhi perintah hukum.** Dasarnya: kewajiban hukum.
- **Data toko** diproses atas nama dan sesuai pemakaian pemilik toko.

Centang persetujuan saat pertama masuk adalah persetujuan Anda atas Syarat & Ketentuan dan pernyataan bahwa Anda sudah membaca kebijakan ini. Kami tidak memakai data Anda untuk pemasaran, tidak mengirim pesan promosi, dan tidak membuat keputusan otomatis atau profil tentang Anda.

## 4. Cookie dan penyimpanan di browser
Semua cookie di bawah ini diperlukan agar layanan berjalan. Tidak ada cookie pihak lain.
- **hp_akun**: menjaga Anda tetap masuk. Berlaku 30 hari sejak terakhir aktif, dan dihapus saat Anda menekan Keluar.
- **hp_masuk**: penanda untuk mengganti tombol "Daftar / Masuk" menjadi "Profil". Tidak berisi data rahasia.
- **hp_token**: pengaman formulir dari pemalsuan permintaan.
- **hp_oauth**: dipakai selama proses masuk dengan Google, paling lama 10 menit.
- **hp_kasir**: menjaga kasir tetap masuk di alamat toko. Berlaku 7 hari sejak terakhir aktif dan hanya terkirim ke alamat toko itu.
- **Penyimpanan browser**: pilihan "Tampilkan istilah teknis", dan keranjang kasir sementara yang hilang saat tab ditutup.

## 5. Siapa saja yang bisa menerima data
- **Pengelola HANS Project**, hanya bila perlu. Akses masuk ke panel pengelola dilindungi verifikasi dua langkah.
- **Google**, saat Anda masuk dengan Google. Proses masuk terjadi di halaman Google dan tunduk pada kebijakan privasi Google. Kami hanya menerima data yang disebut di bagian 2. Pemakaian data yang kami terima dari Google mengikuti Google API Services User Data Policy, termasuk ketentuan Limited Use.
- **Bank atau penyedia QRIS Anda**, saat Anda membayar. Pembayaran diproses oleh bank atau penyedia tersebut sesuai kebijakan mereka. Kami hanya melihat bukti bayar yang Anda kirim.
- **Instagram (Meta)**, bila Anda menghubungi kami lewat DM. Percakapan itu tunduk pada kebijakan privasi Instagram.
- **Instansi berwenang**, hanya bila diwajibkan peraturan atau perintah hukum.
- **Siapa pun yang memegang kode QR / tautan bukti pesanan Anda** (misalnya dari dokumen yang Anda cetak atau bagikan) bisa membuka halaman cek keaslian. Halaman itu hanya menampilkan kode, layanan, status, tanggal, rincian harga, serta nama dan nama usaha yang **disamarkan**. Tautannya memakai kode acak yang tidak bisa ditebak dan tidak muncul di mesin pencari.
- Bila usaha HANS Project beralih ke pihak lain, kami memberi tahu Anda sebelum data dipindahkan.

Kami tidak menjual, menyewakan, atau memberikan data Anda untuk kepentingan pemasaran pihak lain.

## 6. Tempat penyimpanan data
Website dan database berjalan di server yang dikelola sendiri oleh HANS Project di Indonesia. Kami tidak memindahkan data Anda ke luar negeri. Masuk dengan Google terjadi di sistem Google, yang tunduk pada kebijakan Google.

## 7. Berapa lama data disimpan
- **Akun dan data diri**: selama akun Anda ada. Dihapus bila Anda meminta akun dihapus.
- **Sesi login**: 30 hari sejak terakhir aktif. Sesi kasir 7 hari sejak terakhir aktif.
- **Chat** (termasuk obrolan yang sudah selesai dan gambarnya) dan **bukti persetujuan**: selama akun Anda ada.
- **Pesanan yang belum dibayar atau dibatalkan tanpa pembayaran**: ikut dihapus saat akun dihapus.
- **Pesanan yang sudah dibayar (termasuk yang dibatalkan lalu di-refund), bukti bayarnya, dan data refund-nya**: 10 tahun sejak pesanan dibuat, sesuai kewajiban penyimpanan catatan perpajakan, lalu dihapus otomatis. Bila akun dihapus lebih dulu, yang tetap disimpan hanya catatan pesanan itu, bukti bayarnya, serta nama, email, nomor HP, dan nama usaha pemesan.
- **Data toko di Aplikasi Kasir**: selama berlangganan. Dihapus permanen 30 hari setelah masa aktif habis tanpa perpanjangan, atau saat akun pemiliknya dihapus.
- **Catatan keamanan**: memakai IP yang sudah disamarkan. File catatan dibatasi ukurannya dan yang lama terhapus otomatis.
- **Cadangan (backup)**: disimpan paling lama 60 hari. Data yang sudah dihapus dari sistem utama ikut hilang saat cadangan lama terhapus, dan tidak dipakai untuk keperluan lain selama menunggu.

## 8. Keamanan data
- Semua halaman memakai HTTPS (terenkripsi).
- Kode login dan PIN kasir disimpan dalam bentuk acak (hash), sehingga tidak bisa dibaca siapa pun.
- Foto bukti bayar disimpan secara pribadi tanpa alamat publik. Hanya Anda dan pengelola HANS Project yang bisa membukanya.
- Pengelola masuk dengan verifikasi dua langkah, dan hak aksesnya dibatasi.
- Data dicadangkan setiap hari dan sistem diperbarui secara berkala.

Bila terjadi kebocoran atau kegagalan pelindungan yang menyangkut data Anda, kami memberi tahu Anda secara tertulis (lewat halaman akun dan kontak yang Anda berikan) dan lembaga yang berwenang di bidang pelindungan data pribadi paling lambat **3 x 24 jam**. Pemberitahuan memuat data apa yang terdampak, kapan dan bagaimana terjadi, serta langkah penanganan dan pemulihan.

## 9. Hak Anda
Sesuai Undang-Undang Pelindungan Data Pribadi, Anda berhak:
- mendapat informasi tentang pemrosesan data Anda;
- mengakses dan mendapat salinan data Anda;
- melengkapi, memperbarui, dan memperbaiki data Anda;
- meminta pemrosesan dihentikan, dan data dihapus atau dimusnahkan;
- meminta pemrosesan ditunda atau dibatasi;
- menarik persetujuan, bila ada pemrosesan yang berdasarkan persetujuan;
- mendapat data Anda dalam format yang bisa dibaca sistem dan memindahkannya ke penyedia lain;
- mengajukan keberatan atas keputusan yang sepenuhnya otomatis (kami tidak membuat keputusan seperti itu);
- mengadu kepada lembaga yang berwenang dan menuntut ganti rugi sesuai peraturan.

**Cara memakai hak Anda:**
- Data diri bisa Anda ubah sendiri di **Profil → Ubah data diri**. Laporan toko bisa Anda unduh sendiri dalam format CSV di menu **Laporan**.
- Permintaan lain kirim lewat **DM Instagram @hansproject.app**. Untuk memastikan permintaan benar dari pemilik akun, kami bisa meminta Anda mengirim konfirmasi lewat menu **Chat** dari akun Anda.
- Permintaan akses, salinan, perbaikan, penghentian, penundaan, atau pembatasan kami penuhi paling lambat 3 x 24 jam setelah identitas Anda terverifikasi. Penghapusan kami kabarkan kepada Anda setelah selesai.
- Ada data yang wajib tetap kami simpan karena peraturan, misalnya catatan pesanan untuk perpajakan. Bila begitu, kami jelaskan alasannya.
- Tidak ada biaya untuk permintaan ini.

## 10. Data toko: peran kami sebagai prosesor
- Untuk data di dalam toko Anda (termasuk nama pengguna kasir), pemilik toko adalah pengendali data, dan kami memprosesnya hanya untuk menjalankan aplikasi sesuai Syarat & Ketentuan bagian 8.
- Bila ada permintaan tentang data di sebuah toko (misalnya dari karyawan toko), kami teruskan kepada pemilik toko dan membantu pemilik toko menanggapinya.

## 11. Anak
Layanan ini untuk usia 18 tahun ke atas. Kami tidak dengan sengaja memproses data anak. Bila kami mengetahui ada akun milik anak, akun itu kami hapus.

## 12. Perubahan kebijakan
Bila kebijakan ini berubah, kami memberi tahu Anda di website dan di akun Anda paling lambat 14 hari sebelum perubahan berlaku. Untuk perubahan penting, Anda akan diminta menyetujui ulang saat masuk berikutnya. Tanggal berlaku versi ini tercantum di bagian atas halaman.

## 13. Kontak
Pengendali data: **HANS Project** (hansproject.app). Pertanyaan atau permintaan tentang data pribadi: **DM Instagram [@hansproject.app](https://www.instagram.com/hansproject.app)**, atau menu **Chat** bila Anda sudah punya akun."""

LEGAL_PAGES = [
    ("syarat-ketentuan", TERMS_TITLE, TERMS_BODY),
    ("kebijakan-privasi", PRIVACY_TITLE, PRIVACY_BODY),
]
