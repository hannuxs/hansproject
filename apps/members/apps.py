from django.apps import AppConfig


class MembersConfig(AppConfig):
    name = "apps.members"
    label = "members"
    verbose_name = "Akun pelanggan"

    def ready(self) -> None:
        from . import signals  # noqa: F401
