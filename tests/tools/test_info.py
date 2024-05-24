"""Test to create database."""

from etk.tools.utils import run_get_settings


def test_run_get_settings(inventory, tmpdir):

    settings = run_get_settings(db_path=inventory)
    assert settings.srid == 3857


def test_update_settings_srid(inventory, tmpdir):
    settings = run_get_settings(db_path=inventory, srid=31276)
    assert settings.srid == 31276
