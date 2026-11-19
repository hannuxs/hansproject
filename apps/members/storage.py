"""Penyimpanan file PRIBADI (bukti bayar).

Berbeda dengan folder ``media`` (gambar publik seperti QRIS), file di sini
TIDAK punya alamat publik. File hanya bisa dibuka lewat view yang memeriksa
pemiliknya (pelanggan yang bersangkutan) atau pengelola panel.
"""
from __future__ import annotations

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_MEDIA_ROOT)
        kwargs.setdefault("base_url", None)
        super().__init__(**kwargs)

    def url(self, name):  # tidak pernah punya URL publik
        raise ValueError("File pribadi tidak punya alamat publik.")


def private_storage() -> PrivateStorage:
    """Dipanggil saat dipakai (bukan saat import), jadi lokasi folder bisa diatur dari .env."""
    return PrivateStorage()
