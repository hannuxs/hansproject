"""Data awal situs, diambil dari docs/01-bisnis-dan-harga.md.

PENTING: harga, isi paket, batasan, dan kebijakan di sini adalah fakta
bisnis. Setelah instalasi, pemilik mengubahnya lewat panel, bukan di file ini.
"""
from __future__ import annotations

from . import legal

PACKAGES = [
    {
        "code": "tunas",
        "category": "kasir",
        "name": "Tunas",
        "icon": "🌱",
        "tagline": "Warung, usaha rumahan, jualan online, atau yang baru mulai usaha.",
        "price": 25000,
        "price_suffix": "/bulan",
        "outlet_count": 2,
        "order": 10,
        "features": [
            ("Masukkan barang dan harga sendiri, kapan saja", "Manajemen produk & harga mandiri", "box", True),
            ("Hitung belanja pembeli otomatis, tidak perlu kalkulator", "Sistem kasir (POS)", "calculator", True),
            ("Cetak struk untuk pembeli", "Cetak struk (printer thermal)", "receipt", True),
            ("Bisa kasih diskon dan promo", "Pengaturan diskon & promo", "tag", True),
            ("Catatan jualan harian, mingguan, bulanan dibuat otomatis", "Laporan & rekap penjualan otomatis", "chart", True),
            ("Setiap toko punya alamat kasir sendiri di internet, contoh: warungbudi.hansproject.app", "Subdomain *.hansproject.app per toko", "globe", True),
            ("Halaman promosi toko sendiri (lihat bagian Halaman Promosi Toko)", "Landing page toko dengan editor terbatas", "layout", False),
            ("Tempat simpan catatan yang cukup untuk usaha kecil", "Penyimpanan 1 GB", "database", False),
            ("Untuk 2 toko, masing-masing punya alamat kasir, barang, laporan, dan akun kasir sendiri", "2 toko, 1 subdomain & 1 akun kasir per toko", "store", False),
            ("1 kali per bulan boleh minta ganti tampilan (logo, warna, tulisan di struk)", "1 revisi tampilan per bulan", "palette", False),
            ("Bisa tanya-tanya lewat DM Instagram di jam kerja", "Support via DM Instagram (jam kerja)", "chat", False),
        ],
    },
    {
        "code": "tumbuh",
        "category": "kasir",
        "name": "Tumbuh",
        "icon": "🌿",
        "tagline": "Kafe, rumah makan, toko yang punya karyawan, dan usaha yang sudah jalan.",
        "price": 99000,
        "price_suffix": "/bulan",
        "outlet_count": 10,
        # Bisnis masih baru dan belum ada data pelanggan, jadi labelnya jujur:
        "badge": "Paling Direkomendasikan",
        "is_highlighted": True,
        "includes_code": "tunas",
        "order": 20,
        "features": [
            (
                "Ada ikon aplikasi di HP, tinggal pencet seperti aplikasi biasa. Tidak perlu download dari Play Store",
                "Progressive Web App (PWA), bisa diinstal dari browser", "smartphone", False,
            ),
            ("Tempat simpan catatan lebih besar", "Penyimpanan 5 GB", "database", False),
            ("Untuk sampai 10 toko atau cabang, masing-masing terpisah", "10 toko, 1 subdomain & 1 akun kasir per toko", "store", False),
            (
                "Boleh minta 3 tambahan kemampuan baru di aplikasi per tahun, dikerjakan lebih dulu",
                "3 request fitur/modifikasi prioritas per tahun", "zap", False,
            ),
            ("Pertanyaan Anda dijawab lebih dulu", "Customer service prioritas", "headset", False),
        ],
    },
    {
        "code": "rimba",
        "category": "jasa",
        "name": "Rimba",
        "icon": "🌳",
        "tagline": (
            "Usaha yang ingin punya website atau aplikasi sendiri, usaha dengan banyak cabang, "
            "perusahaan, atau siapa saja yang punya ide aplikasi."
        ),
        "description": (
            "Jasa pembuatan website (company profile, toko online, dll.) juga masuk ke paket ini. "
            'Tidak ada paket "website saja" yang terpisah.'
        ),
        "price": 349000,
        "price_prefix": "Mulai",
        "price_suffix": "biaya pembuatan",
        "monthly_price": 200000,
        "order": 30,
        "features": [
            ("Kami buatkan website atau aplikasi khusus untuk usaha Anda, sesuai keinginan", "Custom development dari nol", "code", False),
            ("Aplikasi bisa tayang di Play Store (HP Android) dan App Store (iPhone)", "Aplikasi Android & iOS + publikasi ke store", "smartphone", False),
            ("Alamat website bebas pilih, contoh: tokobudi.com", "Custom domain (.com, .id, .co.id, dll.)", "globe", False),
            ("Isi dan tampilan bebas, sesuai kesepakatan", "Menu & fitur custom sesuai kontrak", "layout", False),
            ("Bisa ditambah fitur pintar, seperti balas chat pembeli otomatis", "Integrasi model AI sederhana (chatbot, rekomendasi, dll.)", "sparkles", False),
            ("Tempat simpan paling besar", "Penyimpanan 10 GB", "database", False),
            ("Ada orang khusus yang mengurus kebutuhan Anda", "Dedicated support", "user-check", False),
        ],
        "notes": [
            ("Harga pembuatan tergantung seberapa rumit permintaan Anda. Konsultasi dulu, gratis.", ""),
            (
                "Biaya bulanan Rp200.000 untuk menjaga website/aplikasi tetap jalan, dirawat, dan dibantu kalau ada masalah.",
                "Hosting, maintenance & support",
            ),
            (
                "Biaya pendaftaran akun Play Store dan App Store ditanggung klien.",
                "Google Play Developer sekali bayar, Apple Developer Program tahunan",
            ),
        ],
    },
]

