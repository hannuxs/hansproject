# 07 — Sistem Informasi Manajemen (SIM): bidang RT, RW, Kelurahan/Desa, Kecamatan — Fase 1

> **Penamaan (22 November 2026):** SIM = *Sistem Informasi Manajemen*, solusi umum untuk instansi & organisasi (nanti juga klinik/rumah sakit, sekolah, organisasi). Bidang pertama: pemerintahan & kemasyarakatan. Jangan menyebutnya "SIM". Di menu pelanggan satu unit disebut **instansi** (model `Wilayah`). Paket mengikuti pola kasir: **SIM Tunas** & **SIM Tumbuh** (bukan paket per tingkat); harga Rp0 = "Segera diumumkan".

Rancangan dan keputusan pemilik untuk SIM. Petunjuk pemakaian ada di `README.md`
bagian 4 (“SIM”).

---

## Latar belakang (survei pemilik ke ketua RT/RW)

1. Data warga berupa **fotokopi KK & KTP** di map, sulit dicari. Data kertas yang sudah ada
   harus bisa dipakai tanpa mengumpulkan ulang: *“ketua RT memotret KK, gambar tersimpan +
   teks terekstrak dengan format rapi”*.
2. Senin–Jumat pengurus bekerja di tempat lain. Warga perlu **minta surat online**, dan
   pengurus perlu **pegangan format surat online** untuk diketik & dicetak di mana saja
   (blanko kertas ada di rumah). Format harus fleksibel.
3. RT, RW, kelurahan, kecamatan **saling terhubung** seperti SIM.

## Keputusan pemilik (22 November 2026)

| Topik | Keputusan |
|---|---|
| Mesin OCR | **Tesseract lokal** (gratis, foto tidak keluar server). Hasil = draf yang diperiksa pengurus |
| Bergabung & terhubung | **Dari bawah + undangan**: RT/RW/kelurahan mendaftar sendiri; wilayah atas membagikan **kode undangan** dan **menyetujui** wilayah di bawahnya. Hanya satu tingkat tepat di atasnya (RT→RW→Kelurahan→Kecamatan) |
| Harga | **Paket langganan** memakai alur pesanan & aktivasi admin yang sama dengan kasir. Paket **SIM Tunas** & **SIM Tumbuh** tampil dengan harga Rp0 ("Segera diumumkan", belum bisa dipesan) sampai pemilik mengisi harga di panel. Batas scan OCR per bulan per paket (`Package.scan_limit`) diterapkan di menu Scan |
| Warga | **Tanpa login**: ajukan surat di halaman wilayah, dapat **kode lacak** |
| Masa aktif | Sama dengan kasir: tenggang 7 hari → terkunci (pengajuan online tutup, data hanya baca) → **dihapus permanen 30 hari** setelah habis |

## Alamat

```
/akun/sim/                     → daftar wilayah milik pengurus (login Google)
/akun/sim/<kode>/...           → dashboard pengurus (lihat README)
/w/<kode>/                     → halaman warga: pengumuman, ajukan surat, lacak
/w/<kode>/ajukan/<jenis>/      → formulir pengajuan (tanpa login)
/surat/lacak/<kode-lacak>/     → status surat (+ cetak bila diizinkan pengurus)
/surat/cek/<kode-keaslian>/    → halaman QR keaslian (nama & NIK tersamar)
```

`<kode>` wilayah = 10 karakter acak. Kode lacak & kode keaslian = `secrets.token_urlsafe(18)`.
Semua halaman warga `no-store` + `noindex` dan diblokir di `robots.txt`.

## Data (tabel `hp_sim_*`)

| Model | Isi |
|---|---|
| `Wilayah` | pemilik (Member), tingkat, nomor RT/RW, nama, konteks alamat (RW, kelurahan, kecamatan, kota, provinsi), sekretariat, ketua & jabatan & NIP, gambar tanda tangan/cap (pribadi), format nomor surat, terima online, warga boleh cetak, **kode halaman warga**, **kode undangan**, `parent` & permintaan bergabung, paket & masa aktif & status & catatan admin |
| `KartuKeluarga`, `Penduduk` | data warga per wilayah; status warga aktif/pindah/meninggal (mutasi) |
| `DokumenScan` | foto KK/KTP/dokumen (pribadi), draf data terstruktur hasil baca (+ teks mentah untuk pemeriksaan), status baca |
| `JenisSurat` | format surat per wilayah: judul, kode nomor, isi dengan `{isian}`, kolom tambahan (JSON), perlu “diketahui” atas, bisa online |
| `Surat` | pengajuan/surat: data isian (JSON), isi final, nomor urut per tahun, penanda tangan, status, sumber (online/langsung), status “mengetahui” wilayah atas, kode lacak, kode keaslian, IP-hash |
| `Pengumuman` | per wilayah, bisa diteruskan ke semua wilayah di bawahnya, jadwal tampil |

`members.Order` ditambah `details` (data wilayah yang dipesan, JSON) dan `wilayah` (FK).

## Aturan penting

- **Isolasi wilayah**: dashboard mengambil wilayah lewat `Wilayah.objects.owned_by(member)`, lalu semua
  data lewat relasi (`wilayah.kk_set`, `wilayah.surat_set`, …). Diuji di `tests/test_sim.py`.
- **Wilayah atas tidak melihat data pribadi warga** wilayah di bawahnya: hanya angka rekap dan surat yang
  dikirim untuk “diketahui”. Panel pengelola juga tidak menampilkan data warga.
- **Isi surat** diisi dengan `apps/content/templating.fill` (bukan `str.format`) dan dicetak sebagai teks
  ter-escape. Baris `Label : isi` dirapikan menjadi tabel. Isian kosong dicetak sebagai titik-titik.
