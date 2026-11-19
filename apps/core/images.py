"""Pemrosesan upload gambar yang aman.

- Jenis file dicek dari ISI file (dibuka dengan Pillow), bukan dari ekstensi.
- Hanya JPEG, PNG, dan WebP. SVG/GIF/format lain ditolak.
- Ukuran file dan ukuran piksel dibatasi.
- Gambar di-encode ulang sehingga metadata (EXIF, lokasi GPS, dll.) terbuang.
- Nama file diganti acak.
"""
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 30_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


@dataclass(frozen=True)
class ImageRule:
    max_side: int = 1600
    output: str = "WEBP"  # "WEBP" untuk foto, "PNG" untuk gambar tajam seperti QRIS
    quality: int = 82


PHOTO = ImageRule(max_side=800, output="WEBP")
QR_CODE = ImageRule(max_side=1200, output="PNG")
RECEIPT = ImageRule(max_side=1600, output="WEBP", quality=85)  # bukti bayar: angka harus tetap terbaca


def process_image(upload, rule: ImageRule = PHOTO) -> ContentFile:
    limit = settings.UPLOAD_MAX_BYTES
    if upload.size > limit:
        raise ValidationError(f"Ukuran file maksimal {limit // (1024 * 1024)} MB.")

    upload.seek(0)
    try:
        with Image.open(upload) as probe:
            fmt = probe.format
            probe.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError) as exc:
        raise ValidationError("File bukan gambar yang valid. Gunakan JPG, PNG, atau WebP.") from exc
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError("Format gambar tidak didukung. Gunakan JPG, PNG, atau WebP.")

    upload.seek(0)
    try:
        with Image.open(upload) as img:
            img.load()
            img = ImageOps.exif_transpose(img)
            has_alpha = img.mode in ("RGBA", "LA", "P")
            img = img.convert("RGBA" if has_alpha else "RGB")
            img.thumbnail((rule.max_side, rule.max_side), Image.Resampling.LANCZOS)
            # Salin piksel ke gambar baru: metadata lama tidak ikut terbawa.
            clean = Image.new(img.mode, img.size)
            clean.paste(img)
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("Gambar tidak bisa diproses. Coba file lain.") from exc

    buffer = io.BytesIO()
    if rule.output == "PNG":
        clean.save(buffer, "PNG", optimize=True)
        ext = "png"
    else:
        clean.save(buffer, "WEBP", quality=rule.quality, method=6)
        ext = "webp"
    return ContentFile(buffer.getvalue(), name=f"{uuid.uuid4().hex}.{ext}")
