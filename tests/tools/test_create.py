"""Test to create database."""

from cetk.tools.utils import run


def test_create(db, tmpdir):
    db_path = tmpdir / "copied_from_template.sqlite"
    run("cetk", "create", str(db_path))
    assert db_path.exists()
