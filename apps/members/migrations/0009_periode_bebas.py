"""Periode rincian harga jadi teks bebas (mis. "3 bulan"); nilai lama "hari/bulan/tahun" -> "1 hari" dst."""
from django.db import migrations, models


def forwards(apps, schema_editor):
    OrderItem = apps.get_model("members", "OrderItem")
    for old in ("hari", "bulan", "tahun"):
        OrderItem.objects.filter(period=old).update(period=f"1 {old}")


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0008_rincian_harga_keaslian"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orderitem",
            name="period",
            field=models.CharField(blank=True, default="", help_text="Diketik bebas, mis. 1 tahun, 3 bulan, 14 hari. Kosongkan bila sekali bayar.", max_length=40, verbose_name="periode"),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
