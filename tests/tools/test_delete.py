"""Tests for emission model importers."""

from importlib import resources

import pytest

from cetk.edb.importers import import_sources
from cetk.edb.models import PointSource
from cetk.edb.utils import delete_sources


@pytest.fixture
def pointsource_xlsx(tmpdir, settings):
    return resources.files("edb.data") / "pointsources.xlsx"


class TestDelete:
    """Test deleting pointsources."""

    def test_delete_pointsources(self, code_sets, pointsource_xlsx):
        # create pointsources
        import_sources(pointsource_xlsx, sourcetype="point")
        nr_sources = PointSource.objects.count()
        delete_sources(PointSource, ["1"])
        assert PointSource.objects.count() == nr_sources - 1
