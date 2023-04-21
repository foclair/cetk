"""etk, a python library for editing Clair emission inventories offline."""

__version__ = "0.0.1.dev"

import os
from pathlib import Path
from django.conf import settings
import django

DEFAULT_SETTINGS = {
    'DEBUG': False,
    'INSTALLED_APPS': [
        'django.contrib.gis',
        'etk.edb.apps.EdbConfig',
        'rest_framework'
    ],
    'DATABASE_ROUTERS': ['dynamic_db_router.DynamicDbRouter'],
    'LANGUAGE_CODE': 'en-us',
    'TIME_ZONE': 'UTC',
    'USE_I18N': True,
    'USE_L10N': True,
    'USE_TZ': True
}

def configure():
    if hasattr(settings, "configured") and not settings.configured:
        default_config_home = os.path.expanduser('~/.config')
        config_home = Path(os.environ.get('XDG_CONFIG_HOME', default_config_home))
        default_db = config_home / "default.sqlite"
        db_path = os.environ.get("ETK_DATABASE_PATH", str(default_db.absolute))
        settings.configure(
            **DEFAULT_SETTINGS,
            DATABASES={
                'default': {
                    'ENGINE': 'django.contrib.gis.db.backends.spatialite',
                    'NAME': db_path,
                    'TEST': {
                        'TEMPLATE': 'default.sqlite'
                    },
                },
            }
        )
        django.setup()
    return settings
