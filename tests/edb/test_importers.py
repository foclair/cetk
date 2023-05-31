"""Tests for emission model importers."""

from contextlib import ExitStack
from importlib import resources

import pkg_resources
import pytest

# from pytest import approx
from ruamel.yaml import YAML

from etk.edb import models
from etk.edb.importers import import_pointsources  # , import_timevars
from etk.edb.models import PointSource  # PointSourceSubstance, Timevar
from etk.edb.units import emis_conversion_factor_from_si


@pytest.fixture
def get_data_file():
    with ExitStack() as file_manager:

        def _get_data_file(filename):
            filepath = resources.as_file(resources.files("edb.data") / filename)
            return str(file_manager.enter_context(filepath))

        yield _get_data_file


def get_yaml_data(filename):
    yaml = YAML(typ="safe")
    with resources.files("edb.data").joinpath(filename).open("rb") as fp:
        return yaml.load(fp)


# def test_import_timevars(ifactory, get_data_file):
#     timevarfile = get_data_file("timevars.yaml")
#     import_timevars(get_yaml_data(timevarfile))
#     assert Timevar.objects.all().count() == 1

#     # test overwriting
#     import_timevars(get_yaml_data(timevarfile), overwrite=True)
#     assert Timevar.objects.all().count() == 1


# class TestImportPointSources:
#     def test_import_pointsources_substance_rows(
#         self, domains, vertical_dist, get_data_file
#     ):
#         # translations ="pointsource_substance_parameter_translation.yaml")
#         # timevar_data = get_yaml_data(get_data_file("timevar_pointsources.yaml"))
#         # timevars = import_timevars(timevar_data)
#         domain = domains[0]
#         cs1 = models.CodeSet.objects.create(
#             name="codeset1", slug="codeset1", domain=domain
#         )
#         cs1.codes.create(code="1", label="Energy")
#         cs1.codes.create(
#             code="1.1", label="Stationary combustion", vertical_dist=vertical_dist
#         )
#         cs1.codes.create(
#             code="1.2", label="Fugitive emissions", vertical_dist=vertical_dist
#         )

#         pscount = PointSource.objects.all().count()
#         import_pointsources(
#             get_data_file("pointsource_substance_rows.csv"),
#         )
#         assert PointSource.objects.all().count() == pscount + 6
#         ps = PointSource.objects.get(
#             name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
#         )
#         assert ps.chimney_outer_diameter == approx(2.5)
#         assert ps.chimney_inner_diameter == approx(1.0)
#         assert ps.chimney_height == approx(10.0)  # default
#         assert ps.chimney_gas_temperature == approx(100.0)  # default
#         assert ps.substances.get(substance__name="NOx").value == approx(0.0025)
#         assert ps.substances.get(substance__name="SOx").value == approx(0.0012)
#         assert ps.timevar.name == "industry0"  # mapping default

#         ps2 = PointSource.objects.get(name="10621_12Verwarmingsinstallatie")
#         assert ps2.chimney_height == approx(25.0)
#         assert ps2.timevar.name == "industry0"  # mapping default
#         assert ps2.substances.get(substance__name="NOx").value == approx(0.000001268)
#         assert ps2.facility.name == "10621"

#         ps3 = PointSource.objects.get(name="10621_6Gloeiovens")
#         assert ps3.timevar.name == "industry1"
#         assert ps2.facility == ps3.facility


@pytest.fixture
def pointsource_csv(tmpdir, settings):
    return pkg_resources.resource_filename(__name__, "data/pointsources.csv")


class TestImportPointSources:

    """Test importing point-sources from csv."""

    def test_import_pointsources(self, domains, vertical_dist, pointsource_csv):
        domain = domains[0]
        # similar to base_set in gadget
        cs1 = models.CodeSet.objects.create(
            name="code set 1", slug="code_set1", domain=domain
        )
        cs1.codes.create(code="1", label="Energy")
        cs1.codes.create(
            code="1.1", label="Stationary combustion", vertical_dist=vertical_dist
        )
        cs1.codes.create(
            code="1.2", label="Fugitive emissions", vertical_dist=vertical_dist
        )
        cs1.codes.create(code="1.3", label="Road traffic", vertical_dist=vertical_dist)
        cs1.save()
        cs2 = models.CodeSet.objects.create(
            name="code set 2", slug="code_set2", domain=domain
        )
        cs2.codes.create(code="A", label="Bla bla")
        cs2.save()
        # create pointsources
        import_pointsources(pointsource_csv, unit="ton/year")

        assert PointSource.objects.all().count()
        source1 = PointSource.objects.filter(name="source1").first()

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

        # update pointsources
        import_pointsources(
            pointsource_csv,
            unit="ton/year",
        )

        # check that source has been overwritten
        source1 = PointSource.objects.filter(name="source1").first()
        assert "test_tag" not in source1.tags
