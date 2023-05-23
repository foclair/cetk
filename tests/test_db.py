"""Test general db interaction."""

import os
import subprocess

from etk.edb.models import Activity
from etk.tools import Editor


def test_init_db(tmpdir):
    """test to initialize an offline database."""
    filepath = tmpdir / "test.sqlite"
    os.environ["ETK_DATABASE_PATH"] = str(filepath)
    editor = Editor()
    editor.init()
    assert filepath.exists(), "no database created"


def test_edit_test_db(db):
    Activity.objects.create(name="activity1", unit="m3")
    assert Activity.objects.filter(name="activity1").exists(), "no record created"


def test_eclair_cli(tmpdir):
    filepath = tmpdir / "test.sqlite"
    os.environ["ETK_DATABASE_PATH"] = str(filepath)
    try:
        subprocess.run(
            ["eclair", "init"],
            # env={"EKT_DATABASE_PATH": str(filepath)},
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        assert False, f"error: {err.stderr}"
    assert filepath.exists(), "no database file created"
