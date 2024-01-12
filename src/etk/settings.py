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

if os.name == "nt":
    import platform

    OSGEO4W = r"C:\OSGeo4W"
    # if '64' in platform.architecture()[0]:
    #     OSGEO4W += "64"
    assert os.path.isdir(OSGEO4W), "Directory does not exist: " + OSGEO4W
    os.environ["OSGEO4W_ROOT"] = OSGEO4W
    os.environ["GDAL_DATA"] = OSGEO4W + r"\share\gdal"
    os.environ["PROJ_LIB"] = OSGEO4W + r"\share\proj"
    # TODO this should look for which gdal version is located here, not hardcoded!
    # os.environ['GDAL_LIBRARY_PATH'] = OSGEO4W + r"\bin\gdal308"
    os.environ["PATH"] = OSGEO4W + r"\bin;" + os.environ["PATH"]
