"""Paket per solusi: Aplikasi Kasir DAN Sistem Informasi Manajemen (SIM) sama-sama punya
Paket Tunas & Tumbuh. FAQ diberi topik supaya halaman utama tidak lagi berisi pertanyaan kasir.

- Paket SIM lama per tingkat (SIM RT / SIM RW / SIM Kelurahan, tersembunyi, Rp0) diganti
  SIM Tunas & SIM Tumbuh. Paket lama hanya dihapus bila masih persis seperti data awal
  (Rp0, tersembunyi); bila pemilik sudah mengubahnya, dibiarkan.
- Harga paket SIM tetap Rp0 = "Harga segera diumumkan" (belum bisa dipesan) sampai pemilik
  mengisi harga di panel.
- Baris tabel perbandingan mendapat nilai untuk paket SIM (nilai yang sudah ada tidak ditimpa).
"""
from django.db import migrations, models

from apps.content.seed_data import FAQ_TOPICS, SIM_COMPARISON, SIM_FAQS, SIM_PACKAGES

OLD_SIM = ["sim-rt", "sim-rw", "sim-kelurahan"]
FIELDS = ("category", "name", "icon", "tagline", "price", "price_suffix", "scan_limit", "badge", "is_highlighted", "order")


def forwards(apps, schema_editor):
    Package = apps.get_model("content", "Package")
    PackageFeature = apps.get_model("content", "PackageFeature")
    ComparisonRow = apps.get_model("content", "ComparisonRow")
    Faq = apps.get_model("content", "Faq")

    Package.objects.filter(code__in=OLD_SIM, category="sim", price=0, is_active=False).delete()

    created = {}
    for spec in SIM_PACKAGES:
        if Package.objects.filter(code=spec["code"]).exists():
            continue
        pkg = Package.objects.create(code=spec["code"], is_active=True, **{k: spec[k] for k in FIELDS if k in spec})
        created[pkg.code] = pkg
        PackageFeature.objects.bulk_create(
            PackageFeature(package=pkg, simple=s, technical=t, icon=i, show_in_highlights=h, order=(n + 1) * 10)
            for n, (s, t, i, h) in enumerate(spec["features"])
        )
    for spec in SIM_PACKAGES:
        parent = Package.objects.filter(code=spec.get("includes_code", "")).first()
        if spec["code"] in created and parent:
            created[spec["code"]].includes_from = parent
            created[spec["code"]].save(update_fields=["includes_from"])

    last = ComparisonRow.objects.order_by("-order").values_list("order", flat=True).first() or 0
    for label, values in SIM_COMPARISON:
        row = ComparisonRow.objects.filter(label=label).first()
        if row is None:
            last += 10
            ComparisonRow.objects.create(label=label, values=values, order=last)
            continue
        current = row.values if isinstance(row.values, dict) else {}
        merged = {**values, **current}  # nilai yang sudah diisi pemilik tidak ditimpa
        if merged != current:
            row.values = merged
            row.save(update_fields=["values"])

    for question, topic in FAQ_TOPICS.items():
        Faq.objects.filter(question=question, topic="umum").update(topic=topic)
    last = Faq.objects.order_by("-order").values_list("order", flat=True).first() or 0
    for question, answer, active, topic in SIM_FAQS:
        if not Faq.objects.filter(question=question).exists():
            last += 10
            Faq.objects.create(question=question, answer=answer, is_active=active, topic=topic, order=last)


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0011_ikon_sim"),
        # Paket lama dirujuk pesanan & instansi SIM (SET_NULL): model-model itu harus sudah ada.
        ("members", "0012_topik_sim_tiket"),
        ("sim", "0001_sim_wilayah"),
    ]

    operations = [
        migrations.AlterField(
            model_name="package",
            name="category",
            field=models.CharField(
                choices=[
                    ("kasir", "Aplikasi Kasir (langganan)"),
                    ("sim", "Sistem Informasi Manajemen / SIM (langganan)"),
                    ("jasa", "Jasa Website & Aplikasi"),
                ],
                default="kasir", max_length=10, verbose_name="jenis layanan",
            ),
        ),
        migrations.AlterField(
            model_name="package",
            name="outlet_count",
            field=models.PositiveSmallIntegerField(
                blank=True, help_text="Aplikasi Kasir. Dipakai kalkulator hemat.", null=True,
                verbose_name="jumlah toko/outlet termasuk",
            ),
        ),
        migrations.AddField(
            model_name="package",
            name="scan_limit",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="batas scan dokumen per bulan",
                help_text="SIM: jumlah foto KK/KTP/dokumen yang bisa dibaca otomatis (OCR) per bulan. Kosongkan = tanpa batas.",
            ),
        ),
        migrations.AddField(
            model_name="faq",
            name="topic",
            field=models.CharField(
                choices=[
                    ("umum", "Umum (halaman utama)"),
                    ("kasir", "Aplikasi Kasir"),
                    ("sim", "Sistem Informasi Manajemen (SIM)"),
                    ("jasa", "Website & Aplikasi"),
                ],
                default="umum", max_length=10, verbose_name="tampil di",
                help_text="Umum = halaman utama. Lainnya = halaman solusi masing-masing.",
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