INCLUDED = [
    ("Bisa dipakai kapan saja, siang atau malam", "Online 24/7", "clock"),
    ("Bisa dibuka dari HP atau laptop, di mana saja, asal ada internet", "Berbasis web (cloud), lintas perangkat", "cloud"),
    ("Catatan jualan tersimpan aman, tidak hilang walau HP rusak", "Data tersimpan di server, bukan di perangkat", "shield"),
]

ADDONS = [
    ("outlet", "Tambah toko/cabang", 15000, "/toko/bulan", "Berlaku untuk Paket Tunas dan Tumbuh. Setiap toko tambahan punya alamat kasir & akun kasir sendiri."),
    ("storage", "+1 GB", 10000, "/bulan", ""),
    ("storage", "+5 GB", 35000, "/bulan", ""),
    ("storage", "+10 GB", 60000, "/bulan", ""),
]

# Baris "Harga" dibuat otomatis dari data paket, jadi tidak ada di sini.
COMPARISON = [
    ("Jenis", {"tunas": "Aplikasi kasir (POS)", "tumbuh": "Aplikasi kasir (POS)", "rimba": "Custom development"}),
    ("Penyimpanan", {"tunas": "1 GB", "tumbuh": "5 GB", "rimba": "10 GB"}),
    ("Jumlah toko", {"tunas": "2", "tumbuh": "10", "rimba": "Sesuai kebutuhan"}),
    ("Akun kasir", {"tunas": "1 per toko, bisa di banyak perangkat", "tumbuh": "1 per toko, bisa di banyak perangkat", "rimba": "Sesuai kebutuhan"}),
    ("Alamat web", {"tunas": "Subdomain per toko", "tumbuh": "Subdomain per toko", "rimba": "Custom domain"}),
    ("Halaman promosi toko", {"tunas": "Ya (editor terbatas)", "tumbuh": "Ya (editor terbatas)", "rimba": "Custom penuh"}),
    ("Aplikasi HP", {"tunas": "–", "tumbuh": "PWA", "rimba": "Android & iOS (Play Store / App Store)"}),
    ("Modifikasi", {"tunas": "1 revisi tampilan/bln", "tumbuh": "3 request fitur prioritas/thn", "rimba": "Bebas sesuai kontrak"}),
    ("Support", {"tunas": "Jam kerja", "tumbuh": "Prioritas", "rimba": "Dedicated"}),
    ("Tambah toko", {"tunas": "Rp15.000/toko/bln", "tumbuh": "Rp15.000/toko/bln", "rimba": "–"}),
    ("Tambah penyimpanan", {"tunas": "Mulai Rp10.000/bln", "tumbuh": "Mulai Rp10.000/bln", "rimba": "Mulai Rp10.000/bln"}),
]

