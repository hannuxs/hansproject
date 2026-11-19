from django.apps import AppConfig


class ContentConfig(AppConfig):
    name = "apps.content"
    label = "content"
    verbose_name = "Konten situs"

    def ready(self) -> None:
        from . import signals  # noqa: F401
