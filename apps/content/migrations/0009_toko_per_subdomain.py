"""Teks paket & dokumen legal: 1 toko = 1 subdomain = 1 akun kasir (bukan "outlet").

Teks paket / tabel perbandingan / biaya tambahan hanya diganti bila MASIH SAMA dengan
data awal. Bila pemilik sudah mengubahnya sendiri lewat panel, teks itu dibiarkan.
Syarat & Ketentuan dan Kebijakan Privasi diperbarui ke versi terbaru di apps/content/legal.py.
"""
from django.db import migrations

from apps.content.legal import LEGAL_PAGES

FEATURES = [
    # (kode paket, teks lama sederhana, teks lama teknis, teks baru sederhana, teks baru teknis)
    ("tunas", "Toko Anda punya alamat di internet sendiri, contoh: warungbudi.hansproject.app", "Subdomain *.hansproject.app",
     "Setiap toko punya alamat kasir sendiri di internet, contoh: warungbudi.hansproject.app", "Subdomain *.hansproject.app per toko"),
    ("tunas", "Untuk 2 toko, masing-masing toko punya akun sendiri", "2 outlet, 1 akun login per outlet",
     "Untuk 2 toko, masing-masing punya alamat kasir, barang, laporan, dan akun kasir sendiri", "2 toko, 1 subdomain & 1 akun kasir per toko"),
    ("tumbuh", "Untuk sampai 10 toko atau cabang", "10 outlet, 1 akun login per outlet",
     "Untuk sampai 10 toko atau cabang, masing-masing terpisah", "10 toko, 1 subdomain & 1 akun kasir per toko"),
]

ROWS = [
    # (label lama, nilai lama, label baru, nilai baru)
    ("Outlet", {"tunas": "2", "tumbuh": "10", "rimba": "Sesuai kebutuhan"},
     "Jumlah toko", {"tunas": "2", "tumbuh": "10", "rimba": "Sesuai kebutuhan"}),
    ("Akun login", {"tunas": "1 per outlet", "tumbuh": "1 per outlet", "rimba": "Sesuai kebutuhan"},
     "Akun kasir", {"tunas": "1 per toko, bisa di banyak perangkat", "tumbuh": "1 per toko, bisa di banyak perangkat", "rimba": "Sesuai kebutuhan"}),
    ("Alamat web", {"tunas": "Subdomain", "tumbuh": "Subdomain", "rimba": "Custom domain"},
     "Alamat web", {"tunas": "Subdomain per toko", "tumbuh": "Subdomain per toko", "rimba": "Custom domain"}),
    ("Tambah outlet", {"tunas": "Rp15.000/outlet/bln", "tumbuh": "Rp15.000/outlet/bln", "rimba": "–"},
     "Tambah toko", {"tunas": "Rp15.000/toko/bln", "tumbuh": "Rp15.000/toko/bln", "rimba": "–"}),
]

ADDON_OLD = "Berlaku untuk Paket Tunas dan Tumbuh."
ADDON_NEW = "Berlaku untuk Paket Tunas dan Tumbuh. Setiap toko tambahan punya alamat kasir & akun kasir sendiri."


def forwards(apps, schema_editor):
    PackageFeature = apps.get_model("content", "PackageFeature")
    ComparisonRow = apps.get_model("content", "ComparisonRow")
    AddOn = apps.get_model("content", "AddOn")
    LegalPage = apps.get_model("content", "LegalPage")
    for code, old_simple, old_tech, new_simple, new_tech in FEATURES:
        PackageFeature.objects.filter(package__code=code, simple=old_simple, technical=old_tech).update(
            simple=new_simple, technical=new_tech
        )
    for old_label, old_values, new_label, new_values in ROWS:
        for row in ComparisonRow.objects.filter(label=old_label):
            if {k: (row.values or {}).get(k) for k in old_values} == old_values:
                row.label = new_label
                row.values = {**(row.values or {}), **new_values}
                row.save(update_fields=["label", "values"])
    AddOn.objects.filter(group="outlet", description=ADDON_OLD).update(description=ADDON_NEW)
    for slug, title, body in LEGAL_PAGES:
        LegalPage.objects.update_or_create(slug=slug, defaults={"title": title, "body": body, "is_draft": False})


class Migration(migrations.Migration):
    dependencies = [("content", "0008_legal_cek_pesanan")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
