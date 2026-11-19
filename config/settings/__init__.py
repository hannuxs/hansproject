"""Memilih setelan sesuai APP_ENV di file .env.

- development : komputer pengembangan
- production  : server (menolak berjalan bila konfigurasinya berbahaya)
- test        : tes otomatis
"""
from config.env import APP_ENV

if APP_ENV == "production":
    from .production import *  # noqa: F401,F403
elif APP_ENV == "test":
    from .test import *  # noqa: F401,F403
elif APP_ENV == "development":
    from .development import *  # noqa: F401,F403
else:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        f"APP_ENV={APP_ENV!r} tidak dikenal. Pilih: development, production, atau test."
    )
