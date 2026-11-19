"""Perbarui teks S&K & Kebijakan Privasi: menu Chat (pengganti Tanya Kami), data chat & refund."""
from django.db import migrations

from apps.content.legal import LEGAL_PAGES


def forwards(apps, schema_editor):
    LegalPage = apps.get_model("content", "LegalPage")
    for slug, title, body in LEGAL_PAGES:
        LegalPage.objects.update_or_create(slug=slug, defaults={"title": title, "body": body, "is_draft": False})


class Migration(migrations.Migration):
    dependencies = [("content", "0006_announcement")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
