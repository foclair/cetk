"""Tests for emission model importers."""

import pkg_resources
import pytest

from etk.edb.importers import (  # , import_timevars
    import_eea_emfacs,
    import_pointsources,
)
from etk.edb.models.source_models import PointSource  # PointSourceSubstance, Timevar
from etk.edb.models.source_models import CodeSet
from etk.edb.units import emis_conversion_factor_from_si


@pytest.fixture
def pointsource_csv(tmpdir, settings):
    return pkg_resources.resource_filename(__name__, "data/pointsources.csv")


@pytest.fixture
def pointsource_xlsx(tmpdir, settings):
    return pkg_resources.resource_filename(__name__, "data/pointsources.xlsx")


class TestImport:

    """Test importing point-sources from csv."""

    def test_import_pointsources(
        self, domains, vertical_dist, pointsource_csv, pointsource_xlsx
    ):
        domain = domains[0]
        # similar to base_set in gadget
        cs1 = CodeSet.objects.create(name="code set 1", slug="code_set1", domain=domain)
        cs1.codes.create(code="1", label="Energy")
        cs1.codes.create(
            code="1.1", label="Stationary combustion", vertical_dist=vertical_dist
        )
        cs1.codes.create(
            code="1.2", label="Fugitive emissions", vertical_dist=vertical_dist
        )
        cs1.codes.create(code="1.3", label="Road traffic", vertical_dist=vertical_dist)
        cs1.save()
        cs2 = CodeSet.objects.create(name="code set 2", slug="code_set2", domain=domain)
        cs2.codes.create(code="A", label="Bla bla")
        cs2.save()
        # create pointsources
        import_pointsources(pointsource_csv, unit="ton/year")

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
        import_pointsources(
            pointsource_xlsx,
            unit="ton/year",
        )

        # check that source has been overwritten
        source1 = PointSource.objects.get(name="source1")
        assert "test_tag" not in source1.tags

    def test_import_eea_emfac(
        self,
        domains,
    ):
        # using domain just to get fixtures
        domain = domains[0]  # noqa
        filename = pkg_resources.resource_filename(
            __name__, "data/EMEPemissionfactors-short.xlsx"
        )
        sd = import_eea_emfacs(filename)
        assert len(sd) > 0
