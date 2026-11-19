"""Hapus semua sisa WhatsApp (keputusan pemilik, 19 Nov 2026). Semua keperluan lewat DM Instagram.

- Kolom lama dibuang: nomor & template pesan di Pengaturan Umum, tulisan tombol & pesan per paket.
- Tabel penghitung klik diganti nama: hp_wa_click -> hp_contact_click (isi tetap).
- Teks di database yang masih menyebut WhatsApp diganti.
- Tambah "versi Syarat & Ketentuan / Kebijakan Privasi" untuk popup persetujuan.
"""
import datetime
import re

from django.db import migrations, models

WA = re.compile(r"(?i)whats\s*app")

# Teks lama (dari data awal versi sebelumnya) -> teks baru.
REPLACEMENTS = [
    ("Bisa tanya-tanya lewat WhatsApp di jam kerja", "Bisa tanya-tanya lewat DM Instagram di jam kerja"),
    ("Support via WhatsApp (jam kerja)", "Support via DM Instagram (jam kerja)"),
    ("Pertanyaan Anda di WhatsApp dijawab lebih dulu", "Pertanyaan Anda dijawab lebih dulu"),
    ("Semua pendaftaran lewat WhatsApp.", "Pendaftaran dan pemesanan lewat akun di website ini."),
    ("Kami kabari lewat WhatsApp sebelum penuh.", "Kami kabari sebelum penuh."),
    ("WhatsApp jam kerja", "Jam kerja"),
    ("lewat WhatsApp", "lewat DM Instagram"),
    ("via WhatsApp", "via DM Instagram"),
    ("di WhatsApp", "lewat DM Instagram"),
    ("WhatsApp", "DM Instagram"),
    # Karakter "–" yang rusak saat disimpan (1–7 hari).
    ("1�7", "1–7"),
]


def _fix(text):
    if not isinstance(text, str):
        return text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def forwards(apps, schema_editor):
    targets = {
        "PackageFeature": ["simple", "technical"],
        "PackageNote": ["simple", "technical"],
        "IncludedFeature": ["simple", "technical"],
        "Package": ["tagline", "description", "badge"],
        "AddOn": ["name", "description"],
        "Faq": ["question", "answer"],
        "Testimonial": [],
        "SiteSettings": ["hero_title", "hero_subtitle", "announcement_text", "seo_title", "seo_description", "support_hours"],
    }
    for model_name, fields in targets.items():
        Model = apps.get_model("content", model_name)
        names = fields or [f.name for f in Model._meta.fields if f.get_internal_type() in ("CharField", "TextField")]
        for obj in Model.objects.all():
            changed = []
            for name in names:
                old = getattr(obj, name)
                new = _fix(old)
                if new != old:
                    setattr(obj, name, new)
                    changed.append(name)
            if changed:
                obj.save(update_fields=changed)
    ComparisonRow = apps.get_model("content", "ComparisonRow")
    for row in ComparisonRow.objects.all():
        values = {k: _fix(v) for k, v in (row.values or {}).items()}
        label = _fix(row.label)
        if values != row.values or label != row.label:
            row.values, row.label = values, label
            row.save(update_fields=["values", "label"])


class Migration(migrations.Migration):
    dependencies = [("content", "0003_tunas_penyimpanan_1gb")]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(model_name="sitesettings", name="whatsapp_number"),
        migrations.RemoveField(model_name="sitesettings", name="wa_package_message"),
        migrations.RemoveField(model_name="sitesettings", name="wa_general_message"),
        migrations.RemoveField(model_name="sitesettings", name="wa_addon_message"),
        migrations.RemoveField(model_name="package", name="cta_label"),
        migrations.RemoveField(model_name="package", name="wa_message"),
        migrations.RemoveConstraint(model_name="waclick", name="hp_wa_click_unique_day_target"),
        migrations.RenameModel(old_name="WaClick", new_name="ContactClick"),
        migrations.AlterModelTable(name="contactclick", table="hp_contact_click"),
        migrations.AddConstraint(
            model_name="contactclick",
            constraint=models.UniqueConstraint(fields=("date", "target"), name="hp_contact_click_day_target"),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="legal_version",
            field=models.DateField(
                default=datetime.date(2026, 11, 19),
                help_text=(
                    "Tanggal versi yang berlaku. Ubah tanggal ini HANYA bila isi Syarat & Ketentuan atau Kebijakan "
                    "Privasi berubah penting: setiap pelanggan akan diminta menyetujui ulang saat masuk berikutnya."
                ),
                verbose_name="versi Syarat & Ketentuan dan Kebijakan Privasi",
            ),
        ),
    ]
