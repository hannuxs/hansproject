"""Mencatat perubahan data penting di panel (ke database dan ke file log).

Yang dicatat hanya NAMA kolom yang berubah, bukan isinya, supaya tidak ada
data sensitif yang masuk log.
"""
from __future__ import annotations

import logging

from .models import AuditLog

log = logging.getLogger("hans.security")


def record(request, action: str, obj=None, *, target_type: str = "", target_repr: str = "", detail: str = "") -> None:
    user = getattr(request, "user", None)
    is_auth = bool(user and user.is_authenticated)
    if obj is not None:
        target_type = target_type or str(obj._meta.verbose_name)
        target_repr = target_repr or str(obj)
    entry = AuditLog.objects.create(
        user=user if is_auth else None,
        username=user.get_username() if is_auth else "",
        action=action,
        target_type=target_type[:60],
        target_repr=target_repr[:200],
        detail=detail[:500],
    )
    log.info(
        "Panel: %s %s '%s' oleh %s %s",
        entry.get_action_display(), entry.target_type, entry.target_repr, entry.username or "-", detail,
    )


def changed_fields_detail(form) -> str:
    if not getattr(form, "changed_data", None):
        return ""
    labels = [str(form.fields[name].label or name) for name in form.changed_data if name in form.fields]
    return "Kolom: " + ", ".join(labels)
