"""Test general db interaction."""

import os
import subprocess

# TODO change to pointsources
from etk.edb.models import Vehicle
from etk.tools import Editor


def test_init_db(tmpdir):
    """test to initialize an offline database."""
    filepath = tmpdir / "test.sqlite"
    os.environ["ETK_DATABASE_PATH"] = str(filepath)
    editor = Editor()
    editor.init()
    assert filepath.exists(), "no database created"


def test_edit_test_db(db):
    Vehicle.objects.create(name="car")
    assert Vehicle.objects.filter(name="car").exists(), "no record created"


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