FAQS = [
    (
        "Bayarnya bagaimana?",
        "Transfer bank atau scan QRIS, lalu kirim foto bukti bayar ke kami. Aplikasi langsung diaktifkan.",
        True,
    ),
    (
        "Bagaimana cara daftarnya?",
        "1. Pilih paket, lalu tekan **Pesan Sekarang**.\n2. Daftar atau masuk ke akun Anda.\n"
        "3. Bayar lewat transfer bank atau scan QRIS.\n4. Kirim foto bukti bayar.\n5. Aplikasi diaktifkan.\n\n"
        "Tidak ada pembayaran online di website ini.",
        True,
    ),
    (
        "Karyawan saya perlu akun sendiri?",
        "Tidak perlu. Setiap toko punya 1 akun, dan siapa pun yang jaga toko bisa memakainya.",
        True,
    ),
    (
        "Toko saya lebih dari 2, bagaimana?",
        "Anda bisa tambah toko/cabang Rp15.000 per toko, per bulan. Kalau tokonya banyak, biasanya lebih hemat "
        "naik ke Paket Tumbuh (sampai 10 toko).",
        True,
    ),
    (
        "Kalau tempat simpan saya penuh bagaimana?",
        "Kami kabari sebelum penuh. Anda bisa beli tambahan tempat simpan atau naik paket.",
        True,
    ),
    (
        "Kalau saya telat bayar bagaimana?",
        "- **Telat 1–7 hari:** aplikasi masih bisa dipakai. Kalau mau berhenti, catatan jualan masih bisa Anda "
        "simpan ke HP atau laptop.\n"
        "- **Telat 8 hari sampai 1 bulan:** aplikasi berhenti sementara. Begitu Anda bayar, aplikasi jalan lagi "
        "dan semua catatan masih lengkap.\n"
        "- **Lewat dari itu:** semua catatan dihapus dan tidak bisa dikembalikan.",
        True,
    ),
    (
        'Apa bedanya "ganti tampilan" dan "tambahan kemampuan baru"?',
        "- **Ganti tampilan:** mengubah yang sudah ada, misalnya logo, warna, atau tulisan di struk.\n"
        "- **Tambahan kemampuan baru:** menambah sesuatu yang belum ada, misalnya fitur catat utang pelanggan.",
        True,
    ),
    (
        "Apakah halaman promosi toko bisa dipakai untuk terima pesanan online?",
        "Tidak. Halaman ini hanya untuk promosi: menampilkan logo, tulisan, foto, dan (kalau mau) daftar harga.",
        True,
    ),
    (
        "Apakah aplikasi Paket Tumbuh ada di Play Store?",
        "Tidak perlu download dari Play Store. Aplikasinya dipasang langsung dari browser HP, lalu muncul ikonnya "
        "di layar seperti aplikasi biasa. Aplikasi yang tayang di Play Store/App Store ada di Paket Rimba.",
        True,
    ),
    (
        "Berapa biaya bikin website atau aplikasi?",
        "Mulai Rp349.000 untuk biaya pembuatan, lalu Rp200.000/bulan untuk menjaga website/aplikasi tetap jalan, "
        "dirawat, dan dibantu kalau ada masalah. Harga pembuatan tergantung seberapa rumit permintaan Anda. "
        "Konsultasi dulu, gratis.",
        True,
    ),
    (
        "Bisa pindah paket?",
        "[PERLU DIISI PEMILIK] Kebijakan pindah paket belum ditentukan. Tulis jawabannya di sini, lalu nyalakan "
        "'tampilkan'.",
        False,  # disembunyikan sampai pemilik mengisi kebijakannya
    ),
]

