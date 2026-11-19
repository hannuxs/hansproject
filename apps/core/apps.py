from django.apps import AppConfig

from . import dbprefix

# Dipasang saat modul ini diimpor (sebelum model mana pun dibuat).
dbprefix.install()


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    verbose_name = "Inti"

    def ready(self) -> None:
        from . import checks  # noqa: F401  (mendaftarkan system checks)
