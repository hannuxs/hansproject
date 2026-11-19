"""Utilitas log: rotasi file yang aman di Windows dan penyaring data sensitif."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

_SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|otp|kode|csrfmiddlewaretoken|sessionid|api[_-]?key)"
    r"(\s*[=:]\s*|['\"]\s*:\s*['\"]?)([^\s,'\"&;}]+)"
)


def redact(text: str) -> str:
    return _SECRET_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)


class RedactSecretsFilter(logging.Filter):
    """Menyamarkan nilai yang tampak seperti password/token di pesan log."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - pesan log rusak
            return True
        cleaned = redact(message)
        if cleaned != message:
            record.msg, record.args = cleaned, ()
        return True


class SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler yang tidak menghentikan aplikasi bila rotasi gagal.

    Di Windows, rotasi bisa gagal (PermissionError) bila file log sedang
    dibuka proses lain. Dalam kasus itu log tetap ditulis ke file yang sama
    dan rotasi dicoba lagi pada pesan berikutnya.
    """

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except OSError:
            if self.stream is None:
                self.stream = self._open()
