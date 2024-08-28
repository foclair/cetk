import datetime

import netCDF4 as nc
import numpy as np
import pytest

# from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import LineString, Point, Polygon

from cetk.edb.const import WGS84_SRID
from cetk.edb.models import AreaSource, PointSource, RoadSource, Substance
from cetk.edb.rasterize import EmissionRasterizer, Output
from cetk.edb.units import emission_unit_to_si

# from importlib import resources
# from operator import itemgetter


# from django.db import IntegrityError


class TestEmissionRasterizer:

    """Unit tests for the Rasterizer class."""

    # def test_point_source(  # noqa: PLR0915
    #     self, testsettings, code_sets, test_timevar, tmpdir
    # ):
    #     ac_1_1 = code_sets[0].codes.get(code="1.1")
    #     # settings.NARC_DATA_ROOT = tmpdir.mkdir("store").strpath

    #     daytime_timevar = test_timevar

    #     subst1 = Substance.objects.get(slug="NOx")
    #     subst2 = Substance.objects.get(slug="SOx")

    #     extent = (0.0, 0.0, 100.0, 100.0)
    #     srid = 3006

    #     # testing with a single point source within the dataset extent
    #     llcorner = Point(x=extent[0] + 5, y=extent[1] + 5, z=None, srid=srid)
    #     llcorner.transform(WGS84_SRID)

    #     src1 = PointSource.objects.create(
    #         name="pointsource1",
    #         geom=Point(x=llcorner.coords[0], y=llcorner.coords[1], srid=WGS84_SRID),
    #         chimney_height=10.0,
    #         activitycode1=ac_1_1,
    #     )

    #     src2 = PointSource.objects.create(
    #         name="pointsource2",
    #         geom=Point(x=llcorner.coords[0], y=llcorner.coords[1], srid=WGS84_SRID),
    #         chimney_height=10.0,
    #         activitycode1=ac_1_1,
    #         timevar=daytime_timevar,
    #     )

    #     # some substance emissions with varying attributes
    #     src1.substances.create(
    #         substance=subst1, value=emission_unit_to_si(1000, "ton/year")
    #     )

    #     src2.substances.create(
    #         substance=subst2, value=emission_unit_to_si(2000, "ton/year")
    #     )

    #     begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
    #     end = datetime.datetime(2012, 1, 1, 2, tzinfo=datetime.timezone.utc)
    #     # timestamps = [begin, end]

    #     output = Output(
    #         extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
    #     )

    #     rasterizer = EmissionRasterizer(output, nx=4, ny=4)
    #     rasterizer.process([subst1, subst2], begin, end, unit="ton/year")

    #     with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
    #         assert dset["time"][0] == 368160
    #         assert dset["Emission of NOx"].shape == (3, 4, 4)
    #         assert np.sum(dset["Emission of NOx"]) == pytest.approx(3000, 1e-6)
    #         assert dset["Emission of NOx"][0, 0, 0] == pytest.approx(1000, 1e-6)

    def test_empty_raster_point_outside_time(  # noqa: PLR0915
        self, testsettings, code_sets, tmpdir
    ):
        ac_1_1 = code_sets[0].codes.get(code="1.1")
        subst1 = Substance.objects.get(slug="NOx")
        extent = (0.0, 0.0, 100.0, 100.0)
        srid = 3006

        # testing with a single point source outside the dataset extent
        llcorner = Point(x=extent[2] + 5, y=extent[3] + 5, z=None, srid=srid)
        llcorner.transform(WGS84_SRID)
        src1 = PointSource.objects.create(
            name="pointsource1",
            geom=Point(x=llcorner.coords[0], y=llcorner.coords[1], srid=WGS84_SRID),
            chimney_height=10.0,
            activitycode1=ac_1_1,
        )
        # some substance emissions with varying attributes
        src1.substances.create(
            substance=subst1, value=emission_unit_to_si(1000, "ton/year")
        )

        begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2012, 1, 1, 2, tzinfo=datetime.timezone.utc)
        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )

        rasterizer = EmissionRasterizer(output, nx=4, ny=4)
        rasterizer.process([subst1], begin, end, unit="ton/year")

        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert dset["time"][0] == 368160
            assert dset["emission_NOx"].shape == (3, 4, 4)
            assert np.sum(dset["emission_NOx"]) == pytest.approx(0, 1e-6)
            assert dset["emission_NOx"][0, 0, 0] == pytest.approx(0, 1e-6)

    def test_empty_raster_point_outside_avg(  # noqa: PLR0915
        self, testsettings, code_sets, tmpdir
    ):
        ac_1_1 = code_sets[0].codes.get(code="1.1")
        subst1 = Substance.objects.get(slug="NOx")
        extent = (0.0, 0.0, 100.0, 100.0)
        srid = 3006

        # testing with a single point source outside the dataset extent
        llcorner = Point(x=extent[2] + 5, y=extent[3] + 5, z=None, srid=srid)
        llcorner.transform(WGS84_SRID)
        src1 = PointSource.objects.create(
            name="pointsource1",
            geom=Point(x=llcorner.coords[0], y=llcorner.coords[1], srid=WGS84_SRID),
            chimney_height=10.0,
            activitycode1=ac_1_1,
        )
        # some substance emissions with varying attributes
        src1.substances.create(
            substance=subst1, value=emission_unit_to_si(1000, "ton/year")
        )

        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )

        rasterizer = EmissionRasterizer(output, nx=4, ny=4)
        rasterizer.process([subst1], unit="ton/year")

        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert dset["emission_NOx"].shape == (4, 4)
            assert np.sum(dset["emission_NOx"]) == pytest.approx(0, 1e-6)
            assert dset["emission_NOx"][0, 0] == pytest.approx(0, 1e-6)

    def test_area_source(self, testsettings, test_timevar, tmpdir):
        daytime_timevar = test_timevar

        subst1 = Substance.objects.get(slug="NOx")
        subst2 = Substance.objects.get(slug="SOx")

        extent = (0.0, 0.0, 100.0, 100.0)
        srid = 3006

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
            assert dset["emission_NOx"].shape == (3, 4, 4)
            assert np.sum(dset["emission_NOx"][0, :, :]) == pytest.approx(
                31.6880878, 1e-6
            )

    def test_empty_raster_area_outside(self, testsettings, test_timevar, tmpdir):
        daytime_timevar = test_timevar

        subst1 = Substance.objects.get(slug="NOx")
        subst2 = Substance.objects.get(slug="SOx")

        extent = (0.0, 0.0, 40.0, 40.0)
        srid = 3006

        geom = Polygon(((50, 50), (90, 50), (90, 90), (50, 90), (50, 50)), srid=srid)
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
            assert dset["emission_NOx"].shape == (3, 4, 4)
            assert np.sum(dset["emission_NOx"][0, :, :]) == pytest.approx(0, 1e-6)

    def test_area_and_point_source(self, testsettings, code_sets, test_timevar, tmpdir):
        # test where each substance has both area and pointsource
        daytime_timevar = test_timevar

        ac_1_1 = code_sets[0].codes.get(code="1.1")

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

        geom = Polygon(((10, 10), (90, 10), (90, 90), (10, 90), (10, 10)), srid=srid)
        geom.transform(4326)

        src3 = AreaSource.objects.create(name="areasource1", geom=geom)

        src4 = AreaSource.objects.create(
            name="areasource2", geom=geom, timevar=daytime_timevar
        )

        # some substance emissions with varying attributes
        src3.substances.create(
            substance=subst1, value=emission_unit_to_si(1000, "ton/year")
        )

        src4.substances.create(
            substance=subst2, value=emission_unit_to_si(2000, "ton/year")
        )

        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )

        rasterizer = EmissionRasterizer(output, nx=4, ny=4)
        begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2012, 1, 1, 2, tzinfo=datetime.timezone.utc)
        rasterizer.process([subst1, subst2], begin, end, unit="ton/year")

        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert dset["time"][0] == 368160
            assert dset["emission_NOx"].shape == (3, 4, 4)
            assert np.sum(dset["emission_NOx"][0, :, :]) == pytest.approx(2000, 1e-6)

    def test_area_or_point_source(self, testsettings, code_sets, test_timevar, tmpdir):
        # test where each substance has either point or areasource
        daytime_timevar = test_timevar

        ac_1_1 = code_sets[0].codes.get(code="1.1")

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
        src1.substances.create(
            substance=subst1, value=emission_unit_to_si(1000, "ton/year")
        )

        geom = Polygon(((10, 10), (90, 10), (90, 90), (10, 90), (10, 10)), srid=srid)
        geom.transform(4326)
        # areasource with timevar
        src2 = AreaSource.objects.create(
            name="areasource1", geom=geom, timevar=daytime_timevar
        )
        src2.substances.create(
            substance=subst2, value=emission_unit_to_si(2000, "ton/year")
        )

        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )

        rasterizer = EmissionRasterizer(output, nx=4, ny=4)

        begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2012, 1, 1, 12, tzinfo=datetime.timezone.utc)

        rasterizer.process([subst1, subst2], begin, end, unit="ton/year")
        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert dset["time"][0] == 368160
            assert dset["emission_NOx"].shape == (13, 4, 4)
            assert np.sum(dset["emission_NOx"]) == pytest.approx(13000, 1e-6)
            assert dset["emission_NOx"][0, 0, 0] == pytest.approx(1000, 1e-6)
        with nc.Dataset(tmpdir + "/SOx.nc", "r", format="NETCDF4") as dset:
            assert dset["time"][0] == 368160
            assert dset["emission_SOx"].shape == (13, 4, 4)
            assert np.sum(dset["emission_SOx"][0, :, :]) == pytest.approx(0, 1e-6)
            # normalize to 2000 with 16 / 24 nonzero hours
            assert np.sum(dset["emission_SOx"][12, :, :]) == pytest.approx(3000, 1e-6)

    def test_point_source_no_timesteps(  # noqa: PLR0915
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

        # timestamps = [begin, end]

        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )

        rasterizer = EmissionRasterizer(output, nx=4, ny=4)
        rasterizer.process([subst1, subst2], unit="ton/year")

        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert dset["emission_NOx"].shape == (4, 4)
            assert np.sum(dset["emission_NOx"]) == pytest.approx(1000, 1e-6)
            assert dset["emission_NOx"][0, 0] == pytest.approx(1000, 1e-6)

    def test_gridsource_no_timesteps(testsettings, gridsources, tmpdir):
        NOx = Substance.objects.get(slug="NOx")
        SOx = Substance.objects.get(slug="SOx")
        extent = (0.0, 0.0, 1200.0, 1200.0)
        srid = 3006
        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )
        rasterizer = EmissionRasterizer(output, nx=4, ny=4)
        rasterizer.process([NOx, SOx], unit="ton/year")
        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert dset["emission_NOx"].shape == (4, 4)
            assert np.sum(dset["emission_NOx"]) == pytest.approx(510.0, 1e-6)

    def test_gridsource(testsettings, gridsources, tmpdir):

        NOx = Substance.objects.get(slug="NOx")
        SOx = Substance.objects.get(slug="SOx")
        extent = (0.0, 0.0, 1200.0, 1200.0)
        srid = 3006
        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )
        rasterizer = EmissionRasterizer(output, nx=4, ny=4)
        begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2012, 1, 1, 2, tzinfo=datetime.timezone.utc)
        rasterizer.process([NOx, SOx], begin, end, unit="ton/year")
        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert dset["time"][0] == 368160
            assert dset["emission_NOx"].shape == (3, 4, 4)
            assert np.sum(dset["emission_NOx"][0, :, :]) == pytest.approx(510.0, 1e-6)

    # ac-filtering not implemented yet!
    # def test_point_source_filter(  # noqa: PLR0915
    #     self, testsettings, code_sets, test_timevar, tmpdir
    # ):
    #     ac_1_1 = code_sets[0].codes.get(code="1.1")
    #     ac_1_2 = code_sets[0].codes.get(code="1.2")
    #     # settings.NARC_DATA_ROOT = tmpdir.mkdir("store").strpath

    #     daytime_timevar = test_timevar

    #     subst1 = Substance.objects.get(slug="NOx")
    #     subst2 = Substance.objects.get(slug="SOx")

    #     extent = (0.0, 0.0, 100.0, 100.0)
    #     srid = 3006

    #     # testing with a single point source within the dataset extent
    #     llcorner = Point(x=extent[0] + 5, y=extent[1] + 5, z=None, srid=srid)
    #     llcorner.transform(WGS84_SRID)

    #     src1 = PointSource.objects.create(
    #         name="pointsource1",
    #         geom=Point(x=llcorner.coords[0], y=llcorner.coords[1], srid=WGS84_SRID),
    #         chimney_height=10.0,
    #         activitycode1=ac_1_1,
    #     )

    #     src2 = PointSource.objects.create(
    #         name="pointsource2",
    #         geom=Point(x=llcorner.coords[0], y=llcorner.coords[1], srid=WGS84_SRID),
    #         chimney_height=10.0,
    #         activitycode1=ac_1_2,
    #     )

    #     # some substance emissions with varying attributes
    #     src1.substances.create(
    #         substance=subst1, value=emission_unit_to_si(1000, "ton/year")
    #     )

    #     src2.substances.create(
    #         substance=subst2, value=emission_unit_to_si(2000, "ton/year")
    #     )

    #     begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
    #     end = datetime.datetime(2012, 1, 1, 2, tzinfo=datetime.timezone.utc)
    #     # timestamps = [begin, end]

    #     output = Output(
    #         extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
    #     )

    #     rasterizer = EmissionRasterizer(output, nx=4, ny=4)
    #     rasterizer.process([subst1, subst2], begin, end, unit="ton/year", ac1=["1.1"])

    #     with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
    #         assert dset["time"][0] == 368160
    #         assert dset["Emission of NOx"].shape == (3, 4, 4)
    #         assert np.sum(dset["Emission of NOx"]) == pytest.approx(3000, 1e-6)
    #         assert dset["Emission of NOx"][0, 0, 0] == pytest.approx(1000, 1e-6)

    #     with nc.Dataset(tmpdir + "/SOx.nc", "r", format="NETCDF4") as dset:
    #         assert np.sum(dset["Emission of SOx"]) == pytest.approx(0, 1e-6)
    #         # should be 0 since ac 1.2

    def test_road_source(self, testsettings, tmpdir, roadclasses, fleets):
        NOx = Substance.objects.get(slug="NOx")
        SOx = Substance.objects.get(slug="SOx")

        extent = (0.0, 0.0, 100.0, 100.0)
        srid = 3006
        output = Output(
            extent=extent, timezone=datetime.timezone.utc, path=tmpdir, srid=srid
        )

        # testing with one road segment just within the dataset extent
        llcorner = Point(x=extent[0] + 1, y=extent[1] + 1, z=None, srid=3006)
        llcorner.transform(WGS84_SRID)

        urcorner = Point(x=extent[2] - 1, y=extent[3] - 1, z=None, srid=3006)
        urcorner.transform(WGS84_SRID)

        road1 = RoadSource.objects.create(
            name="road1",
            geom=LineString(llcorner.coords, urcorner.coords, srid=WGS84_SRID),
            tags={"tag2": "B"},
            aadt=1000,
            speed=80,
            width=20,
            roadclass=roadclasses[0],
            fleet=fleets[0],
        )

        rasterizer = EmissionRasterizer(output, nx=4, ny=4)
        # testing to rasterize average emission intensity
        rasterizer.process(NOx)
        # need to find a way to compute the sum of all emissions in inventory!
        emissions = RoadSource.objects.first().emission(substance=NOx.id)
        emissions_sum = sum([list(value.values())[0] for value in emissions.values()])
        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert np.sum(dset["emission_NOx"]) == pytest.approx(emissions_sum, 1e-4)

        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert np.sum(dset["emission_NOx"]) == pytest.approx(1.6361665e-07, 1e-4)

        # testing to rasterize all hours in time interval
        begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2012, 1, 1, 2, tzinfo=datetime.timezone.utc)
        rasterizer.process(NOx, begin, end, unit="g/s")

        with nc.Dataset(tmpdir + "/NOx.nc", "r", format="NETCDF4") as dset:
            assert len(dset.variables["time"]) == 3
            data1 = dset.variables["emission_NOx"][:]
            assert data1.sum() > 0

        avg_emis2 = sum(
            [next(iter(v.values())) for v in road1.emission(substance=SOx).values()]
        )
        # avg_emis2 in gadget 1.6361665242450532e-07
        begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2012, 12, 31, 23, tzinfo=datetime.timezone.utc)

        rasterizer.process(SOx, begin, end)
        with nc.Dataset(tmpdir + "/SOx.nc", "r", format="NETCDF4") as dset:
            data2 = dset.variables["emission_SOx"][:]
            gridded_avg_emis = data2.sum() / data2.shape[0]

        # summing large number of grid cells may cause some truncation
        # we need to have a higher error tolerance (1e-2)
        # rasterize returns emissions in kg/s by default
        assert avg_emis2 == pytest.approx(gridded_avg_emis, 1e-2)
