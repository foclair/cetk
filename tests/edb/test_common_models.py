"""Unit and regression tests for edb models."""

# from collections import OrderedDict
import ast

import numpy as np
import pytest
from django.contrib.gis.geos import GEOSGeometry, Polygon

from cetk.edb.const import WGS84_SRID
from cetk.edb.models import AreaSource, source_models
from cetk.edb.models.common_models import Settings


class TestActivityCodes:
    def test_activitycode1_manager_create(self, code_sets):
        """Test creating a new activitycode with reference to a code-set."""
        code_set = code_sets[0]
        ac1 = source_models.ActivityCode.objects.create(
            code="actcode1", label="label1", code_set=code_set
        )
        ac1_ref = code_set.codes.get(code="actcode1", code_set=code_set)
        assert ac1 == ac1_ref

        ac1, created = code_set.codes.get_or_create(code="actcode1", label="label1")
        assert not created
        assert ac1 == ac1_ref

        ac2, created = code_set.codes.get_or_create(code="actcode2", label="label2")
        assert created

    def test_get_children(self, code_sets):
        code_set = code_sets[0]
        ac1 = code_set.codes.get(code="1")
        ac13 = code_set.codes.get(code="1.3")
        ac131 = code_set.codes.get(code="1.3.1")
        # breakpoint()
        assert ac13 in list(ac1.get_children())
        assert ac131 not in list(ac1.get_children())
        assert ac131 in list(ac13.get_children())

    def test_get_parent(self, code_sets):
        code_set = code_sets[0]
        ac1 = code_set.codes.get(code="1")
        ac13 = code_set.codes.get(code="1.3")
        ac131 = code_set.codes.get(code="1.3.1")
        assert ac1 == ac13.get_parent()
        assert ac13 == ac131.get_parent()
        with pytest.raises(RuntimeError):
            ac1.get_parent()


class TestVerticalDist:
    def test_create_vertical_dist(self, code_sets):
        # code_sets only used to get fixture
        code_set = code_sets[0]  # noqa
        vdist = source_models.VerticalDist.objects.create(
            name="residential heating",
            weights="[[5, 0], [10, 0.3], [15, 0.7]]",
            slug="residential_heating",
        )
        assert len(np.array(ast.literal_eval(vdist.weights))) == 3

    def test_str(self, vertical_dist):
        assert str(vertical_dist) == vertical_dist.name


class TestSettings:
    def test_settings(self, code_sets):
        codeset1 = code_sets[0]
        # Create or update the settings
        instance, created = Settings.objects.get_or_create(
            defaults={
                "srid": WGS84_SRID,
                "extent": "POLYGON ((10.95 55.33, 24.16 55.33, 24.16 69.06,"
                + " 10.95 69.06, 10.95 55.33))",
                "timezone": "Europe/Stockholm",
                "codeset1": codeset1,
            }
        )
        assert Settings.objects.get().srid == 4326

        # update settings
        settings = Settings.objects.get()
        settings.srid = 3006
        settings.save()
        assert Settings.objects.get().srid == 3006

    def test_settings_functions(self, code_sets):
        codeset2 = code_sets[1]
        # use functions defined in Settings directly
        settings = Settings.get_current()
        settings.srid = WGS84_SRID
        settings.extent = GEOSGeometry(
            "POLYGON ((10. 55., 24. 55., 24. 69., 10. 69., 10. 55.))"
        )
        settings.timezone = "Europe/Oslo"
        settings.codeset1 = codeset2
        settings.save()
        settings = Settings.get_current()
        assert settings.srid == WGS84_SRID
        assert settings.timezone == "Europe/Oslo"
        assert settings.codeset1 == codeset2


# class TestInventoryAreaSources:
#     POLYGON_WKT = (
#         "SRID=4326;POLYGON((17.8 52.0, 17.0 52.0, 17.0 51.0, 17.8 51.0, 17.8 52.0))"
#     )

#     @pytest.mark.usefixtures("areasources")
#     def test_sources(self):
#         """Test filtering and listing sources."""


#         # test filtering name using regexp
#         assert inv1.sources("area", name=".*1").count() == 1

#         # test filtering on tags
#         assert inv1.sources("area", tags={"tag2": "B"}).count() == 1

#         assert inv1.sources("area", polygon=self.POLYGON_WKT).count() == 4

#     @pytest.mark.usefixtures("areasources")
#     def test_source_emissions(self, inventories, source_ef_sets):
#         """Test to aggregate emissions from area or area sources."""

#         SOx = Substance.objects.get(slug="SOx")
#         NOx = Substance.objects.get(slug="NOx")
#         inv1 = inventories[0]
#         source_ef_set = source_ef_sets[0]
#         ac1 = {ac.code: ac for ac in inv1.base_set.code_set1.codes.all()}
#         srid = inv1.project.domain.srid

#         # test without filtering
#         emis = dictfetchall(inv1.emissions("area", source_ef_set, srid))
#         emis_SOx = sum([e["emis"] for e in emis if e["substance_id"] == SOx.pk])
#         emis_NOx = sum([e["emis"] for e in emis if e["substance_id"] == NOx.pk])
#         verif_SOx = sum_source_emissions(inv1, SOx)
#         verif_NOx = sum_source_emissions(inv1, NOx)
#         assert emis_SOx == pytest.approx(verif_SOx, 1e-6)
#         assert emis_NOx == pytest.approx(verif_NOx, 1e-6)

#         # test filtering emissions by name
#         assert (len(emissions("area", source_ef_set, name=".*1").fetchall())) == 2

#         # test filtering emissions by substance
#         assert (
#             len(inv1.emissions("area", source_ef_set, substances=SOx).fetchall())
#         ) == 2

#         # test filtering by ac1 level1
#         assert len(emissions("area", source_ef_set, ac1=ac1["1"]).fetchall()) == 2

#         # test filtering emissions by ac1 level2
#         assert (
#             len(inv1.emissions("area", source_ef_set, ac1=ac1["1.2"]).fetchall()) == 2
#         )

#         # test filtering by polygon
#         assert (
#             len(
#                 inv1.emissions(
#                     "area", source_ef_set, polygon=self.POLYGON_WKT
#                 ).fetchall()
#             )
#             == 4
#         )

#         # test filtering by tags
#         assert (
#             len(inv1.emissions("area", source_ef_set, tags={"tag1": "A"}).fetchall())
#             == 4
#         )
#         assert (
#             len(
#                 inv1.emissions(
#                     "area", source_ef_set, tags={"tag1": "A", "tag2": "!=B"}
#                 ).fetchall()
#             )
#             == 2
#         )


class TestAreaSource:
    def test_areasource_manager_create(self, code_sets):
        """
        Creating a new areasource
        """
        # not used, just to enable fixtures
        ac1 = code_sets[0]  # noqa

        src1 = AreaSource.objects.create(
            name="ps1",
            geom=Polygon(
                ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
                srid=WGS84_SRID,
            ),
        )

        sources = list(AreaSource.objects.all())
        assert src1 == sources[0]

    def test_str(self, areasources):
        src1 = areasources[0]
        assert str(src1) == src1.name
