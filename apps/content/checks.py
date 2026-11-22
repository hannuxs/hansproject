"""Daftar data yang masih berupa contoh (placeholder) dan perlu diisi pemilik."""
from __future__ import annotations

from dataclasses import dataclass

from .models import BankAccount, LegalPage, Package, SiteSettings


@dataclass
class Reminder:
    text: str
    url_name: str  # nama URL panel tempat memperbaikinya


def placeholder_reminders() -> list[Reminder]:
    site = SiteSettings.load()
    items: list[Reminder] = []
    if not site.instagram_username:
        items.append(Reminder("Username Instagram kosong: tombol DM Instagram tidak tampil.", "panel:pengaturan"))
    if not site.support_hours:
        items.append(Reminder("Jam kerja layanan belum diisi.", "panel:pengaturan"))
    accounts = list(BankAccount.objects.filter(is_active=True))
    if not accounts or any(a.is_placeholder for a in accounts):
        items.append(Reminder("Info rekening bank masih contoh.", "panel:pengaturan"))
    if not site.qris_image:
        items.append(Reminder("Gambar QRIS belum diunggah.", "panel:pengaturan"))
    for pkg in Package.objects.filter(is_active=True, price=0).exclude(category=Package.CATEGORY_SERVICE):
        items.append(Reminder(
            f"Harga {pkg.product_short} Paket {pkg.name} belum diisi: tampil \"Segera diumumkan\" dan belum bisa dipesan.",
            "panel:paket-list",
        ))
    for page in LegalPage.objects.filter(is_draft=True):
        items.append(Reminder(f"Halaman '{page.title}' masih draf. Tinjau lalu matikan tanda draf.", "panel:legal-list"))
    return items
