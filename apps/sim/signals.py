"""Hapus file pribadi (scan KK/KTP, tanda tangan, cap) saat datanya dihapus.

Berlaku juga untuk penghapusan berantai (wilayah dihapus 30 hari setelah masa aktif habis).
File dihapus setelah transaksi berhasil, supaya file tidak hilang bila penghapusan dibatalkan.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import DokumenScan, Wilayah


def _delete_later(field_file) -> None:
    if field_file and field_file.name:
        storage, name = field_file.storage, field_file.name
        transaction.on_commit(lambda: storage.delete(name))


@receiver(post_delete, sender=DokumenScan)
def delete_scan_file(sender, instance, **kwargs):
    _delete_later(instance.gambar)


@receiver(post_delete, sender=Wilayah)
def delete_signature_files(sender, instance, **kwargs):
    _delete_later(instance.ttd)
    _delete_later(instance.cap)
