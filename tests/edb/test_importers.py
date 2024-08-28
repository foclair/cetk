"""Tests for emission model importers."""

from importlib import resources

import pytest

from cetk.edb.importers import (
    import_gridsources,
    import_sourceactivities,
    import_sources,
)
from cetk.edb.models import (
    AreaSource,
    AreaSourceActivity,
    CodeSet,
    GridSource,
    PointSource,
    PointSourceActivity,
    get_gridsource_raster,
)
from cetk.edb.units import emis_conversion_factor_from_si


@pytest.fixture
def pointsource_csv(tmpdir, settings):
    return resources.files("edb.data") / "pointsources.csv"


@pytest.fixture
def pointsource_xlsx(tmpdir, settings):
    return resources.files("edb.data") / "pointsources.xlsx"


@pytest.fixture
def areasource_xlsx(tmpdir, settings):
    return resources.files("edb.data") / "areasources.xlsx"


@pytest.fixture
def gridsource_xlsx(tmpdir, settings):
    return resources.files("edb.data") / "gridsources.xlsx"


class TestImport:

    """Test importing point-sources from csv."""

    def test_import_pointsources(
        self, vertical_dist, pointsource_csv, pointsource_xlsx
    ):

        # similar to base_set in gadget
        cs1 = CodeSet.objects.create(name="code set 1", slug="code_set1")
        cs1.codes.create(code="1", label="Energy")
        cs1.codes.create(
            code="1.1", label="Stationary combustion", vertical_dist=vertical_dist
        )
        cs1.codes.create(
            code="1.2", label="Fugitive emissions", vertical_dist=vertical_dist
        )
        cs1.codes.create(code="1.3", label="Road traffic", vertical_dist=vertical_dist)
        cs1.save()
        cs2 = CodeSet.objects.create(name="code set 2", slug="code_set2")
        cs2.codes.create(code="A", label="Bla bla")
        cs2.save()
        # create pointsources
        import_sources(pointsource_csv, sourcetype="point")

        assert PointSource.objects.all().count()
        source1 = PointSource.objects.get(name="source1")

        assert source1.name == "source1"
        assert source1.tags["tag1"] == "val1"
        assert source1.timevar is None
        assert source1.substances.all().count() == 1
        assert source1.activitycode1.code == "1.3"
        assert source1.activitycode2.code == "A"
        source1_nox = source1.substances.get(substance__slug="NOx")
        emis_value = source1_nox.value * emis_conversion_factor_from_si("ton/year")
        assert emis_value == pytest.approx(1.0, 1e-4)

        source1.tags["test_tag"] = "test"
        source1.save()
        # update pointsources from xlsx
        import_sources(pointsource_xlsx, sourcetype="point")

        # check that source has been overwritten
        source1 = PointSource.objects.get(name="source1")
        assert "test_tag" not in source1.tags

    def test_import_pointsourceactivities(
        self, vertical_dist, pointsource_csv, pointsource_xlsx
    ):
        # similar to base_set in gadget
        cs1 = CodeSet.objects.create(name="code set 1", slug="code_set1")

        cs1.codes.create(
            code="1.1", label="Stationary combustion", vertical_dist=vertical_dist
        )
        cs1.codes.create(
            code="1.2", label="Fugitive emissions", vertical_dist=vertical_dist
        )
        cs1.codes.create(code="1.3", label="Road traffic", vertical_dist=vertical_dist)
        cs1.save()
        cs2 = CodeSet.objects.create(name="code set 2", slug="code_set2")
        cs2.codes.create(code="A", label="Bla bla")
        cs2.save()
        # create pointsources
        filepath = resources.files("edb.data") / "pointsourceactivities.xlsx"
        # test if create pointsourceactivities works
        import_sourceactivities(filepath)
        assert PointSourceActivity.objects.all().count() > 0
        # test if update also works
        import_sourceactivities(filepath)
        assert PointSourceActivity.objects.all().count() > 0

    def test_import_areasources(self, vertical_dist, areasource_xlsx):

        # similar to base_set in gadget
        cs1 = CodeSet.objects.create(name="SNAP", slug="SNAP")
        cs1.codes.create(code="1.3", label="Energy", vertical_dist=vertical_dist)
        cs1.save()
        # create areasources
        import_sources(areasource_xlsx, sourcetype="area")
        assert AreaSource.objects.all().count() > 0
        source1 = AreaSource.objects.get(name="source1")
        assert source1.name == "source1"
        assert source1.timevar is None
        assert source1.substances.all().count() == 1

        # test if update also works
        import_sources(areasource_xlsx, sourcetype="area")
        assert AreaSource.objects.all().count() > 0

    def test_import_areasourceactivities(self, vertical_dist):
        vdist = vertical_dist  # noqa

        # create pointsources
        filepath = resources.files("edb.data") / "areasourceactivities.xlsx"
        # test if create pointsourceactivities works
        import_sourceactivities(filepath)
        assert AreaSourceActivity.objects.all().count() > 0
        # test if update also works
        import_sourceactivities(filepath)
        assert AreaSourceActivity.objects.all().count() > 0

    @pytest.mark.django_db(transaction=False)
    def test_import_gridsources(
        self, transactional_db, gridsource_xlsx, activities, code_sets
    ):
        filepath = resources.files("edb.data") / "gridsources.xlsx"
        updates, messages = import_gridsources(filepath)
        assert (
            len(messages) == 0
        ), f"errors importing gridsources: {', '.join(messages)}"
        source1 = GridSource.objects.get(name="gridsource1")
        source2 = GridSource.objects.get(name="gridsource2")
        assert source1.name == "gridsource1"
        assert source1.tags["tag1"] == "tag1_value"
        assert source1.timevar is None
        assert source1.substances.all().count() == 1
        source1_pm25 = source1.substances.get(substance__slug="PM25")
        emis_value = source1_pm25.value * emis_conversion_factor_from_si("ton/year")
        assert emis_value == pytest.approx(5378.204285, 1e-4)
        data, metadata = get_gridsource_raster(source1_pm25.raster)
        assert data.sum() == 1.0

        assert source2.substances.all().count() == 2
        source2_pm25 = source2.substances.get(substance__slug="PM25")
        source2_nox = source2.substances.get(substance__slug="NOx")
        data, metadata = get_gridsource_raster(source2_pm25.raster)
        assert data.sum() == 1.0
        data, metadata = get_gridsource_raster(source2_nox.raster)
        assert data.sum() == 1.0

        emis_value2_pm25 = source2_pm25.value * emis_conversion_factor_from_si(
            "ton/year"
        )
        emis_value2_nox = source2_nox.value * emis_conversion_factor_from_si("ton/year")
        assert emis_value2_pm25 == pytest.approx(10.0, 1e-4)
        assert emis_value2_nox == pytest.approx(20.0, 1e-4)

        # modify a source
        source1.tags["test_tag"] = "test"
        source1.save()

        # re-import gridsources from file
        # and check that existing source is updated
        import_gridsources(filepath)
        source1 = GridSource.objects.get(name="gridsource1")
        source2 = GridSource.objects.get(name="gridsource2")
        assert "test_tag" not in source1.tags
