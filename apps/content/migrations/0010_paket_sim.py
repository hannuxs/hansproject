"""Jenis layanan baru: SIM Wilayah (RT/RW/Kelurahan/Kecamatan), langganan bulanan.

Paket SIM dibuat TERSEMBUNYI dengan harga Rp0: harga belum ditentukan pemilik, jadi tidak
boleh tampil atau dipesan. Pemilik mengisi harga di panel (Paket & Harga), lalu menyalakan
"tampilkan". Isi fitur di bawah sesuai yang benar-benar ada di aplikasi (apps/sim).
"""
from django.db import migrations, models

SIM_FEATURES = [
    ("Foto KK/KTP lama langsung tersimpan dan teksnya dibaca otomatis jadi data warga", "OCR lokal (Tesseract) + draf data terstruktur", "sparkles", True),
    ("Cari data warga dalam hitungan detik, tidak perlu membongkar map fotokopi", "Pencarian nama/NIK/No. KK", "database", True),
    ("Warga minta surat lewat HP kapan saja, tanpa harus datang pagi-pagi", "Pengajuan surat online + kode lacak", "smartphone", True),
    ("Format surat (domisili, pengantar, SKTM, berkelakuan baik, dll.) siap pakai dan bisa diubah sendiri", "Template surat fleksibel + nomor otomatis", "file", True),
    ("Cetak surat dari HP atau komputer mana saja, tanpa menulis tangan", "Cetak A4 dari browser / simpan PDF", "printer", True),
    ("Setiap surat punya kode QR untuk cek keaslian", "QR verifikasi keaslian surat", "qr", False),
    ("Terhubung dengan RT, RW, kelurahan, dan kecamatan (surat bisa 'diketahui' wilayah di atasnya)", "Hierarki wilayah + undangan & persetujuan", "link", False),
    ("Pengumuman untuk warga, bisa diteruskan ke semua wilayah di bawahnya", "Pengumuman berjenjang di halaman warga", "megaphone", False),
    ("Data warga hanya bisa dibuka pengurus wilayah itu sendiri", "Isolasi data per wilayah; wilayah atas hanya melihat rekap", "shield", False),
]

PACKAGES = [
    ("sim-rt", "SIM RT", "🏘️", "Ketua & pengurus RT", 110),
    ("sim-rw", "SIM RW", "🏙️", "Ketua & pengurus RW (rekap semua RT yang tergabung)", 120),
    ("sim-kelurahan", "SIM Kelurahan/Desa", "🏛️", "Kantor kelurahan/desa dan kecamatan", 130),
]


def add_sim_packages(apps, schema_editor):
    Package = apps.get_model("content", "Package")
    PackageFeature = apps.get_model("content", "PackageFeature")
    for code, name, icon, tagline, order in PACKAGES:
        if Package.objects.filter(code=code).exists():
            continue
        pkg = Package.objects.create(
            code=code, category="sim", name=name, icon=icon, tagline=tagline, price=0, price_suffix="/bulan",
            description="Harga belum ditentukan. Isi harga di panel lalu nyalakan 'tampilkan'.",
            is_active=False, order=order,
        )
        PackageFeature.objects.bulk_create(
            PackageFeature(package=pkg, simple=s, technical=t, icon=i, show_in_highlights=h, order=(n + 1) * 10)
            for n, (s, t, i, h) in enumerate(SIM_FEATURES)
        )


def remove_sim_packages(apps, schema_editor):
    apps.get_model("content", "Package").objects.filter(code__in=[p[0] for p in PACKAGES], category="sim").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0009_toko_per_subdomain"),
    ]

    operations = [
        migrations.AlterField(
            model_name="package",
            name="category",
            field=models.CharField(
                choices=[
                    ("kasir", "Aplikasi Kasir (langganan)"),
                    ("sim", "SIM Wilayah RT/RW/Kelurahan (langganan)"),
                    ("jasa", "Jasa Website & Aplikasi"),
                ],
                default="kasir", max_length=10, verbose_name="jenis layanan",
            ),
        ),
        migrations.RunPython(add_sim_packages, remove_sim_packages),
    ]
