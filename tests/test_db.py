"""Test general db interaction."""

import os
import subprocess
from pathlib import Path

from cetk.edb.models.source_models import Activity
from cetk.tools import Editor


def test_init_db(tmpdir):
    """test to initialize an offline database."""
    filepath = Path(os.path.join(tmpdir, "test.sqlite"))
    os.environ["CETK_DATABASE_PATH"] = str(filepath)
    editor = Editor()
    editor.migrate()
    assert filepath.exists(), "no database created"


def test_edit_test_db(db):
    Activity.objects.create(name="activity1", unit="m3")
    assert Activity.objects.filter(name="activity1").exists(), "no record created"


def test_cetk_cli(tmpdir):
    filepath = Path(os.path.join(tmpdir, "test.sqlite"))
    os.environ["CETK_DATABASE_PATH"] = str(filepath)
    try:
        subprocess.run(
            ["cetk", "migrate"],
            # env={"EKT_DATABASE_PATH": str(filepath)},
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        assert False, f"error: {err.stderr}"
    assert filepath.exists(), "no database file created"
