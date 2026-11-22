"""Mengisi data awal. Aman dijalankan berulang kali.

- Jalan pertama: semua data awal dibuat.
- Jalan berikutnya: tidak melakukan apa-apa (ditandai ``SiteSettings.seeded_at``),
  supaya data yang sudah diubah/dihapus pemilik tidak dikembalikan.
- ``only_missing=True``: hanya menambahkan data awal yang belum ada,
  tanpa menimpa data yang sudah ada.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from . import seed_data as data
from .models import (
    AddOn,
    BankAccount,
    ComparisonRow,
    Faq,
    IncludedFeature,
    LegalPage,
    Package,
    PackageFeature,
    PackageNote,
    SiteSettings,
)

PACKAGE_FIELDS = (
    "category", "name", "icon", "tagline", "description", "price", "price_prefix", "price_suffix",
    "monthly_price", "outlet_count", "scan_limit", "badge", "is_highlighted", "order",
)


@transaction.atomic
def seed(*, only_missing: bool = False) -> dict[str, int]:
    site = SiteSettings.load()
    if site.seeded_at and not only_missing:
        return {}
    created: dict[str, int] = {}

    def bump(key: str, n: int = 1) -> None:
        created[key] = created.get(key, 0) + n

    by_code: dict[str, Package] = {}
    all_packages = data.PACKAGES + data.SIM_PACKAGES
    for spec in all_packages:
        defaults = {k: spec[k] for k in PACKAGE_FIELDS if k in spec}
        pkg, is_new = Package.objects.get_or_create(code=spec["code"], defaults=defaults)
        by_code[pkg.code] = pkg
        if not is_new:
            continue
        bump("paket")
        PackageFeature.objects.bulk_create(
            PackageFeature(package=pkg, simple=s, technical=t, icon=i, show_in_highlights=h, order=(n + 1) * 10)
            for n, (s, t, i, h) in enumerate(spec.get("features", []))
        )
        PackageNote.objects.bulk_create(
            PackageNote(package=pkg, simple=s, technical=t, order=(n + 1) * 10)
            for n, (s, t) in enumerate(spec.get("notes", []))
        )
    for spec in all_packages:
        parent = by_code.get(spec.get("includes_code", ""))
        pkg = by_code[spec["code"]]
        if parent and pkg.includes_from_id is None:
            pkg.includes_from = parent
            pkg.save(update_fields=["includes_from"])

    if not IncludedFeature.objects.exists():
        IncludedFeature.objects.bulk_create(
            IncludedFeature(simple=s, technical=t, icon=i, order=(n + 1) * 10) for n, (s, t, i) in enumerate(data.INCLUDED)
        )
        bump("termasuk", len(data.INCLUDED))

    for n, (group, name, price, unit, desc) in enumerate(data.ADDONS):
        _, is_new = AddOn.objects.get_or_create(
            group=group, name=name, defaults={"price": price, "unit": unit, "description": desc, "order": (n + 1) * 10}
        )
        if is_new:
            bump("tambahan")

    sim_values = dict(data.SIM_COMPARISON)
    labels = [label for label, _ in data.COMPARISON] + [label for label, _ in data.SIM_COMPARISON if label not in dict(data.COMPARISON)]
    for n, label in enumerate(labels):
        values = {**dict(data.COMPARISON).get(label, {}), **sim_values.get(label, {})}
        _, is_new = ComparisonRow.objects.get_or_create(label=label, defaults={"values": values, "order": (n + 1) * 10})
        if is_new:
            bump("tabel")

    faqs = [(q, a, active, data.FAQ_TOPICS.get(q, "umum")) for q, a, active in data.FAQS] + list(data.SIM_FAQS)
    for n, (question, answer, active, topic) in enumerate(faqs):
        _, is_new = Faq.objects.get_or_create(
            question=question, defaults={"answer": answer, "is_active": active, "topic": topic, "order": (n + 1) * 10}
        )
        if is_new:
            bump("faq")

    for slug, title, body in data.LEGAL_PAGES:
        _, is_new = LegalPage.objects.get_or_create(slug=slug, defaults={"title": title, "body": body, "is_draft": False})
        if is_new:
            bump("legal")

    if not BankAccount.objects.exists():
        bank, number, holder = data.BANK_PLACEHOLDER
        BankAccount.objects.create(bank_name=bank, account_number=number, account_holder=holder, order=10)
        bump("rekening")

    if not site.seeded_at:
        site.seeded_at = timezone.now()
        site.save()
    return created