# ---------------------------------------------------------------------------
# Sistem Informasi Manajemen (SIM): paket Tunas & Tumbuh, sama seperti Aplikasi Kasir.
# Harga Rp0 = belum ditentukan pemilik: tampil "Harga segera diumumkan" dan belum bisa
# dipesan sampai harganya diisi di panel (Paket & Harga).
# Bagian pertama yang tersedia: SIM untuk RT, RW, kelurahan/desa, dan kecamatan.
# ---------------------------------------------------------------------------
SIM_PACKAGES = [
    {
        "code": "sim-tunas",
        "category": "sim",
        "name": "Tunas",
        "icon": "🌱",
        "tagline": "RT, RW, dan organisasi kecil yang mulai merapikan data dan surat.",
        "price": 0,
        "price_suffix": "/bulan",
        "scan_limit": 100,
        "order": 40,
        "features": [
            ("Foto KK/KTP lama langsung tersimpan, teksnya dibaca otomatis jadi data", "Scan dokumen + OCR (hasil diperiksa dulu)", "scan", True),
            ("Cari data dalam hitungan detik, tidak perlu membongkar map fotokopi", "Pencarian nama / NIK / No. KK", "search", True),
            ("Warga minta surat lewat HP kapan saja, lalu memantau statusnya", "Pengajuan surat online + kode lacak", "smartphone", True),
            ("Format surat siap pakai dan bisa diubah sendiri, nomor surat otomatis", "Template surat fleksibel + penomoran otomatis", "file", True),
            ("Ketik dan cetak surat dari HP atau komputer mana saja, tanpa tulis tangan", "Cetak A4 dari browser / simpan PDF", "printer", True),
            ("Setiap surat punya kode QR untuk cek keaslian", "QR verifikasi keaslian", "qr", False),
            ("Terhubung dengan tingkat di atasnya, misalnya RT ke RW, RW ke kelurahan", "Hierarki instansi + kode undangan & persetujuan", "link", False),
            ("Pengumuman untuk warga di halaman instansi", "Halaman publik + pengumuman", "megaphone", False),
            ("Sampai 100 foto dokumen dibaca otomatis setiap bulan", "Kuota OCR 100 dokumen/bulan", "scan", False),
            ("Tempat simpan yang cukup untuk satu RT/RW", "Penyimpanan 1 GB", "database", False),
            ("Bisa tanya-tanya lewat DM Instagram di jam kerja", "Support via DM Instagram (jam kerja)", "chat", False),
        ],
    },
    {
        "code": "sim-tumbuh",
        "category": "sim",
        "name": "Tumbuh",
        "icon": "🌿",
        "tagline": "Kelurahan/desa, kecamatan, dan instansi dengan data serta surat yang lebih banyak.",
        "price": 0,
        "price_suffix": "/bulan",
        "scan_limit": 1000,
        "badge": "Untuk instansi besar",
        "is_highlighted": True,
        "includes_code": "sim-tunas",
        "order": 50,
        "features": [
            ("Sampai 1.000 foto dokumen dibaca otomatis setiap bulan", "Kuota OCR 1.000 dokumen/bulan", "scan", False),
            ("Tempat simpan lebih besar", "Penyimpanan 5 GB", "database", False),
            ("Rekap jumlah warga dari semua RT/RW yang tergabung, tanpa membuka data pribadinya", "Rekap berjenjang + pengumuman ke semua unit di bawahnya", "chart", False),
            ("Boleh minta 3 tambahan kemampuan atau format khusus per tahun, dikerjakan lebih dulu", "3 request fitur/modifikasi prioritas per tahun", "zap", False),
            ("Pertanyaan Anda dijawab lebih dulu", "Customer service prioritas", "headset", False),
        ],
    },
]

