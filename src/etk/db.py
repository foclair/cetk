"""Database management."""

import os
import subprocess


class EtkDatabaseError(Exception):
    pass


def run_migrate(db_path=None):
    env = {**os.environ}
    if db_path is not None:
        env["ETK_DATABASE_PATH"] = db_path

    proc = subprocess.run(
        ["etkmanage", "migrate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        env=env,
    )
    return proc.stdout, proc.stderr
