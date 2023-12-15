import datetime

# from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Point

from etk.edb.models.source_models import (  # AreaSource,; CodeSet,; Parameter,
    PointSource,
    Substance,
)
from etk.edb.rasterize import EmissionRasterizer, Output
from etk.edb.units import emission_unit_to_si

# import numpy as np
# import pytest


# from importlib import resources
# from operator import itemgetter


# from django.db import IntegrityError


WGS84_SRID = 4326
DUMMY_SRID = 3857


class TestEmissionRasterizer:

    """Unit tests for the Rasterizer class."""

    # TODO do not understand where tmpdir comes from
    def test_point_source(  # noqa: PLR0915
        self, testsettings, code_sets, test_timevar, tmpdir
    ):
        ac_1_1 = code_sets[0].codes.get(code="1.1")
        # settings.NARC_DATA_ROOT = tmpdir.mkdir("store").strpath

        daytime_timevar = test_timevar

        subst1 = Substance.objects.get(slug="NOx")
        subst2 = Substance.objects.get(slug="SOx")

        extent = (0.0, 0.0, 100.0, 100.0)
        srid = 3006

        # testing with a single point source within the dataset extent
        llcorner = Point(x=extent[0] + 5, y=extent[1] + 5, z=None, srid=srid)
        llcorner.transform(WGS84_SRID)

        src1 = PointSource.objects.create(
            name="pointsource1",
            geom=Point(x=llcorner.coords[0], y=llcorner.coords[1], srid=WGS84_SRID),
            chimney_height=10.0,
            activitycode1=ac_1_1,
        )

        src2 = PointSource.objects.create(
            name="pointsource2",
            geom=Point(x=llcorner.coords[0], y=llcorner.coords[1], srid=WGS84_SRID),
            chimney_height=10.0,
            activitycode1=ac_1_1,
            timevar=daytime_timevar,
        )

        # some substance emissions with varying attributes
        src1.substances.create(
            substance=subst1, value=emission_unit_to_si(1000, "ton/year")
        )

        src2.substances.create(
            substance=subst2, value=emission_unit_to_si(2000, "ton/year")
        )

        begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2012, 1, 1, 2, tzinfo=datetime.timezone.utc)
        # timestamps = [begin, end]

        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )

        rasterizer = EmissionRasterizer(output, nx=4, ny=4)

        # rasterizer.process([subst1, subst2], begin, end, unit="ton/year")
        rasterizer.process([subst1], begin, end, unit="ton/year")

        # assert dataset.fields2d.filter(parameter__substance=subst1).exists()
        # var = dataset.fields2d.get(parameter__substance=subst1)
        # with var.open("r"):
        #     data1 = var.get_data([begin])
        #     # TODO: should we use timezone-aware datetimes or not?
        #     assert var.get_time_variable().size == 3
        # assert data1.sum() == pytest.approx(1000, 1e-6)
        # var = dataset.fields2d.get(parameter__substance=subst3)
        # with var.open("r"):
        #     tempvar_series = var.get_timeseries(4, 4)
        # assert tempvar_series.emission_PM10_field2d_1H[-1] == 0
