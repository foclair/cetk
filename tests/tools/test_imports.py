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
def tmp_db(tmpdir):
    db_path = tmpdir / "test.sqlite"
    os.environ["ETK_DATABASE_PATH"] = str(db_path)
    return db_path


def test_import_pointsources(tmp_db, pointsourceactivities_xlsx):
    run_migrate(db_path=tmp_db)

    # Regular expression pattern to extract the dictionary part
    pattern = r"imported data (.+)\\n"

    stdout = run_import(pointsourceactivities_xlsx, db_path=tmp_db)
    # Find the dictionary part using regular expression
    match = re.search(pattern, str(stdout[1]))
    expected_dict = {
        "codeset": {"updated": 0, "created": 2},
        "activitycode": {"updated": 0, "created": 3},
        "activity": {"updated": 0, "created": 2},
        "emission_factors": {"updated": 0, "created": 4},
        "timevar": {"updated or created": 2},
        "facility": {"updated": 0, "created": 4},
        "pointsource": {"updated": 0, "created": 4},
    }
    assert eval(match.group(1)) == expected_dict

    stdout = run_import(pointsourceactivities_xlsx, db_path=tmp_db, dry_run=True)
    assert "Successful dry-run" in str(stdout)
