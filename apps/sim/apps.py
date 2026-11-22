from django.apps import AppConfig


class SimConfig(AppConfig):
    name = "apps.sim"
    label = "sim"
    verbose_name = "Sistem Informasi Manajemen (SIM)"

    def ready(self):
        from . import signals  # noqa: F401
