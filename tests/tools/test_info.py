"""Test to create database."""

from etk.tools.utils import run_get_settings, run_update_settings


def test_run_get_settings(inventory, tmpdir):

    settings = run_get_settings(db_path=inventory)
    assert settings.srid == 3006


def test_run_update_settings(inventory, tmpdir):
    run_update_settings(db_path=inventory, srid=31276)
    settings = run_get_settings(db_path=inventory)
    assert settings.srid == 31276
