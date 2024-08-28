"""tests for general emission related functions."""


from cetk.emissions.calc import get_used_substances


def test_get_used_substances(pointsources):
    substances = get_used_substances()
    assert sorted([s.slug for s in substances]) == ["NOx", "SOx"]


def test_get_used_substances_roadclass(roadclasses):
    # coming from conftest.py, vehicle_ef
    substances = get_used_substances()
    assert sorted([s.slug for s in substances]) == ["NOx", "SOx"]
