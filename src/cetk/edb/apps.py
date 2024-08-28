from django.apps import AppConfig


class EdbConfig(AppConfig):
    name = "cetk.edb"
    verbose_name = "CETK Emission Database"

    def ready(self):
        from . import signals  # noqa
