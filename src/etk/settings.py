"""Django settings for the offline-editor."""

import os

DEBUG = os.environ.get("ETK_DEBUG", False)

# SPATIALITE_LIBRARY_PATH="/usr/libspatialite50/lib/libspatialite.so.8"
SPATIALITE_LIBRARY_PATH = "/usr/lib64/mod_spatialite.so"
# Application definition
INSTALLED_APPS = [
    "django.contrib.gis",
    "etk.edb.apps.EdbConfig",
]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Database
# directory where template database will be stored
DATABASE_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "eclair"
)
os.makedirs(DATABASE_DIR, exist_ok=True)
# get database path from environment variable
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.spatialite",
        "NAME": os.environ.get(
            "ETK_DATABASE_PATH", os.path.join(DATABASE_DIR, "eclair.sqlite")
        ),
        "TEST": {"TEMPLATE": "eclair.sqlite"},
    }
}

# Internationalization
LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Logging
level = "DEBUG" if DEBUG else "INFO"

if level == "DEBUG":
    etk_logger = {"handlers": ["console_debug"], "level": level}
else:
    etk_logger = {"handlers": ["console"], "level": level}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "etk": {"format": "%(levelname)s: %(message)s"},  # noqa
        "etk_debug": {
            "format": "%(asctime)s %(levelname)s: %(name)s  %(message)s"
        },  # noqa
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "etk"},
        "console_debug": {"class": "logging.StreamHandler", "formatter": "etk_debug"},
    },
    "loggers": {"etk": etk_logger},
}
