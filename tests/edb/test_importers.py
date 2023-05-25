"""Tests for emission model importers."""

from contextlib import ExitStack
from importlib import resources

import pytest
from pytest import approx
from ruamel.yaml import YAML

from etk.edb import models
from etk.edb.importers import import_pointsources, import_timevars
from etk.edb.models import PointSource, PointSourceSubstance, Timevar


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


class TestImportPointSources:
    def test_import_pointsources_substance_rows(
        self, domains, vertical_dist, get_data_file
    ):
        # translations ="pointsource_substance_parameter_translation.yaml")
        # timevar_data = get_yaml_data(get_data_file("timevar_pointsources.yaml"))
        # timevars = import_timevars(timevar_data)
        domain = domains[0]
        cs1 = models.CodeSet.objects.create(
            name="codeset1", slug="codeset1", domain=domain
        )
        cs1.codes.create(code="1", label="Energy")
        cs1.codes.create(
            code="1.1", label="Stationary combustion", vertical_dist=vertical_dist
        )
        cs1.codes.create(
            code="1.2", label="Fugitive emissions", vertical_dist=vertical_dist
        )

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_rows.csv"),
        )
        assert PointSource.objects.all().count() == pscount + 6
        ps = PointSource.objects.get(
            name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
        )
        assert ps.chimney_outer_diameter == approx(2.5)
        assert ps.chimney_inner_diameter == approx(1.0)
        assert ps.chimney_height == approx(10.0)  # default
        assert ps.chimney_gas_temperature == approx(100.0)  # default
        assert ps.substances.get(substance__name="NOx").value == approx(0.0025)
        assert ps.substances.get(substance__name="SOx").value == approx(0.0012)
        assert ps.timevar.name == "industry0"  # mapping default

        ps2 = PointSource.objects.get(name="10621_12Verwarmingsinstallatie")
        assert ps2.chimney_height == approx(25.0)
        assert ps2.timevar.name == "industry0"  # mapping default
        assert ps2.substances.get(substance__name="NOx").value == approx(0.000001268)
        assert ps2.facility.name == "10621"

        ps3 = PointSource.objects.get(name="10621_6Gloeiovens")
        assert ps3.timevar.name == "industry1"
        assert ps2.facility == ps3.facility

    # NB: had to be added because not using inventories fixture
    def test_import_pointsources_timevars(self, domains, vertical_dist, get_data_file):
        domain = domains[0]
        notimevars = Timevar.objects.all().count()
        cs1 = models.CodeSet.objects.create(
            name="codeset1", slug="codeset1", domain=domain
        )
        cs1.codes.create(code="1", label="Energy")
        cs1.codes.create(
            code="1.1", label="Stationary combustion", vertical_dist=vertical_dist
        )
        cs1.codes.create(
            code="1.2", label="Fugitive emissions", vertical_dist=vertical_dist
        )
        # translations = get_yaml_data("test_point_source_translation_timevars.yaml")
        timevar_data = get_yaml_data(get_data_file("test_timevar_pointsources.yaml"))
        timevars = import_timevars(timevar_data)
        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("eldstader_backe.gpkg"),
        )
        assert PointSource.objects.all().count() == pscount + 174
        assert Timevar.objects.all().count() == notimevars + 4
        assert PointSourceSubstance.objects.all().count() == 174

        # 10 "BBR godknd vedpanna" + 54 "vedpanna"
        assert (
            PointSource.objects.filter(timevar=timevars["emission"]["vedpanna"]).count()
            == 10 + 54
        )
        # 1 "udda typ eldstad" not defined gets default
        assert (
            PointSource.objects.filter(timevar=timevars["emission"]["STANDARD"]).count()
            == 1
        )

    @pytest.fixture()
    def test_import_pointsources(self, get_data_file):
        timevars = import_timevars(
            get_yaml_data(get_data_file("test_timevar_pointsources.yaml")),
        )

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("eldstader_backe.gpkg"),
            get_yaml_data("test_point_source_translation.yaml"),
            timevars,
        )
        assert PointSourceSubstance.objects.all().count() == 174
        assert (
            PointSource.objects.filter(timevar=timevars["emission"]["vedpanna"]).count()
            == pscount + 174
        )

    @pytest.fixture()
    def test_import_pointsources_substance_attributes(self, get_data_file):
        translations = get_yaml_data(
            "pointsource_substance_attributes_translation.yaml"
        )
        timevars = import_timevars(
            get_yaml_data(get_data_file("timevar_pointsources.yaml"))
        )

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_attributes.gpkg"),
            translations,
            timevars,
        )
        assert PointSource.objects.all().count() == pscount + 6
        ps = PointSource.objects.get(
            name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
        )
        assert ps.chimney_outer_diameter == approx(2.5)
        assert ps.chimney_inner_diameter == approx(1.0)
        assert ps.chimney_height == approx(10.0)  # default
        assert ps.chimney_gas_temperature == approx(100.0)  # default
        assert ps.substances.get(substance__name="NOx").value == approx(0.0025)
        assert ps.substances.get(substance__name="SOx").value == approx(0.0012)
        assert ps.timevar.name == "industry0"  # mapping default
        assert ps.geom.coords == approx((4.5419448, 51.9085558))

        ps2 = PointSource.objects.get(name="10621_12Verwarmingsinstallatie")
        assert ps2.chimney_height == approx(25.0)
        assert ps2.timevar.name == "industry0"  # mapping default
        assert ps2.substances.get(substance__name="NOx").value == approx(0.000001268)
        assert ps2.facility.name == "10621"

        ps3 = PointSource.objects.get(name="10621_6Gloeiovens")
        assert ps3.timevar.name == "industry1"
        assert ps2.facility == ps3.facility

    @pytest.fixture()
    def test_import_pointsources_substance_attributes_filter(self, get_data_file):
        translations = get_yaml_data(
            "pointsource_substance_attributes_translation.yaml"
        )
        timevar_data = get_yaml_data(get_data_file("timevar_pointsources.yaml"))
        timevars = import_timevars(timevar_data)

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_attributes.gpkg"),
            translations,
            timevars,
            exclude={"facility": "10621"},
        )
        assert PointSource.objects.all().count() == pscount + 1
        PointSource.objects.get(name="AWZIKralingseveer(HoogheemraadschapvanSchieland)")

    @pytest.fixture()
    def test_import_pointsources_substance_attributes_only(self, get_data_file):
        translations = get_yaml_data(
            "pointsource_substance_attributes_translation.yaml"
        )
        timevar_data = get_yaml_data(get_data_file("timevar_pointsources.yaml"))
        timevars = import_timevars(timevar_data)

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_attributes.gpkg"),
            translations,
            timevars,
            only={"facility": "10621"},
        )
        assert PointSource.objects.all().count() == pscount + 5
        with pytest.raises(PointSource.DoesNotExist):
            PointSource.objects.get(
                name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
            )

    @pytest.fixture()
    def test_import_pointsources_substance_parameter(self, get_data_file):
        translations = get_yaml_data("pointsource_substance_parameter_translation.yaml")
        timevar_data = get_yaml_data(get_data_file("timevar_pointsources.yaml"))
        timevars = import_timevars(timevar_data)

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_parameter.gpkg"),
            translations,
            timevars,
        )
        assert PointSource.objects.all().count() == pscount + 6
        ps = PointSource.objects.get(
            name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
        )
        assert ps.chimney_outer_diameter == approx(2.5)
        assert ps.chimney_inner_diameter == approx(1.0)
        assert ps.chimney_height == approx(10.0)  # default
        assert ps.chimney_gas_temperature == approx(100.0)  # default
        assert ps.substances.get(substance__name="NOx").value == approx(0.0025)
        assert ps.substances.get(substance__name="SOx").value == approx(0.0012)
        assert ps.timevar.name == "industry0"  # mapping default

        ps2 = PointSource.objects.get(name="10621_12Verwarmingsinstallatie")
        assert ps2.chimney_height == approx(25.0)
        assert ps2.timevar.name == "industry0"  # mapping default
        assert ps2.substances.get(substance__name="NOx").value == approx(0.000001268)
        assert ps2.facility.name == "10621"

        ps3 = PointSource.objects.get(name="10621_6Gloeiovens")
        assert ps3.timevar.name == "industry1"
        assert ps2.facility == ps3.facility

    @pytest.fixture()
    def test_import_pointsources_substance_mappedsubst(self, get_data_file):
        translations = get_yaml_data(
            "pointsource_substance_mappedsubst_translation.yaml"
        )

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_mappedsubst.csv"),
            translations,
        )
        assert PointSource.objects.all().count() == pscount + 6
        ps = PointSource.objects.get(
            name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
        )
        assert ps.substances.get(substance__name="NOx").value == approx(0.0025)
        assert ps.substances.get(substance__name="SOx").value == approx(0.0012)

        ps2 = PointSource.objects.get(name="10621_12Verwarmingsinstallatie")
        assert ps2.substances.get(substance__name="NOx").value == approx(0.000001268)

    @pytest.fixture()
    def test_import_pointsources_substance_rows_no_timevars(self, get_data_file):
        translations = get_yaml_data("pointsource_substance_parameter_translation.yaml")

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_rows.csv"),
            translations,
        )
        assert PointSource.objects.all().count() == pscount + 6
        ps = PointSource.objects.get(
            name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
        )
        assert ps.timevar is None

    @pytest.fixture()
    def test_import_pointsources_substance_rows_filter(self, get_data_file):
        config = get_yaml_data("pointsource_substance_parameter_translation.yaml")

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_rows.csv"),
            config=config,
            exclude={"facility": "10621"},
        )
        assert PointSource.objects.all().count() == pscount + 1
        ps = PointSource.objects.get(
            name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
        )
        assert ps.timevar is None

    @pytest.fixture()
    def test_import_pointsources_substance_rows_only(self, get_data_file):
        config = get_yaml_data("pointsource_substance_parameter_translation.yaml")

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_rows.csv"),
            config=config,
            only={"facility": "10621"},
        )
        assert PointSource.objects.all().count() == pscount + 5
        with pytest.raises(PointSource.DoesNotExist):
            PointSource.objects.get(
                name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
            )

    @pytest.fixture()
    def test_import_pointsources_mappedunits(self, get_data_file):
        config = get_yaml_data("pointsource_substance_mappedunit.yaml")

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_mappedunit.csv"),
            config,
        )
        assert PointSource.objects.all().count() == pscount + 6
        ps = PointSource.objects.get(
            name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
        )
        assert ps.chimney_outer_diameter == approx(2.5)
        assert ps.chimney_inner_diameter == approx(1.0)
        assert ps.chimney_height == approx(10.0)  # default
        assert ps.chimney_gas_temperature == approx(100.0)  # default
        assert ps.substances.get(substance__name="NOx").value == approx(0.0025)
        assert ps.substances.get(substance__name="SOx").value == approx(0.0012)

        ps2 = PointSource.objects.get(name="10621_12Verwarmingsinstallatie")
        assert ps2.chimney_height == approx(25.0)
        assert ps2.substances.get(substance__name="NOx").value == approx(0.001268)
        assert ps2.facility.name == "10621"

        ps3 = PointSource.objects.get(name="10621_6Gloeiovens")
        assert ps2.facility == ps3.facility

    @pytest.fixture()
    def test_import_pointsources_substance_colums(self, get_data_file):
        config = get_yaml_data("pointsource_substance_attributes_translation.yaml")
        timevar_data = get_yaml_data(get_data_file("timevar_pointsources.yaml"))
        timevars = import_timevars(timevar_data)

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_substance_columns.csv"),
            config,
            timevars,
        )
        assert PointSource.objects.all().count() == pscount + 6
        ps = PointSource.objects.get(
            name="AWZIKralingseveer(HoogheemraadschapvanSchieland)"
        )
        assert ps.chimney_outer_diameter == approx(2.5)
        assert ps.chimney_inner_diameter == approx(1.0)
        assert ps.chimney_height == approx(10.0)  # default
        assert ps.chimney_gas_temperature == approx(100.0)  # default
        assert ps.substances.get(substance__name="NOx").value == approx(0.0025)
        assert ps.substances.get(substance__name="SOx").value == approx(0.0012)
        assert ps.timevar.name == "industry0"  # mapping default
        assert ps.geom.coords == approx((4.5419448, 51.9085558))

        ps2 = PointSource.objects.get(name="10621_12Verwarmingsinstallatie")
        assert ps2.chimney_height == approx(25.0)
        assert ps2.timevar.name == "industry0"  # mapping default
        assert ps2.substances.get(substance__name="NOx").value == approx(0.000001268)
        assert ps2.facility.name == "10621"

        ps3 = PointSource.objects.get(name="10621_6Gloeiovens")
        assert ps3.timevar.name == "industry1"
        assert ps2.facility == ps3.facility

    def test_import_pointsources_codes(self, code_sets, get_data_file):
        config = get_yaml_data("pointsource_codes.yaml")

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_codes.csv"),
            config,
            codeset=code_sets[0],
        )
        assert PointSource.objects.all().count() == pscount + 3
        ps = PointSource.objects.get(name="Asfaltsverket")
        assert ps.activitycode1.code == "2.2"

    def test_import_pointsources_codemap(self, code_sets, get_data_file):
        config = get_yaml_data("pointsource_codemap.yaml")

        pscount = PointSource.objects.all().count()
        import_pointsources(
            get_data_file("pointsource_codes.csv"),
            config,
            codeset=code_sets[1],
        )
        assert PointSource.objects.all().count() == pscount + 3
        ps = PointSource.objects.get(name="Asfaltsverket")
        assert ps.activitycode1.code == "A"
