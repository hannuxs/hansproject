"""Paket Tunas: penyimpanan 1,5 GB menjadi 1 GB (keputusan pemilik, 17 Nov 2026).

Hanya mengganti teks yang MASIH SAMA dengan data awal. Bila pemilik sudah
mengubahnya sendiri lewat panel, teks itu dibiarkan.
"""
from django.db import migrations

OLD, NEW = "1,5 GB", "1 GB"


def forwards(apps, schema_editor):
    _swap(apps, OLD, NEW)


def backwards(apps, schema_editor):
    _swap(apps, NEW, OLD)


def _swap(apps, old, new):
    PackageFeature = apps.get_model("content", "PackageFeature")
    ComparisonRow = apps.get_model("content", "ComparisonRow")
    PackageFeature.objects.filter(package__code="tunas", technical=f"Penyimpanan {old}").update(
        technical=f"Penyimpanan {new}"
    )
    for row in ComparisonRow.objects.filter(label="Penyimpanan"):
        if (row.values or {}).get("tunas") == old:
            row.values["tunas"] = new
            row.save(update_fields=["values"])


class Migration(migrations.Migration):
    dependencies = [("content", "0002_instagram_dm")]
    operations = [migrations.RunPython(forwards, backwards)]
