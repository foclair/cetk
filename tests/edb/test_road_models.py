"""Unit and regression tests for the edb app's common database models."""

import datetime

import numpy as np
import pandas as pd
import pytest
from django.contrib.gis.geos import LineString
from django.db import IntegrityError

from cetk.edb.models import CongestionProfile, RoadSource, Substance, Vehicle

SWEREF99_TM_SRID = 3006
WGS84_SRID = 4326
POLYGON_WKT = (
    "SRID=4326;POLYGON((17.0 53.0, 17.0 52.0, 18.0 52.0, 18.0 53.0, 17.0 53.0))"
)


def dictfetchall(cursor):
    """Returns all rows from a cursor as dicts."""
    return [
        dict(zip([col[0] for col in cursor.description], row))
        for row in cursor.fetchall()
    ]


class TestCongestionProfile:
    def test_congestion_profile(self, test_flowtimevar_constant):
        constant_timevar = test_flowtimevar_constant

        test_profile = np.ones((24, 7)) * 1
        test_profile[:7, :] = 2
        test_profile[23:, :] = 3

        congestion_profile = CongestionProfile.objects.create(
            name="test congestion profile",
            traffic_condition=str(test_profile.tolist()),
        )

        conditions = congestion_profile.get_fractions(constant_timevar)
        assert conditions["freeflow"] == pytest.approx((16 * 7) / (24 * 7), 1e-6)
        assert conditions["heavy"] == pytest.approx(49 / (24 * 7), 1e-6)
        assert conditions["saturated"] == pytest.approx(7 / (24 * 7), 1e-6)
        assert conditions["stopngo"] == 0

    @pytest.mark.parametrize(
        "start,shift",
        # 2020-06-01 is a Monday
        [("2020-05-31 23:00", 1), ("2020-06-01 00:00", 0), ("2020-06-01 01:00", -1)],
    )
    def test_to_series(self, start, shift):
        congestion = CongestionProfile(
            id=123, traffic_condition=str([[1] * 7, [2] * 7, [3] * 7, [4] * 7] * 6)
        )
        time_index = pd.date_range(
            start, periods=24 * 7 * 2, freq="h", tz=datetime.timezone.utc
        )
        time_series = congestion.to_series(time_index, timezone=time_index.tz)
        expected_time_series = pd.Series(
            np.roll([1, 2, 3, 4] * 6 * 7 * 2, shift), index=time_index
        )
        pd.testing.assert_series_equal(time_series, expected_time_series)


