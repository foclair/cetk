"""Test to create database."""

import pytest

from cetk.tools.utils import run_get_settings, run_update_settings


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_run_get_settings(inventory):
    settings = run_get_settings(db_path=inventory)
    assert settings.srid == 3006


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_run_update_settings(inventory):
    run_update_settings(db_path=inventory, srid=31276)
    settings = run_get_settings(db_path=inventory)
    assert settings.srid == 31276
