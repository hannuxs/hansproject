from django.apps import AppConfig


class PosConfig(AppConfig):
    name = "apps.pos"
    label = "pos"
    verbose_name = "Aplikasi kasir"

    def ready(self):
        from . import signals  # noqa: F401
