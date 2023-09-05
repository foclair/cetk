"""etk, a python library for editing Clair emission inventories offline."""

__version__ = "0.0.1.dev"

import os

import django
from django.conf import settings

DEFAULT_SETTINGS = {
    "DEBUG": False,
    "INSTALLED_APPS": ["django.contrib.gis", "etk.edb.apps.EdbConfig"],
    "LANGUAGE_CODE": "en-us",
    "TIME_ZONE": "UTC",
    "USE_I18N": True,
    "USE_TZ": True,
}


def configure():
    if hasattr(settings, "configured") and not settings.configured:
        default_config_home = os.path.expanduser("~/.config")
        config_home = os.path.join(
            os.environ.get("XDG_CONFIG_HOME", default_config_home), "eclair"
        )
        default_db = os.path.abspath(os.path.join(config_home, "eclair.sqlite"))
        db_path = os.environ.get("ETK_DATABASE_PATH", default_db)
        settings.configure(
            **DEFAULT_SETTINGS,
            DATABASES={
                "default": {
                    "ENGINE": "django.contrib.gis.db.backends.spatialite",
                    "NAME": db_path,
                    "TEST": {"TEMPLATE": "default.sqlite"},
                },
            }
        )
        django.setup()
    return settings
