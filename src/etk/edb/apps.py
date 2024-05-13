from django.apps import AppConfig


class EdbConfig(AppConfig):
    name = "etk.edb"
    verbose_name = "ETK Emission Database"

    def ready(self):
        from . import signals  # noqa