# Nilai tabel perbandingan untuk paket SIM (digabung ke baris yang sama dengan kasir).
SIM_COMPARISON = [
    ("Jenis", {"sim-tunas": "Sistem Informasi Manajemen", "sim-tumbuh": "Sistem Informasi Manajemen"}),
    ("Cocok untuk", {"sim-tunas": "RT, RW", "sim-tumbuh": "Kelurahan/desa, kecamatan"}),
    ("Scan dokumen otomatis (OCR)", {"sim-tunas": "100 dokumen/bln", "sim-tumbuh": "1.000 dokumen/bln"}),
    ("Penyimpanan", {"sim-tunas": "1 GB", "sim-tumbuh": "5 GB"}),
    ("Surat online & QR keaslian", {"sim-tunas": "Ya", "sim-tumbuh": "Ya"}),
    ("Terhubung antar tingkat", {"sim-tunas": "Ya", "sim-tumbuh": "Ya + rekap unit di bawahnya"}),
    ("Modifikasi", {"sim-tunas": "1 revisi format/bln", "sim-tumbuh": "3 request fitur prioritas/thn"}),
    ("Support", {"sim-tunas": "Jam kerja", "sim-tumbuh": "Prioritas"}),
]

SIM_FAQS = [
    (
        "Apa itu SIM?",
        "SIM adalah singkatan dari **Sistem Informasi Manajemen**: aplikasi untuk mencatat, mencari, dan mengolah data "
        "sebuah instansi atau organisasi, lalu memakainya untuk pekerjaan sehari-hari seperti membuat surat.\n\n"
        "Yang tersedia sekarang: SIM untuk **RT, RW, kelurahan/desa, dan kecamatan**. SIM untuk bidang lain "
        "(misalnya klinik/rumah sakit, sekolah, organisasi) sedang kami siapkan.",
        True, "umum",
    ),
    (
        "Data warga di SIM aman? Siapa yang bisa melihatnya?",
        "Data warga hanya bisa dibuka oleh pengurus instansi itu sendiri lewat akunnya. Tingkat di atasnya "
        "(misalnya RW atau kelurahan) hanya melihat **angka rekap**, bukan data pribadi. Foto KK/KTP disimpan di tempat "
        "pribadi tanpa alamat publik, dan dibaca di server kami sendiri (tidak dikirim ke layanan lain).",
        True, "sim",
    ),
    (
        "Apakah hasil baca foto KK/KTP selalu benar?",
        "Belum tentu. Hasil baca otomatis adalah **draf**: pengurus memeriksa dan membetulkannya dulu sebelum disimpan "
        "jadi data. Foto yang terang, lurus, dan tidak buram memberi hasil paling baik.",
        True, "sim",
    ),
    (
        "Warga perlu daftar akun untuk minta surat?",
        "Tidak. Warga membuka halaman instansi, mengisi formulir pengajuan, lalu mendapat **kode lacak** untuk memantau "
        "status suratnya. Pengurus memeriksa, lalu mencetak atau mengizinkan warga mencetak sendiri.",
        True, "sim",
    ),
    (
        "Format surat di daerah saya berbeda, bisa diubah?",
        "Bisa. Semua format surat (domisili, pengantar, SKTM, berkelakuan baik, dan lainnya) bisa diubah, dihapus, atau "
        "ditambah sendiri oleh pengurus, termasuk kop, nomor surat, dan kolom isiannya.",
        True, "sim",
    ),
]

# Topik FAQ bawaan: pertanyaan yang khusus satu solusi tampil di halaman solusinya.
FAQ_TOPICS = {
    "Karyawan saya perlu akun sendiri?": "kasir",
    "Toko saya lebih dari 2, bagaimana?": "kasir",
    "Apakah halaman promosi toko bisa dipakai untuk terima pesanan online?": "kasir",
    "Apakah aplikasi Paket Tumbuh ada di Play Store?": "kasir",
    "Berapa biaya bikin website atau aplikasi?": "jasa",
    'Apa bedanya "ganti tampilan" dan "tambahan kemampuan baru"?': "kasir",
}

BANK_PLACEHOLDER = ("BANK CONTOH (ganti di panel)", "0000000000", "NAMA PEMILIK REKENING")

# Teks final ada di apps/content/legal.py (dipakai seed & migrasi).
LEGAL_PAGES = legal.LEGAL_PAGES

