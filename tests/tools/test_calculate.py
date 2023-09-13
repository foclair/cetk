"""Tests for emission model importers."""

import os

import pytest

# from etk.tools.utils import run_aggregate_emissions, run_update_emission_tables


# TODO, add tests of emission calculations


@pytest.fixture
def tmp_db(tmpdir):
    db_path = tmpdir / "test.sqlite"
    os.environ["ETK_DATABASE_PATH"] = str(db_path)
    return db_path


def test_aggregate_emissions(tmp_db):
    pass
