"""Platform solusi digital: S&K/Privasi mencakup Sistem Informasi Manajemen (SIM), versi legal baru
(pelanggan diminta menyetujui ulang), dan judul/deskripsi Google tidak lagi khusus kasir.

Judul & deskripsi Google hanya diganti bila masih sama dengan bawaan lama (belum diubah pemilik).
"""
import datetime

from django.db import migrations, models

from apps.content.legal import LEGAL_PAGES

NEW_VERSION = datetime.date(2026, 11, 22)
OLD_TITLE = "Aplikasi Kasir Murah Mulai Rp25 Ribu/Bulan | HANS Project"
NEW_TITLE = "HANS Project: Aplikasi Kasir, SIM & Jasa Website/Aplikasi"
OLD_DESCRIPTIONS = [
    "Aplikasi kasir online untuk warung, toko, kafe, dan UMKM. Cukup pakai HP, mulai Rp25.000/bulan. Juga jasa pembuatan website & aplikasi Android/iOS.",
    "Aplikasi kasir online untuk warung, toko, kafe, dan UMKM. Cukup pakai HP, mulai Rp25.000/bulan. Juga jasa pembuatan website & aplikasi.",
]
NEW_DESCRIPTION = (
    "Solusi digital siap pakai: aplikasi kasir untuk usaha, Sistem Informasi Manajemen (SIM) untuk RT, RW, "
    "kelurahan & instansi, serta jasa pembuatan website & aplikasi."
)


def forwards(apps, schema_editor):
    LegalPage = apps.get_model("content", "LegalPage")
    SiteSettings = apps.get_model("content", "SiteSettings")
    for slug, title, body in LEGAL_PAGES:
        LegalPage.objects.update_or_create(slug=slug, defaults={"title": title, "body": body, "is_draft": False})
    for site in SiteSettings.objects.all():
        changed = []
        if site.legal_version is None or site.legal_version < NEW_VERSION:
            site.legal_version = NEW_VERSION
            changed.append("legal_version")
        if site.seo_title == OLD_TITLE:
            site.seo_title = NEW_TITLE
            changed.append("seo_title")
        if site.seo_description in OLD_DESCRIPTIONS:
            site.seo_description = NEW_DESCRIPTION
            changed.append("seo_description")
        if changed:
            site.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("content", "0012_paket_per_solusi")]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="legal_version",
            field=models.DateField(
                default=NEW_VERSION, verbose_name="versi Syarat & Ketentuan dan Kebijakan Privasi",
                help_text=(
                    "Tanggal versi yang berlaku. Ubah tanggal ini HANYA bila isi Syarat & Ketentuan atau Kebijakan Privasi "
                    "berubah penting: setiap pelanggan akan diminta menyetujui ulang saat masuk berikutnya."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="seo_title",
            field=models.CharField(default=NEW_TITLE, max_length=70, verbose_name="judul di Google"),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="seo_description",
            field=models.CharField(default=NEW_DESCRIPTION, max_length=170, verbose_name="deskripsi di Google"),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
