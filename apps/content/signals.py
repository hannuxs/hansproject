"""Hapus cache konten setiap kali data yang tampil di website berubah."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import services
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
    Testimonial,
)

CONTENT_MODELS = (
    AddOn, BankAccount, ComparisonRow, Faq, IncludedFeature, LegalPage,
    Package, PackageFeature, PackageNote, SiteSettings, Testimonial,
)


@receiver(post_save)
@receiver(post_delete)
def clear_content_cache(sender, **kwargs):
    if sender in CONTENT_MODELS:
        services.invalidate()
