import pytest

from etk.edb.models import PointSource


@pytest.fixture
def pointsources(db):
    point1 = PointSource.objects.create(name="pointsource")
    return [point1]
