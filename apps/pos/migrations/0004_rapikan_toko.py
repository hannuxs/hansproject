# Langkah 3/3 (1 toko = 1 subdomain = 1 kasir): buang kolom lama & tabel outlet. Dibuat Django 5.2.19.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0003_pindah_data_toko'),
    ]

    operations = [
        # Tabel outlet dihapus utuh di akhir (DeleteModel). Kolom store-nya TIDAK dihapus
        # terpisah: MariaDB menolak karena masih dipakai constraint (store, number).
        migrations.RemoveField(
            model_name='sale',
            name='outlet',
        ),
        migrations.RemoveField(
            model_name='cashier',
            name='outlet',
        ),
        migrations.AlterModelOptions(
            name='store',
            options={'ordering': ['created_at', 'pk'], 'verbose_name': 'toko', 'verbose_name_plural': 'toko'},
        ),
        migrations.RemoveConstraint(
            model_name='cashier',
            name='hp_pos_cashier_username_uniq',
        ),
        migrations.RemoveField(
            model_name='store',
            name='active_until',
        ),
        migrations.RemoveField(
            model_name='store',
            name='admin_note',
        ),
        migrations.RemoveField(
            model_name='store',
            name='base_outlets',
        ),
        migrations.RemoveField(
            model_name='store',
            name='extra_outlets',
        ),
        migrations.RemoveField(
            model_name='store',
            name='package',
        ),
        migrations.RemoveField(
            model_name='store',
            name='package_name',
        ),
        migrations.RemoveField(
            model_name='store',
            name='status',
        ),
        migrations.AlterField(
            model_name='cashier',
            name='store',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='cashier', to='pos.store'),
        ),
        migrations.AlterField(
            model_name='store',
            name='subscription',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stores', to='pos.subscription', verbose_name='langganan'),
        ),
        migrations.DeleteModel(
            name='Outlet',
        ),
    ]
