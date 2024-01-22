"""Tests for emission model importers."""

from importlib import resources

import numpy as np
import pytest

from etk.edb.importers import (  # , import_timevars
    import_eea_emfacs,
    import_sourceactivities,
    import_sources,
)
from etk.edb.models.eea_emfacs import EEAEmissionFactor
from etk.edb.models.source_models import (
    AreaSource,
    AreaSourceActivity,
    CodeSet,
    PointSource,
    PointSourceActivity,
)
from etk.edb.units import emis_conversion_factor_from_si


@pytest.fixture
def pointsource_csv(tmpdir, settings):
    return resources.files("edb.data") / "pointsources.csv"


@pytest.fixture
def pointsource_xlsx(tmpdir, settings):
    return resources.files("edb.data") / "pointsources.xlsx"


@pytest.fixture
def areasource_xlsx(tmpdir, settings):
    return resources.files("edb.data") / "areasources.xlsx"


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
        import_sources(pointsource_csv, type="point")

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
        import_sources(pointsource_xlsx, type="point")

        # check that source has been overwritten
        source1 = PointSource.objects.get(name="source1")
        assert "test_tag" not in source1.tags

    def test_import_eea_emfac(self, vertical_dist):
        # using vertical_dist just to get fixtures
        vdist = vertical_dist  # noqa
        filename = resources.files("edb.data") / "EMEPemissionfactors-short.xlsx"
        sd = import_eea_emfacs(filename)
        assert len(sd) > 0

    def test_import_pointsourceactivities(
        self, vertical_dist, pointsource_csv, pointsource_xlsx
    ):
        # similar to base_set in gadget
        cs1 = CodeSet.objects.create(name="code set 1", slug="code_set1")
        filename = resources.files("edb.data") / "EMEPemissionfactors-short.xlsx"

        # example code how to use eea emfacs for codeset
        import_eea_emfacs(filename)
        emfacs = EEAEmissionFactor.objects.all()
        nfr_codes = [ef.nfr_code for ef in emfacs]
        unique_nfr_codes = set(nfr_codes)
        sectors = [ef.sector for ef in emfacs]
        for code in unique_nfr_codes:
            index = np.argmax(np.asarray(nfr_codes) == code)
            cs1.codes.create(code=code, label=sectors[index])

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
        psa = import_sourceactivities(filepath)
        print(psa)
        assert PointSourceActivity.objects.all().count()
        # test if update also works
        psa = import_sourceactivities(filepath)
        print(psa)
        assert PointSourceActivity.objects.all().count()

    def test_import_areasources(self, vertical_dist, areasource_xlsx):

        # similar to base_set in gadget
        cs1 = CodeSet.objects.create(name="SNAP", slug="SNAP")
        cs1.codes.create(code="1.3", label="Energy", vertical_dist=vertical_dist)
        cs1.save()
        # create areasources
        import_sources(areasource_xlsx, type="area")
        assert AreaSource.objects.all().count()
        source1 = AreaSource.objects.get(name="source1")
        assert source1.name == "source1"
        assert source1.timevar is None
        assert source1.substances.all().count() == 1

        # test if update also works
        import_sources(areasource_xlsx, type="area")
        assert AreaSource.objects.all().count()

    def test_import_areasourceactivities(self, vertical_dist):
        vdist = vertical_dist  # noqa

        # create pointsources
        filepath = resources.files("edb.data") / "areasourceactivities.xlsx"
        # test if create pointsourceactivities works
        psa = import_sourceactivities(filepath)
        print(psa)

        assert AreaSourceActivity.objects.all().count()
        # test if update also works
        psa = import_sourceactivities(filepath)
        print(psa)
        assert AreaSourceActivity.objects.all().count()


# TODO test_import_residentialheating
