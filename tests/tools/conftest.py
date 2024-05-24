import os
from importlib import resources

import pytest

from etk.db import run_migrate
from etk.tools.utils import run_import


@pytest.fixture
def inventory_xlsx(testsettings):
    return resources.files("tools.data") / "inventory.xlsx"


@pytest.fixture
def test_db(tmpdir):
    db_path = tmpdir / "test.gpkg"
    os.environ["ETK_DATABASE_PATH"] = str(db_path)
    run_migrate(db_path=db_path)
    return db_path


@pytest.fixture
def inventory(test_db, inventory_xlsx):
    run_import(inventory_xlsx, db_path=test_db)
    run_import(inventory_xlsx, db_path=test_db)
    return test_db
