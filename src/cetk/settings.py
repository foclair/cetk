"""Django settings for the offline-editor."""

import os

DEBUG = os.environ.get("CETK_DEBUG", False)

if "FLATPAK_ID" in os.environ:
    SPATIALITE_LIBRARY_PATH = "/app/lib/mod_spatialite.so"
elif os.name == "posix":
    SPATIALITE_LIBRARY_PATH = "/usr/lib64/mod_spatialite.so"
elif os.name == "nt":
    SPATIALITE_LIBRARY_PATH = r"C:\OSGeo4W\bin\mod_spatialite.dll"
else:
    SPATIALITE_LIBRARY_PATH = "/usr/lib64/mod_spatialite.so"

# Application definition
INSTALLED_APPS = [
    "django.contrib.gis",
    "cetk.edb.apps.EdbConfig",
]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Database
# directory where template database will be stored
DATABASE_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
    "eclair",
)
os.makedirs(DATABASE_DIR, exist_ok=True)

# get database path from environment variable
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.spatialite",
        "NAME": os.environ.get(
            "CETK_DATABASE_PATH", os.path.join(DATABASE_DIR, "eclair.gpkg")
        ),
        "TEST": {"NAME": os.path.join(DATABASE_DIR, "test.eclair.gpkg")},
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
    cetk_logger = {"handlers": ["console_debug"], "level": level}
else:
    cetk_logger = {"handlers": ["console"], "level": level}

LOGGING = {
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
        "console_debug": {"class": "logging.StreamHandler", "formatter": "cetk_debug"},
    },
    "loggers": {"cetk": cetk_logger},
}

if os.name == "nt":

    OSGEO4W = r"C:\OSGeo4W"
    assert os.path.isdir(OSGEO4W), "Directory does not exist: " + OSGEO4W
    os.environ["OSGEO4W_ROOT"] = OSGEO4W
    os.environ["GDAL_DATA"] = OSGEO4W + r"\share\gdal"
    os.environ["PROJ_LIB"] = OSGEO4W + r"\share\proj"
    # TODO this should look for which gdal version is located here, not hardcoded!
    # os.environ['GDAL_LIBRARY_PATH'] = OSGEO4W + r"\bin\gdal308"
    os.environ["PATH"] = OSGEO4W + r"\bin;" + os.environ["PATH"]
