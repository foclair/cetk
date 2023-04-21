"""Database management."""

import shutil
import os
import json
from pathlib import Path
import django
from django.conf import settings

class EtkDatabaseError(Exception):
    pass


def migrate_db():
    try:
        os.system("eclairmanage migrate")
    except Exception as err:
        raise EtkDatabaseError(f"Error while initializing database: {err}")
