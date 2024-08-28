""" Unit tests for the ltreefield lookups. """
import pytest

from cetk.edb.models.source_models import ActivityCode, CodeSet


@pytest.fixture
def activity_codes(db):
    codeset = CodeSet.objects.create(name="TestCodeSet")
    codes = []
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
        codes.append(codeset.codes.create(code=ltreecode, label=f"{ltreecode}-label"))
    return codes


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
def test_match(activity_codes, ltreecode, expected):
    actual = ActivityCode.objects.filter(code__match=ltreecode).values_list(
        "code", flat=True
    )
    assert set(actual) == expected


@pytest.mark.parametrize(
    "ltreecode, expected",
    [("1", {"", "1"}), ("1.1", {"", "1", "1.1"}), ("4", {""})],
)
def test_aore(activity_codes, ltreecode, expected):
    actual = ActivityCode.objects.filter(code__aore=ltreecode).values_list(
        "code", flat=True
    )
    assert set(actual) == expected


@pytest.mark.parametrize(
    "ltreecode, expected",
    [("2", {"2", "2.1", "2.1.1"}), ("1.3", {"1.3", "1.3.1", "1.3.1.1", "1.3.2"})],
)
def test_dore(activity_codes, ltreecode, expected):
    actual = ActivityCode.objects.filter(code__dore=ltreecode).values_list(
        "code", flat=True
    )
    assert set(actual) == expected
