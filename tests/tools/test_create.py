"""Test to create database."""

import filecmp
import shutil
from pathlib import Path

from django.conf import settings

from cetk.tools.utils import get_template_db, run


def test_create(db, monkeypatch, tmp_path):
    # With a template database
    xdg_config_home = str(tmp_path / "config")
    monkeypatch.setenv("XDG_CONFIG_HOME", xdg_config_home)
    template_db_path = get_template_db()
    assert template_db_path.startswith(xdg_config_home)
    Path(template_db_path).parent.mkdir(parents=True)
    shutil.copyfile(settings.DATABASES["default"]["NAME"], template_db_path)

    # Create a new cetk database
    target_path = tmp_path / "copied_from_template.gpkg"
    run("cetk", "create", str(target_path))

    # And make sure it's identical to the template database
    assert target_path.exists()
    assert filecmp.cmp(target_path, template_db_path, shallow=False)
