"""Kebijakan Privasi: daftar data warga SIM mengikuti kolom KK Dukcapil yang kini disimpan
(tanggal perkawinan, paspor/KITAS/KITAP, wilayah lengkap, tanggal KK dikeluarkan).

Hanya melengkapi daftar isi KK yang sudah disebut, jadi versi legal tidak diubah (tidak perlu persetujuan ulang).
Teks hanya diganti bila kalimat lamanya masih ada (belum diubah pemilik di panel).
"""
from django.db import migrations

OLD = 'kewarganegaraan, nama ayah dan ibu, golongan darah, alamat, dan status warga'
NEW = 'kewarganegaraan, nomor paspor dan KITAS/KITAP (bila ada), tanggal perkawinan atau perceraian, nama ayah dan ibu, golongan darah, alamat beserta desa/kelurahan sampai provinsi, tanggal KK dikeluarkan, dan status warga'


def forwards(apps, schema_editor):
    LegalPage = apps.get_model("content", "LegalPage")
    for page in LegalPage.objects.filter(body__contains=OLD):
        page.body = page.body.replace(OLD, NEW)
        page.save(update_fields=["body", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("content", "0014_jumlah_pengguna")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
