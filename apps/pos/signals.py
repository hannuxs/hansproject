"""Membersihkan file gambar halaman toko saat tokonya dihapus (mis. 30 hari setelah masa aktif habis)."""
from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Store


@receiver(post_delete, sender=Store, dispatch_uid="pos-store-page-files")
def delete_page_files(sender, instance: Store, **kwargs):
    folder = (Path(settings.MEDIA_ROOT) / "uploads" / "toko" / str(instance.pk)).resolve()
    root = (Path(settings.MEDIA_ROOT) / "uploads" / "toko").resolve()
    if root in folder.parents and folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
