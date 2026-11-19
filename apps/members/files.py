"""Menyimpan & menyajikan file pribadi (bukti bayar) dengan aman."""
from __future__ import annotations

from django.http import FileResponse, Http404
from django.utils import timezone

from .models import Order

CONTENT_TYPES = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg"}


def replace_proof(order: Order, content) -> None:
    """Simpan bukti bayar baru (sudah diproses ulang), hapus file lama, ubah status jadi 'dicek'."""
    old_name = order.payment_proof.name if order.payment_proof else ""
    order.payment_proof.save(content.name, content, save=False)
    order.proof_uploaded_at = timezone.now()
    order.status = Order.STATUS_CHECKING
    order.save(update_fields=["payment_proof", "proof_uploaded_at", "status", "updated_at"])
    if old_name and old_name != order.payment_proof.name:
        order.payment_proof.storage.delete(old_name)


def serve_private(field_file) -> FileResponse:
    name = field_file.name or ""
    suffix = name[name.rfind(".") :].lower() if "." in name else ""
    content_type = CONTENT_TYPES.get(suffix)
    if not content_type or not field_file.storage.exists(name):
        raise Http404
    response = FileResponse(field_file.storage.open(name, "rb"), content_type=content_type)
    response["Content-Disposition"] = "inline"
    response["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'none'; sandbox"
    response["Cache-Control"] = "private, no-store"
    return response
