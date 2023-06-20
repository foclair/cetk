""" Unit tests for the ltreefield lookups. """
import pytest

from etk.edb.models.source_models import ActivityCode


# See https://www.postgresql.org/docs/9.1/ltree.html for more examples of a lquery.
@pytest.mark.parametrize(
    "ltreecode, expected",
    [
        # lquery expressions to select a specific ltree code.
        ("1", {"1"}),
        ("1.1", {"1.1"}),
        ("4", set()),
        # lquery expression to select a ltree code and all its children
        # and childrens children.
        # ("1.3.*", {"1.3", "1.3.1", "1.3.1.1", "1.3.2"}),
        # alternative for SQLite and 'like'
        ("1.3%", {"1.3", "1.3.1", "1.3.1.1", "1.3.2"}),
    ],
)
def test_match(ifactory, activity_codes, ltreecode, expected):
    actual = ActivityCode.objects.filter(code__match=ltreecode).values_list(
        "code", flat=True
    )
    assert set(actual) == expected


@pytest.mark.parametrize(
    "ltreecode, expected",
    [("1", {"", "1"}), ("1.1", {"", "1", "1.1"}), ("4", {""})],
)
def test_aore(ifactory, activity_codes, ltreecode, expected):
    actual = ActivityCode.objects.filter(code__aore=ltreecode).values_list(
        "code", flat=True
    )
    assert set(actual) == expected


@pytest.mark.parametrize(
    "ltreecode, expected",
    [("2", {"2", "2.1", "2.1.1"}), ("1.3", {"1.3", "1.3.1", "1.3.1.1", "1.3.2"})],
)
def test_dore(ifactory, activity_codes, ltreecode, expected):
    actual = ActivityCode.objects.filter(code__dore=ltreecode).values_list(
        "code", flat=True
    )
    assert set(actual) == expected


@pytest.fixture
def activity_codes(ifactory):
    for ltreecode in [
        "",
        "1",
        "1.1",
        "1.2",
        "1.3",
        "1.3.1",
        "1.3.1.1",
        "1.3.2",
        "2",
        "2.1",
        "2.1.1",
        "3",
    ]:
        ifactory.edb.activitycode(code=ltreecode)
