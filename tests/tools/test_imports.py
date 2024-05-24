"""Tests for emission model importers."""

import os
import re
from importlib import resources

import pytest

from etk.db import run_migrate
from etk.tools.utils import run_import


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
    os.environ["ETK_DATABASE_PATH"] = str(db_path)
    return db_path


def test_import_pointsources(tmp_db, pointsourceactivities_xlsx, validation_xlsx):
    run_migrate(db_path=tmp_db)

    # Regular expression pattern to extract the dictionary part
    pattern = r"imported data (.+)\\n"

    (stderr, stdout) = run_import(pointsourceactivities_xlsx, db_path=tmp_db)
    # Find the dictionary part using regular expression
    match = re.search(pattern, str(stdout))
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
    assert eval(match.group(1)) == expected_dict

    # from etk.tools.utils import CalledProcessError
    # try:
    (stderr, stdout) = run_import(validation_xlsx, db_path=tmp_db, dry_run=True)
    # except CalledProcessError as e:
    #    error = e.stderr.decode("utf-8")
    #    print(error)
    assert "ERROR" in str(stdout)


def test_import_traffic(tmp_db, traffic_xlsx):
    run_migrate(db_path=tmp_db)

    # Regular expression pattern to extract the dictionary part
    pattern = r"imported data (.+)\\n"

    (stderr, stdout) = run_import(traffic_xlsx, db_path=tmp_db)
    match = re.search(pattern, str(stdout))
    expected_dict = {
        "codeset": {"updated": 0, "created": 3},
        "activitycode": {"updated": 0, "created": 9},
        "roads": {"created": 26, "updated": 0},
        "vehicle_emission_factors": {"updated": 0, "created": 6},
    }
    assert eval(match.group(1)) == expected_dict
