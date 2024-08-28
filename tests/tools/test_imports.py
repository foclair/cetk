"""Tests for emission model importers."""

import glob
import os
from importlib import resources
from tempfile import gettempdir

import pytest

from cetk.db import run_migrate
from cetk.tools.utils import run_import


@pytest.fixture
def pointsourceactivities_xlsx():
    return resources.files("edb.data") / "pointsourceactivities.xlsx"


@pytest.fixture
def traffic_xlsx():
    return resources.files("edb.data") / "TrafficImportFormat.xlsx"


@pytest.fixture
def validation_xlsx():
    return resources.files("tools.data") / "validation.xlsx"


@pytest.fixture
def tmp_db(tmpdir):
    db_path = tmpdir / "test.sqlite"
    os.environ["CETK_DATABASE_PATH"] = str(db_path)
    return db_path


def test_import_pointsources(tmp_db, pointsourceactivities_xlsx, validation_xlsx):
    run_migrate(db_path=tmp_db)
    backup_path, proc = run_import(pointsourceactivities_xlsx, db_path=tmp_db)
    proc.wait()
    # Read the latest stderr file
    stderr_files = glob.glob(os.path.join(gettempdir(), "cetk_import_*_stderr.log"))
    stderr_files.sort(key=lambda f: int(f.split("_")[-2]))
    if stderr_files:
        latest_stderr_file = stderr_files[-1]
        with open(latest_stderr_file, "r") as f:
            stderr_content = f.read()
    # Find the dictionary part using regular expression
    changes = eval(stderr_content.split("\n")[-2].split("imported")[1].strip())
    expected_dict = {
        "codeset": {"updated": 0, "created": 2},
        "activitycode": {"updated": 0, "created": 3},
        "activity": {"updated": 0, "created": 2},
        "emission_factors": {"updated": 0, "created": 4},
        "timevar": {"updated or created": 2},
        "facility": {"updated": 0, "created": 4},
        "pointsource": {"updated": 0, "created": 4},
        "pointsourceactivity": {"created": 3, "updated": 0},
    }
    assert changes == expected_dict

    backup_path, proc = run_import(validation_xlsx, db_path=tmp_db, dry_run=True)
    proc.wait()
    # Read the latest stderr file
    stderr_files = glob.glob(os.path.join(gettempdir(), "cetk_import_*_stderr.log"))
    stderr_files.sort(key=lambda f: int(f.split("_")[-2]))
    if stderr_files:
        latest_stderr_file = stderr_files[-1]
        with open(latest_stderr_file, "r") as f:
            stderr_content = f.read()
    assert "ERROR" in stderr_content


def test_import_traffic(tmp_db, traffic_xlsx):
    run_migrate(db_path=tmp_db)
    backup_path, proc = run_import(traffic_xlsx, db_path=tmp_db)
    proc.wait()
    expected_dict = {
        "codeset": {"updated": 0, "created": 3},
        "activitycode": {"updated": 0, "created": 9},
        "roads": {"created": 26, "updated": 0},
        "vehicle_emission_factors": {"updated": 0, "created": 6},
    }

    # Read the latest stderr file
    stderr_files = glob.glob(os.path.join(gettempdir(), "cetk_import_*_stderr.log"))
    stderr_files.sort(key=lambda f: int(f.split("_")[-2]))
    if stderr_files:
        latest_stderr_file = stderr_files[-1]
        with open(latest_stderr_file, "r") as f:
            stderr_content = f.read()
    changes = eval(stderr_content.split("\n")[-2].split("imported")[1].strip())
    assert changes == expected_dict
