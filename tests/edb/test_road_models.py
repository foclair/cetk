"""Unit and regression tests for the edb app's common database models."""

import datetime

import numpy as np
import pandas as pd
import pytest
from django.contrib.gis.geos import LineString
from django.db import IntegrityError

from etk.edb.models import CongestionProfile, RoadSource, Substance, Vehicle

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
    def test_congestion_profile(self, inventories):
        inv1 = inventories[0]
        constant_timevar = inv1.flow_timevars.get(name="constant")

        test_profile = np.ones((24, 7)) * 1
        test_profile[:7, :] = 2
        test_profile[23:, :] = 3

        congestion_profile = CongestionProfile.objects.create(
            name="test congestion profile",
            inventory=inv1,
            traffic_condition=test_profile.tolist(),
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
            id=123, traffic_condition=[[1] * 7, [2] * 7, [3] * 7, [4] * 7] * 6
        )
        time_index = pd.date_range(
            start, periods=24 * 7 * 2, freq="H", tz=datetime.timezone.utc
        )
        time_series = congestion.to_series(time_index, timezone=time_index.tz)
        expected_time_series = pd.Series(
            np.roll([1, 2, 3, 4] * 6 * 7 * 2, shift), index=time_index
        )
        pd.testing.assert_series_equal(time_series, expected_time_series)


class TestRoadSource:
    @pytest.fixture
    def inventory(self, ifactory):
        return ifactory.edb.inventory()

    @pytest.fixture
    def roadclass(self, ifactory):
        return ifactory.edb.roadclass()

    @pytest.fixture
    def fleet(self, ifactory, inventory):
        fleet = ifactory.edb.fleet(inventory=inventory, default_heavy_vehicle_share=0.3)
        ifactory.edb.fleetmember(
            fraction=1, vehicle=ifactory.edb.vehicle(isheavy=True), fleet=fleet
        )
        ifactory.edb.fleetmember(
            fraction=1, vehicle=ifactory.edb.vehicle(isheavy=False), fleet=fleet
        )
        return fleet

    def test_roadsource_manager_create(self, inventories, fleets, roadclasses):
        """
        Test creating a new roadsource with references to an inventory.
        """
        inv1 = inventories[0]
        freeflow = inv1.congestion_profiles.get(name="free-flow")
        src1 = RoadSource.objects.create(
            name="roadsource1",
            inventory=inv1,
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
    def test_create(self, inventory, roadclass, attrs):
        try:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                roadclass=roadclass,
                inventory=inventory,
                **attrs,
            )
        except IntegrityError as exc:
            pytest.fail(f"Unexpected IntegrityError when creating road source: {exc}")

    def test_negative_aadt(self, inventory, roadclass):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                aadt=-1,
                roadclass=roadclass,
                inventory=inventory,
            )
        assert "aadt" in str(excinfo.value)

    @pytest.mark.parametrize("nolanes", [-1, 0])
    def test_invalid_nolanes(self, inventory, roadclass, nolanes):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                nolanes=nolanes,
                roadclass=roadclass,
                inventory=inventory,
            )
        assert "nolanes" in str(excinfo.value)

    @pytest.mark.parametrize("width", [-1, 0, 0.0])
    def test_invalid_width(self, inventory, roadclass, width):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                width=width,
                roadclass=roadclass,
                inventory=inventory,
            )
        assert "width" in str(excinfo.value)

    @pytest.mark.parametrize("median_strip_width", [-1, -0.1, 20])
    def test_invalid_median_strip_width(self, inventory, roadclass, median_strip_width):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                width=20,
                median_strip_width=median_strip_width,
                roadclass=roadclass,
                inventory=inventory,
            )
        assert "median_strip_width" in str(excinfo.value)

    @pytest.mark.parametrize("heavy_vehicle_share", [-0.1, 1.1])
    def test_invalid_heavy_vehicle_share(
        self, inventory, roadclass, heavy_vehicle_share
    ):
        with pytest.raises(IntegrityError) as excinfo:
            RoadSource.objects.create(
                geom="LINESTRING (0 0, 1 1)",
                width=20,
                heavy_vehicle_share=heavy_vehicle_share,
                roadclass=roadclass,
                inventory=inventory,
            )
        assert "heavy_vehicle_share" in str(excinfo.value)

    @pytest.mark.parametrize(
        "median_strip_width,expected_drivable_width", [(0, 20), (10, 10), (20, 0)]
    )
    def test_drivable_width(self, median_strip_width, expected_drivable_width):
        road = RoadSource(width=20, median_strip_width=median_strip_width)
        assert road.drivable_width == expected_drivable_width

    def test_get_heavy_vehicle_share(self, fleet):
        road = RoadSource(fleet=fleet, heavy_vehicle_share=0.6)
        assert road.get_heavy_vehicle_share() == 0.6

    def test_get_heavy_vehicle_share_from_fleet(self, fleet):
        road = RoadSource(fleet=fleet)
        assert road.get_heavy_vehicle_share() == fleet.default_heavy_vehicle_share

    @pytest.mark.parametrize(
        "rel_dist,target_x,target_y,target_bearing",
        [
            (0.0000, 0.0, 0.0, 45),
            (0.1250, 0.5, 0.5, 45),
            (0.2499, 1.0, 1.0, 45),
            (0.2501, 1.0, 1.0, 135),
            (0.3750, 1.5, 0.5, 135),
            (0.4999, 2.0, 0.0, 135),
            pytest.param(0.5001, 2.0, 0.0, 225, marks=pytest.mark.xfail),
            pytest.param(0.6250, 1.5, -0.5, 225, marks=pytest.mark.xfail),
            pytest.param(0.7499, 1.0, -1.0, 225, marks=pytest.mark.xfail),
            pytest.param(0.7501, 1.0, -1.0, 315, marks=pytest.mark.xfail),
            pytest.param(0.8750, 0.5, -0.5, 315, marks=pytest.mark.xfail),
            pytest.param(1.0000, 0.0, -0.0, 315, marks=pytest.mark.xfail),
        ],
    )
    def test_get_segments(self, ifactory, rel_dist, target_x, target_y, target_bearing):
        geom = LineString((0, 0), (1, 1), (2, 0), (1, -1), (0, 0), srid=3006)
        road = ifactory.edb.roadsource(geom=geom.transform(4326, clone=True))
        ((point, bearing),) = road.get_segments([rel_dist])
        assert point.transform(3006, clone=True).coords == (
            pytest.approx(target_x, rel=1e-3, abs=1e-3),
            pytest.approx(target_y, rel=1e-3, abs=1e-3),
        )
        assert bearing == pytest.approx(target_bearing)

        geom = LineString((0, 0), (1, 1), (1, 1), (1, -1), srid=3006)
        road = ifactory.edb.roadsource(geom=geom.transform(4326, clone=True))
        ((point, bearing),) = road.get_segments([rel_dist])

    def test_str(self, roadsources):
        """Test string representation."""
        src1 = roadsources[0]
        assert str(src1) == src1.name


