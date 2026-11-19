"""Menjalankan website dengan Waitress (server produksi yang mendukung Windows)."""
from __future__ import annotations

import atexit
import logging
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

log = logging.getLogger("hans")


class Command(BaseCommand):
    help = "Menjalankan website (mode produksi) dengan Waitress di alamat SERVER_HOST:SERVER_PORT."

    def handle(self, *args, **options):
        from waitress import serve

        from config.wsgi import application

        pid_file = Path(settings.RUN_DIR) / "server.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()), encoding="ascii")
        atexit.register(lambda: pid_file.unlink(missing_ok=True))

        host, port = settings.SERVER_HOST, settings.SERVER_PORT
        log.info("Website berjalan di http://%s:%s (mode: %s)", host, port, "DEBUG" if settings.DEBUG else "produksi")
        self.stdout.write(self.style.SUCCESS(f"Website berjalan di http://{host}:{port}  (tekan Ctrl+C untuk berhenti)"))

        proxy_options = {}
        if settings.TRUSTED_PROXY:
            # Header X-Forwarded-* HANYA dipercaya bila datang dari reverse proxy ini.
            proxy_options = {
                "trusted_proxy": settings.TRUSTED_PROXY,
                "trusted_proxy_count": 1,
                "trusted_proxy_headers": {"x-forwarded-for", "x-forwarded-proto"},
                "clear_untrusted_proxy_headers": True,
            }
        serve(
            application,
            host=host,
            port=port,
            threads=settings.SERVER_THREADS,
            ident="",  # jangan sebutkan nama/versi server di header
            expose_tracebacks=False,
            max_request_body_size=8 * 1024 * 1024,
            channel_timeout=60,
            connection_limit=300,
            **proxy_options,
        )