class TestRoadSource:
    # @pytest.fixture
    # def roadclass(self, ifactory):
    #     return ifactory.edb.roadclass()

    def test_roadsource_manager_create(self, fleets, roadclasses):
        """
        Test creating a new roadsource with references to an inventory.
        """
        test_profile = np.ones((24, 7)) * 1
        test_profile[:7, :] = 2
        test_profile[23:, :] = 2
        CongestionProfile.objects.create(
            name="free-flow", traffic_condition=str(test_profile.tolist())
        )
        freeflow = CongestionProfile.objects.get(name="free-flow")
        src1 = RoadSource.objects.create(
            name="roadsource1",
            geom=LineString((1.0, 1.0), (2.0, 2.0), srid=WGS84_SRID),
            fleet=fleets[0],
            roadclass=roadclasses[0],
            congestion_profile=freeflow,
        )
        sources = list(RoadSource.objects.all())
        assert src1 == sources[0]

    @pytest.mark.parametrize(
        "attrs",
        [
            {"aadt": 0},
            {"nolanes": 1},
            {"width": 0.1},
            {"median_strip_width": 0},
            {"width": 21, "median_strip_width": 20.9},
            {"heavy_vehicle_share": 0},
            {"heavy_vehicle_share": 1},
        ],
    )
    def test_create(self, roadclasses, attrs):
        try:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                roadclass=roadclasses[0],
                **attrs,
            )
        except IntegrityError as exc:
            pytest.fail(f"Unexpected IntegrityError when creating road source: {exc}")

    def test_negative_aadt(self, roadclasses):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                aadt=-1,
                roadclass=roadclasses[0],
            )
        assert "aadt" in str(excinfo.value)

    @pytest.mark.parametrize("nolanes", [-1, 0])
    def test_invalid_nolanes(self, roadclasses, nolanes):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                nolanes=nolanes,
                roadclass=roadclasses[0],
            )
        assert "nolanes" in str(excinfo.value)

    @pytest.mark.parametrize("width", [-1, 0, 0.0])
    def test_invalid_width(self, roadclasses, width):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                width=width,
                roadclass=roadclasses[0],
            )
        assert "width" in str(excinfo.value)

    @pytest.mark.parametrize("median_strip_width", [-1, -0.1, 20])
    def test_invalid_median_strip_width(self, roadclasses, median_strip_width):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                width=20,
                median_strip_width=median_strip_width,
                roadclass=roadclasses[0],
            )
        assert "median_strip_width" in str(excinfo.value)

    @pytest.mark.parametrize("heavy_vehicle_share", [-0.1, 1.1])
    def test_invalid_heavy_vehicle_share(self, roadclasses, heavy_vehicle_share):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                width=20,
                heavy_vehicle_share=heavy_vehicle_share,
                roadclass=roadclasses[0],
            )
        assert "heavy_vehicle_share" in str(excinfo.value)

    @pytest.mark.parametrize(
        "median_strip_width,expected_drivable_width", [(0, 20), (10, 10), (20, 0)]
    )
    def test_drivable_width(self, median_strip_width, expected_drivable_width):
        road = RoadSource(width=20, median_strip_width=median_strip_width)
        assert road.drivable_width == expected_drivable_width

    def test_get_heavy_vehicle_share(self, fleets):
        road = RoadSource(fleet=fleets[0], heavy_vehicle_share=0.6)
        assert road.get_heavy_vehicle_share() == 0.6

    def test_get_heavy_vehicle_share_from_fleet(self, fleets):
        road = RoadSource(fleet=fleets[0])
        assert road.get_heavy_vehicle_share() == fleets[0].default_heavy_vehicle_share

    @pytest.mark.parametrize(
        "rel_dist,target_x,target_y,target_bearing",
        [
            pytest.param(0.0000, 0.0, 0.0, 45, marks=pytest.mark.xfail),
            pytest.param(0.1250, 0.5, 0.5, 45, marks=pytest.mark.xfail),
            pytest.param(0.2499, 1.0, 1.0, 45, marks=pytest.mark.xfail),
            pytest.param(0.2501, 1.0, 1.0, 135, marks=pytest.mark.xfail),
            pytest.param(0.3750, 1.5, 0.5, 135, marks=pytest.mark.xfail),
            pytest.param(0.4999, 2.0, 0.0, 135, marks=pytest.mark.xfail),
            pytest.param(0.5001, 2.0, 0.0, 225, marks=pytest.mark.xfail),
            pytest.param(0.6250, 1.5, -0.5, 225, marks=pytest.mark.xfail),
            pytest.param(0.7499, 1.0, -1.0, 225, marks=pytest.mark.xfail),
            pytest.param(0.7501, 1.0, -1.0, 315, marks=pytest.mark.xfail),
            pytest.param(0.8750, 0.5, -0.5, 315, marks=pytest.mark.xfail),
            pytest.param(1.0000, 0.0, -0.0, 315, marks=pytest.mark.xfail),
        ],
    )
    def test_get_segments(
        self, roadsources, rel_dist, target_x, target_y, target_bearing
    ):
        geom = LineString((0, 0), (1, 1), (2, 0), (1, -1), (0, 0), srid=3006)
        road = roadsources[0]
        road.geom = geom.transform(4326, clone=True)
        ((point, bearing),) = road.get_segments([rel_dist])
        assert point.transform(3006, clone=True).coords == (
            pytest.approx(target_x, rel=1e-3, abs=1e-3),
            pytest.approx(target_y, rel=1e-3, abs=1e-3),
        )
        assert bearing == pytest.approx(target_bearing)

        geom = LineString((0, 0), (1, 1), (1, 1), (1, -1), srid=3006)
        road.geom = geom.transform(4326, clone=True)
        ((point, bearing),) = road.get_segments([rel_dist])

    def test_str(self, roadsources):
        """Test string representation."""
        src1 = roadsources[0]
        assert str(src1) == src1.name


class TestRoadSources:
    @pytest.mark.usefixtures("fleets", "roadclasses")
    def test_road_emissions(self, vehicles, roadsources, code_sets):
        """Test to calculate road emissions and to filter by ac."""

        subst1 = Substance.objects.get(slug="NOx")

        road1, road2, road3 = roadsources[:3]

        ref_emis_by_veh_and_subst = road1.emission(substance=subst1)
        assert ref_emis_by_veh_and_subst[Vehicle.objects.get(name="car")][subst1] > 0
