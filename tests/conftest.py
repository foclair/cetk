import pytest

from etk.edb.models import Vehicle

SPEEDS = ["20", "30", "40", "50", "60", "70", "80", "90", "100", "110", "120", "130"]
ROADTYPES = ["highway", "primary", "secondary", "tertiary", "residential", "busway"]


@pytest.fixture
def vehicles(db):
    car = Vehicle.objects.create(name="car", isheavy=False)
    truck = Vehicle.objects.create(name="truck", isheavy=True)
    return [car, truck]
