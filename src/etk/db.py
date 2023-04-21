"""Database management."""

import os


class EtkDatabaseError(Exception):
    pass


def migrate_db():
    try:
        os.system("eclairmanage migrate")
    except Exception as err:
        raise EtkDatabaseError(f"Error while initializing database: {err}")
