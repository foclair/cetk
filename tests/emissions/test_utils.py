"""tests for general emission related functions."""

from etk.emissions.calc import get_used_substances


def test_get_used_substances(pointsources):
    substances = get_used_substances()
    assert sorted(substances) == ["NOx", "SOx"]
