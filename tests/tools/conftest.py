import os
from importlib import resources

import pytest

from cetk.db import run_migrate
from cetk.tools.utils import run_import


@pytest.fixture
def inventory_xlsx(testsettings):
    return os.path.join(resources.files("tools.data"), "inventory.xlsx")


@pytest.fixture
def test_db(tmpdir):
    db_path = os.path.join(tmpdir, "test.eclair.gpkg")
    os.environ["CETK_DATABASE_PATH"] = str(db_path)
    run_migrate(db_path=db_path)
    return db_path


@pytest.fixture
def inventory(test_db, inventory_xlsx):
    _, proc = run_import(inventory_xlsx, db_path=test_db)
    assert proc.wait() == 0
    return test_db