class TestInventoryRoadSources:
    @pytest.mark.usefixtures("roadsources")
    def test_sources(self, inventories):
        """Test filtering and listing sources."""
        inv1 = inventories[0]

        ids = [source.pk for source in inv1.sources("road").all()]
        assert inv1.sources("road", ids=ids[:-1]).count() == len(ids) - 1

        # test filtering name using regexp
        assert inv1.sources("road", name=".*1").count() == 1

        # test filtering on tags
        assert inv1.sources("road", tags={"tag2": "B"}).count() == 1

        assert inv1.sources("road", polygon=POLYGON_WKT).count() == 2

    @pytest.mark.usefixtures("fleets", "roadclasses")
    def test_road_emissions(self, inventories, road_ef_sets, vehicles, roadsources):
        """Test to calculate road emissions and to filter by ac."""

        subst1 = Substance.objects.get(slug="NOx")
        subst2 = Substance.objects.get(slug="SOx")

        road_ef_set1, road_ef_set2 = road_ef_sets[:2]

        inv1 = inventories[0]
        srid = inv1.project.domain.srid
        ac1 = {ac.code: ac for ac in inv1.base_set.code_set1.codes.all()}
        road1, road2, road3 = roadsources[:3]

        # test filtering emissions by name and substance 1
        # calculate emissions in db
        emission_recs = dictfetchall(
            inv1.emissions("road", road_ef_set1, srid, name=".*1", substances=subst1)
        )

        # calculate emissions outside of db
        ref_emis_by_veh_and_subst = road1.emission(road_ef_set1, substance=subst1)

        # sort calculated emissions into a nested dict
        emis_by_veh_and_subst = {}
        for em in emission_recs:
            em_subst = Substance.objects.get(pk=em["substance_id"])
            em_veh = Vehicle.objects.get(pk=em["vehicle_id"])
            if em_veh not in emis_by_veh_and_subst:
                emis_by_veh_and_subst[em_veh] = {}
            veh_subst = emis_by_veh_and_subst[em_veh]
            veh_subst[em_subst] = em

            assert emis_by_veh_and_subst[em_veh][em_subst]["emis"] == pytest.approx(
                ref_emis_by_veh_and_subst[em_veh][em_subst], 1e-6
            )

        # test filtering emissions by name, substance 1 and activitycode1
        # calculate emission in db
        emis_ac_3_2 = dictfetchall(
            inv1.emissions(
                "road",
                road_ef_set1,
                srid,
                name=".*1",
                substances=subst2,
                ac1=ac1["1.3.2"],
            )
        )[0]

        # calculate emission outside db
        ref_emis_subst2_ac_3_2 = road1.emission(
            road_ef_set1, substance=subst2, ac1=[ac1["1.3.2"]]
        )
        veh = vehicles[1]
        assert emis_ac_3_2["emis"] == pytest.approx(
            ref_emis_subst2_ac_3_2[veh][subst2], 1e-6
        )

    @pytest.mark.usefixtures("vehicles", "fleets", "roadclasses")
    def test_road_missions_filter_by_name(self, inventories, road_ef_sets, roadsources):
        """Test to filter road emissions by name"""

        inv1 = inventories[0]
        road_ef_set1 = road_ef_sets[0]
        srid = inv1.project.domain.srid
        subst1 = Substance.objects.get(slug="NOx")
        road3 = roadsources[2]

        # test filtering emissions by name and substance 1
        # calculate emissions in db
        emission_recs = dictfetchall(
            inv1.emissions("road", road_ef_set1, srid, name=".*3", substances=subst1)
        )

        # calculate emissions outside of db
        ref_emis_by_veh_and_subst = road3.emission(road_ef_set1, substance=subst1)
        # sort calculated emissions into a nested dict
        emis_by_veh_and_subst = {}
        for em in emission_recs:
            em_subst = Substance.objects.get(pk=em["substance_id"])
            em_veh = Vehicle.objects.get(pk=em["vehicle_id"])
            if em_veh not in emis_by_veh_and_subst:
                emis_by_veh_and_subst[em_veh] = {}
            veh_subst = emis_by_veh_and_subst[em_veh]
            veh_subst[em_subst] = em

            assert emis_by_veh_and_subst[em_veh][em_subst]["emis"] == pytest.approx(
                ref_emis_by_veh_and_subst[em_veh][em_subst], 1e-6
            )

    @pytest.mark.usefixtures("vehicles", "fleets", "roadclasses", "roadsources")
    def test_road_emissions_filter_by_polygon(self, inventories, road_ef_sets):
        """Test to calculate road emissions and to filter by polygon."""

        inv1 = inventories[0]
        road_ef_set1 = road_ef_sets[0]
        srid = inv1.project.domain.srid
        subst1 = Substance.objects.get(slug="NOx")

        # test filtering emissions outside polygon
        # calculate emissions in db
        emission_recs = dictfetchall(
            inv1.emissions(
                "road",
                road_ef_set1,
                srid,
                name=".*3",
                substances=subst1,
                polygon=POLYGON_WKT,
            )
        )
        assert len(emission_recs) == 0

        # test filtering emissions inside polygon
        # calculate emissions in db
        emission_recs = dictfetchall(
            inv1.emissions(
                "road",
                road_ef_set1,
                srid,
                name=".*2",
                substances=subst1,
                polygon=POLYGON_WKT,
            )
        )
        assert len(emission_recs) == 2

    @pytest.mark.usefixtures("vehicles", "fleets", "roadclasses")
    def test_road_emissions_filter_by_ids(self, inventories, road_ef_sets, roadsources):
        """Test to calculate road emissions and to filter by polygon."""

        inv1 = inventories[0]
        road_ef_set1 = road_ef_sets[0]
        srid = inv1.project.domain.srid
        road1 = roadsources[0]
        road3 = roadsources[2]

        # test filter by list of id's
        ids = (road1.pk, road3.pk)
        emission_recs = dictfetchall(
            inv1.emissions("road", road_ef_set1, srid, ids=ids)
        )
        result_ids = [
            rec["source_id"] for rec in emission_recs if rec["source_id"] in ids
        ]
        assert len(np.unique(np.array(result_ids))) == 2

    @pytest.mark.usefixtures("vehicles", "fleets", "roadclasses")
    def test_road_emissions_filter_by_tags(
        self, inventories, road_ef_sets, roadsources
    ):
        """Test to calculate road emissions and to filter by tags."""

        inv1 = inventories[0]
        road_ef_set1 = road_ef_sets[0]
        srid = inv1.project.domain.srid
        subst1 = Substance.objects.get(slug="NOx")
        road1, road2, road3 = roadsources[:3]

        # test filtering by tags
        # plain equal
        emission_recs = dictfetchall(
            inv1.emissions(
                "road", road_ef_set1, srid, tags={"test1": "tag 1"}, substances=subst1
            )
        )
        assert {road3.pk} == {rec["source_id"] for rec in emission_recs}

        # tags equal with explicit operator
        emission_recs = dictfetchall(
            inv1.emissions(
                "road", road_ef_set1, srid, tags={"test1": "=tag 1"}, substances=subst1
            )
        )
        assert {road3.pk} == {rec["source_id"] for rec in emission_recs}

        # tags not equal
        emission_recs = dictfetchall(
            inv1.emissions("road", road_ef_set1, srid, tags={"test1": "!=tag 1"})
        )
        assert {road1.pk, road2.pk} == {rec["source_id"] for rec in emission_recs}
