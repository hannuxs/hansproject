"""Awalan nama tabel untuk SEMUA model, termasuk tabel bawaan Django.

Database di server produksi sudah berisi tabel dan data lain. Supaya tidak
pernah bertabrakan (misalnya dengan tabel ``auth_user`` atau
``django_migrations`` milik aplikasi lain), setiap tabel aplikasi ini diberi
awalan ``hp_``: ``hp_auth_permission``, ``hp_django_migrations``, dst.

Receiver dipasang saat ``apps.core`` dimuat (fase pertama ``django.setup()``),
sebelum model apa pun dibuat, sehingga juga berlaku untuk model historis yang
dipakai migrasi dan untuk tabel catatan migrasi Django.
"""
from __future__ import annotations

from django.db.models.signals import class_prepared

MAX_TABLE_NAME = 64  # batas panjang nama tabel MariaDB


def get_prefix() -> str:
    from django.conf import settings

    return getattr(settings, "DB_TABLE_PREFIX", "hp_")


def prefixed(table: str, prefix: str | None = None) -> str:
    prefix = get_prefix() if prefix is None else prefix
    if not prefix or table.startswith(prefix):
        return table
    return (prefix + table)[:MAX_TABLE_NAME]


def add_table_prefix(sender, **kwargs) -> None:
    opts = sender._meta
    if opts.proxy:  # model proxy memakai tabel induknya (sudah berawalan)
        return
    opts.db_table = prefixed(opts.db_table)


def install() -> None:
    class_prepared.connect(add_table_prefix, dispatch_uid="hans_table_prefix")
