import datetime

import netCDF4 as nc
import numpy as np
import pytest

# from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Point, Polygon

from etk.edb.const import WGS84_SRID
from etk.edb.models.source_models import AreaSource, PointSource, Substance
from etk.edb.rasterize import EmissionRasterizer, Output
from etk.edb.units import emission_unit_to_si

# from importlib import resources
# from operator import itemgetter


# from django.db import IntegrityError


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

        rasterizer.process([subst1, subst2], begin, end, unit="ton/year")
        # rasterizer.process([subst1], begin, end, unit="ton/year")
        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert dset["time"][0] == 368160
            assert dset["Emission of NOx"].shape == (3, 4, 4)
            assert np.sum(dset["Emission of NOx"]) == pytest.approx(3000, 1e-6)
            assert dset["Emission of NOx"][0, 0, 0] == pytest.approx(1000, 1e-6)

    def test_area_source(self, testsettings, test_timevar, tmpdir):
        daytime_timevar = test_timevar

        subst1 = Substance.objects.get(slug="NOx")
        subst2 = Substance.objects.get(slug="SOx")

        extent = (0.0, 0.0, 100.0, 100.0)
        srid = 3006
        # testing with one point just within the dataset extent
        llcorner = Point(x=extent[0] + 5, y=extent[1] + 5, z=None, srid=srid)
        llcorner.transform(WGS84_SRID)
        geom = Polygon(((10, 10), (90, 10), (90, 90), (10, 90), (10, 10)), srid=srid)
        geom.transform(4326)

        src1 = AreaSource.objects.create(name="areasource1", geom=geom)

        src2 = AreaSource.objects.create(
            name="areasource2", geom=geom, timevar=daytime_timevar
        )

        # some substance emissions with varying attributes
        src1.substances.create(
            substance=subst1, value=emission_unit_to_si(1000, "ton/year")
        )

        src2.substances.create(
            substance=subst2, value=emission_unit_to_si(2000, "ton/year")
        )

        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )

        rasterizer = EmissionRasterizer(output, nx=4, ny=4)

        begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2012, 1, 1, 2, tzinfo=datetime.timezone.utc)

        rasterizer.process([subst1, subst2], begin, end, unit="g/s")
        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert dset["time"][0] == 368160
            assert dset["Emission of NOx"].shape == (3, 4, 4)
            assert np.sum(dset["Emission of NOx"][0, :, :]) == pytest.approx(
                31.6880878, 1e-6
            )
