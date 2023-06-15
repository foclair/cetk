"""Django settings for the offline-editor."""

import os

DEBUG = False

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
