"""Langkah 1/3 (1 toko = 1 subdomain = 1 kasir): tabel langganan + kolom baru di toko."""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0008_legal_cek_pesanan"),
        ("members", "0009_periode_bebas"),
        ("pos", "0001_aplikasi_kasir"),
    ]

    operations = [
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("package_name", models.CharField(max_length=60, verbose_name="nama paket")),
                ("base_stores", models.PositiveSmallIntegerField(default=2, validators=[django.core.validators.MaxValueValidator(500)], verbose_name="toko termasuk paket")),
                ("extra_stores", models.PositiveSmallIntegerField(default=0, help_text="Bertambah otomatis saat pesanan tambahan toko diaktifkan.", validators=[django.core.validators.MaxValueValidator(500)], verbose_name="toko tambahan (dibeli)")),
                ("status", models.CharField(choices=[("aktif", "Normal"), ("ditangguhkan", "Ditangguhkan admin")], default="aktif", max_length=14, verbose_name="status")),
                ("active_until", models.DateField(verbose_name="aktif sampai")),
                ("admin_note", models.TextField(blank=True, help_text="Tampil di halaman semua toko dalam langganan ini, misalnya alasan ditangguhkan.", max_length=1000, verbose_name="catatan untuk pemilik toko")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="dibuat")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="diperbarui")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subscriptions", to="members.member", verbose_name="pemilik")),
                ("package", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="content.package", verbose_name="paket")),
            ],
            options={
                "verbose_name": "langganan kasir",
                "verbose_name_plural": "langganan kasir",
                "db_table": "hp_pos_subscription",
                "ordering": ["created_at", "pk"],
            },
        ),
        migrations.AddField(
            model_name="store",
            name="subscription",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="stores", to="pos.subscription", verbose_name="langganan"),
        ),
        migrations.AddField(
            model_name="store",
            name="is_active",
            field=models.BooleanField(default=True, help_text="Toko nonaktif tidak memakai kuota paket dan kasirnya tidak bisa masuk. Datanya tetap ada.", verbose_name="toko aktif"),
        ),
        migrations.AddField(
            model_name="store",
            name="sale_seq",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AlterField(
            model_name="cashier",
            name="outlet",
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="cashier", to="pos.outlet"),
        ),
    ]
