"""Database management."""

import os
import sqlite3
import subprocess


class CetkDatabaseError(Exception):
    pass


def run_migrate(db_path=None):
    env = {**os.environ}
    if db_path is not None:
        env["CETK_DATABASE_PATH"] = str(db_path)

        # handle error in geodjango starting with sqlite 3.36
        # see: https://groups.google.com/g/spatialite-users/c/SnNZt4AGm_o
        sqlite_version = list(map(int, sqlite3.sqlite_version.split(".")))
        if sqlite_version[0] >= 3 and sqlite_version[1] >= 36:
            proc = subprocess.run(
                [
                    "cetkmanage",
                    "shell",
                    "-c",
                    "import django;django.db.connection.cursor().execute('SELECT InitSpatialMetaData(1);')",  # noqa: E501
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                env=env,
            )

    proc = subprocess.run(
        ["cetkmanage", "migrate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        env=env,
    )
    return proc.stdout, proc.stderr
