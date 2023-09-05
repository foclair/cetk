"""Tests for emission model importers."""

import os
from importlib import resources

import pytest

from etk.db import run_migrate
from etk.tools.utils import CalledProcessError, run_import


@pytest.fixture
def pointsource_xlsx():
    return resources.files("edb.data") / "pointsources.xlsx"


@pytest.fixture
def tmp_db(tmpdir):
    db_path = tmpdir / "test.sqlite"
    os.environ["ETK_DATABASE_PATH"] = str(db_path)
    return db_path


def test_import_pointsources(tmp_db, pointsource_xlsx):
    run_migrate(db_path=tmp_db)
    # expected failure since codeset has not been loaded yet
    # this test should be completed
    with pytest.raises(CalledProcessError):
        run_import(pointsource_xlsx, "pointsources", unit="ton/year", db_path=tmp_db)
