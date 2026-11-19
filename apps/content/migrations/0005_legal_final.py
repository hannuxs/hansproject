"""Syarat & Ketentuan dan Kebijakan Privasi versi final (19 Nov 2026), bukan draf lagi.

Teks diambil dari apps/content/legal.py. Halaman legal lama (draf) ditimpa.
"""
from django.db import migrations

# Catatan: teks dibaca dari legal.py saat migrasi dijalankan. Migrasi ini hanya
# berarti untuk database yang sudah berisi draf lama; instalasi baru memakai seed.
from apps.content.legal import LEGAL_PAGES


def forwards(apps, schema_editor):
    LegalPage = apps.get_model("content", "LegalPage")
    for slug, title, body in LEGAL_PAGES:
        LegalPage.objects.update_or_create(slug=slug, defaults={"title": title, "body": body, "is_draft": False})


class Migration(migrations.Migration):
    dependencies = [("content", "0004_tanpa_whatsapp")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
