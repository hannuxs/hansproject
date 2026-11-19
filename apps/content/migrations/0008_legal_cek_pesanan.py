"""Kebijakan Privasi: tambah keterangan halaman cek keaslian pesanan (QR)."""
from django.db import migrations

from apps.content.legal import LEGAL_PAGES


def forwards(apps, schema_editor):
    LegalPage = apps.get_model("content", "LegalPage")
    for slug, title, body in LEGAL_PAGES:
        LegalPage.objects.update_or_create(slug=slug, defaults={"title": title, "body": body, "is_draft": False})


class Migration(migrations.Migration):
    dependencies = [("content", "0007_legal_chat_refund")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