- **Nomor surat** otomatis per tahun dengan kunci baris wilayah (`select_for_update`). Format bisa diubah:
  `{nomor} {kode_surat} {wilayah} {bulan} {bulan_romawi} {tahun}`.
- **Pengajuan warga**: NIK wajib 16 angka, kotak persetujuan wajib, honeypot, rate limit 5/jam per IP-hash
  dan 150/hari per wilayah. NIK dicocokkan dengan data warga **hanya untuk pengurus** (tidak ada bocoran
  “NIK terdaftar/tidak” ke publik).
- **Pembaca foto (utama)**: `apps/sim/ocr_foto.py` = PaddleOCR PP-OCRv4 (RapidOCR + ONNX Runtime) + OpenCV,
  paket opsional `requirements/ocr.txt` (CPU) atau `requirements/ocr-gpu.txt` (GPU NVIDIA: onnxruntime-gpu 1.26 =
  build CUDA 12 terakhir, cuDNN 9.10; dipasang `--no-deps` karena bentrok dengan onnxruntime CPU). `pasang-ocr.bat`
  memilih varian otomatis dan memeriksa dengan `scripts/ocr_check.py`; `update.bat` memperbarui varian yang sama.
  Saat dimuat, `_engine()` memastikan sesi benar-benar memakai CUDA (ONNX Runtime diam-diam pindah ke CPU bila
  driver/cuDNN bermasalah). Ukuran di RTX 2050: baca 1 foto KK ±1,5 dtk (GPU) vs ±2,6 dtk (CPU), hasil identik. Alur KK: sudut tabel dicari dari titik
  persilangan garis atau kontur jaring garis (beberapa calon, dipilih yang menghasilkan tabel 10 + 9 kolom utuh),
  perspektif diluruskan & halaman diputar mendatar, satu kali baca seluruh halaman, cek terbalik (label kepala KK
  harus di atas tabel), grid dari gambar "garis saja" (morfologi), teks dipasangkan ke sel, sel penting yang kosong
  dibaca ulang dari potongannya, spasi yang hilang dipulihkan (teks berspasi di KK yang sama, daftar kata nama/tempat
  umum, dan posisi spasi dari Tesseract untuk teks panjang). `read_text` memilih hasil terlengkap (`kk_score`) bila
  PaddleOCR lemah lalu Tesseract juga dicoba.
- **OCR Tesseract (cadangan)**: `apps/sim/ocr.py` memanggil Tesseract tanpa shell, maks. 40 detik per panggilan, satu dokumen
  sekaligus (beberapa kolom dibaca paralel, `TESSERACT_WORKERS`), pixel dicek sebelum dibuka.
  KK dibaca **mengikuti struktur tabel Dukcapil**: gambar diluruskan, garis tabel dideteksi dari proyeksi
  piksel (kolom = konsensus garis di banyak baris), tiap kolom dipotong & dibaca terpisah (NIK & tanggal
  hanya angka, dibaca 3 skala lalu divoting), nilai dicocokkan ke ejaan baku (pendidikan, pekerjaan,
  status perkawinan "tercatat", hubungan, golongan darah). No. KK (huruf segmen) dibaca beberapa variasi.
  Kepala KK dibaca per baris (label kiri & kanan). Bila tabel tidak terdeteksi, dipakai pembacaan teks biasa.
  Hasilnya **langsung mengisi formulir KK + anggota**; pengurus mencocokkan dengan gambar lalu menyimpan
  (tidak pernah tersimpan otomatis). Teks mentah OCR tidak ditampilkan.
- **Kepala keluarga** tidak diketik: `KartuKeluarga.kepala_nama` diisi otomatis dari anggota yang
  hubungannya "Kepala Keluarga" (`services.sync_kepala`); satu KK hanya boleh punya satu kepala keluarga.
- **Hapus surat**: surat terbit/ditolak/dibatalkan bisa dihapus pengurus; QR & kode lacaknya langsung
  tidak berlaku. Nomor urut tidak dipakai ulang (`Wilayah.nomor_terakhir`/`nomor_tahun`). Unggah maks. 6 MB (`SIM_SCAN_MAX_BYTES`); `static/js/sim.js` mengecilkan foto
  di HP sebelum dikirim. Gambar di-re-encode (EXIF/lokasi dibuang) dan disimpan di `PRIVATE_MEDIA_ROOT/sim/`.
- **File pribadi** (scan, tanda tangan, cap) dihapus setelah transaksi penghapusan berhasil
  (`transaction.on_commit`, `apps/sim/signals.py`).

## Format surat bawaan (`apps/sim/defaults.py`)

Pengantar · Domisili · Berkelakuan baik (SKCK, TNI/Polri) · SKTM · Usaha · Belum menikah · Kematian ·
Kelahiran · Pengantar pindah · Kehilangan · Izin keramaian · Penghasilan · (kelurahan/kecamatan) Ahli waris.
Jenis & syarat surat berbeda di tiap daerah, jadi semuanya bisa diubah, dihapus, atau ditambah pengurus.

## Fase berikutnya (usulan, belum dibuat)

- Akun pengurus tambahan per wilayah (sekretaris/bendahara) dengan hak terbatas.
- Iuran/kas RT (catat setoran warga, laporan kas).
- Laporan/aduan warga dan jadwal ronda.
- Pengajuan surat berjenjang penuh (RT → RW → kelurahan) dengan nomor di tiap tingkat.
- Impor data warga dari Excel/CSV.
- OCR akurat opsional (layanan pihak ketiga) bila pemilik memutuskan, dengan persetujuan pemrosesan data.
