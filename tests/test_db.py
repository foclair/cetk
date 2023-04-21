"""Test general db interaction."""

import os
from pathlib import Path
import pkg_resources
import subprocess
import django
import pytest
from etk.tools import Editor
from etk.edb.models import Vehicle
from django.conf import settings
from django.core.management import call_command


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
        proc = subprocess.run(
            ["eclair", "init"],
            #env={"EKT_DATABASE_PATH": str(filepath)},
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError as err:
        assert False, f"error: {err.stderr}"
    assert filepath.exists(), "no database file created"
