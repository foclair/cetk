"""cetk, a python library for editing Clair emission inventories offline."""

__version__ = "0.0.5.dev"

import os

import django
from django.conf import settings

from cetk import logging

DEFAULT_SETTINGS = {
    "DEBUG": False,
    "INSTALLED_APPS": ["django.contrib.gis", "cetk.edb.apps.EdbConfig"],
    "LANGUAGE_CODE": "en-us",
    "TIME_ZONE": "UTC",
    "USE_I18N": True,
    "USE_TZ": True,
}

log = logging.getLogger(__name__)


def configure():
    if hasattr(settings, "configured") and not settings.configured:
        default_config_home = os.path.expanduser("~/.config")
        config_home = os.path.join(
            os.environ.get("XDG_CONFIG_HOME", default_config_home), "eclair"
        )
        default_db = os.path.abspath(os.path.join(config_home, "eclair.gpkg"))
        db_path = os.environ.get("CETK_DATABASE_PATH", default_db)
        DEBUG = os.environ.get("CETK_DEBUG", False)
        level = "DEBUG" if DEBUG else "INFO"
        if level == "DEBUG":
            cetk_logger = {"handlers": ["console_debug"], "level": level}
        else:
            cetk_logger = {"handlers": ["console"], "level": level}

        if "FLATPAK_ID" in os.environ:
            spatialite_path = os.environ.get(
                "SPATIALITE_LIBRARY_PATH", "/app/lib/mod_spatialite.so"
            )
        elif os.name == "posix":
            spatialite_path = os.environ.get(
                "SPATIALITE_LIBRARY_PATH", "/usr/lib64/mod_spatialite.so"
            )
        elif os.name == "nt":
            spatialite_path = os.environ.get(
                "SPATIALITE_LIBRARY_PATH", r"C:\OSGeo4W\bin\mod_spatialite.dll"
            )
        else:
            spatialite_path = os.environ.get(
                "SPATIALITE_LIBRARY_PATH", "/usr/lib64/mod_spatialite.so"
            )

        settings.configure(
            **DEFAULT_SETTINGS,
            SPATIALITE_LIBRARY_PATH=spatialite_path,
            DATABASES={
                "default": {
                    "ENGINE": "django.contrib.gis.db.backends.spatialite",
                    "NAME": db_path,
                    "TEST": {"NAME": os.path.join(config_home, "test.eclair.gpkg")},
                },
            },
            LOGGING={
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "cetk": {"format": "%(levelname)s: %(message)s"},  # noqa
                    "cetk_debug": {
                        "format": "%(asctime)s %(levelname)s: %(name)s  %(message)s"
                    },  # noqa
                },
                "handlers": {
                    "console": {"class": "logging.StreamHandler", "formatter": "cetk"},
                    "console_debug": {
                        "class": "logging.StreamHandler",
                        "formatter": "cetk_debug",
                    },
                },
                "loggers": {"cetk": cetk_logger},
            }
        )
        django.setup()
        log.debug("configured django")
    return settings
