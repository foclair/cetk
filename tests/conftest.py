"""Global pytest configuration."""

import os
import sys

import numpy as np
import pytest
from django.contrib.gis.geos import GEOSGeometry, LineString

if sys.argv[0] != "pytest" and "--help" not in sys.argv:
    from cetk.edb import models

# from django.contrib.auth import get_user_model
import rasterio as rio

# from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Point, Polygon

from cetk.edb.const import WGS84_SRID
from cetk.edb.models import (
    CongestionProfile,
    Fleet,
    RoadAttribute,
    RoadClass,
    Substance,
    TrafficSituation,
    VehicleFuel,
    VehicleFuelComb,
    write_gridsource_raster,
)
from cetk.edb.units import (
    activity_ef_unit_to_si,
    activity_rate_unit_to_si,
    emission_unit_to_si,
    vehicle_ef_unit_to_si,
)
from cetk.utils import GTiffProfile

EXTENT = GEOSGeometry(
    "POLYGON ((10.95 55.33, 24.16 55.33, 24.16 69.06, 10.95 69.06, 10.95 55.33))",
    srid=WGS84_SRID,
)
ROADTYPES = ["highway", "primary", "secondary", "tertiary", "residential", "busway"]
SPEEDS = ["20", "30", "40", "50", "60", "70", "80", "90", "100", "110", "120", "130"]


@pytest.fixture
def testsettings(code_sets):
    settings = models.Settings.get_current()
    codeset1, codeset2 = code_sets
    settings.srid = 3006
    settings.extent = EXTENT
    settings.timezone = "Europe/Stockholm"
    settings.codeset1 = codeset1
    settings.codeset2 = codeset2
    settings.save()
    return settings


@pytest.fixture()
def activities(db):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    act1 = models.Activity.objects.create(name="activity1", unit="m3")
    act1.emissionfactors.create(
        substance=NOx, factor=activity_ef_unit_to_si(10.0, "kg/m3")
    )
    act1.emissionfactors.create(
        substance=SOx, factor=activity_ef_unit_to_si(1.0, "kg/m3")
    )
    act2 = models.Activity.objects.create(name="activity2", unit="ton")
    act2.emissionfactors.create(
        substance=NOx, factor=activity_ef_unit_to_si(10.0, "g/ton")
    )
    act2.emissionfactors.create(
        substance=SOx, factor=activity_ef_unit_to_si(1.0, "g/ton")
    )
    return (act1, act2)


@pytest.fixture()
def vertical_dist(db):
    vdist = models.VerticalDist.objects.create(
        name="vdist1", weights="[[5.0, 0.4], [10.0, 0.6]]"
    )
    return vdist


@pytest.fixture()
def test_timevar(db):
    # array representing daytime activity
    daytime_profile = np.ones((24, 7)) * 100
    daytime_profile[:7, :] = 0
    daytime_profile[23:, :] = 0
    test_timevar = models.Timevar.objects.create(
        name="daytime", typeday=str(daytime_profile.tolist())
    )
    return test_timevar


@pytest.fixture()
def code_sets(vertical_dist):
    cs1 = models.CodeSet.objects.create(name="codeset1", slug="codeset1")
    cs1.codes.create(code="1", label="Energy")
    cs1.codes.create(
        code="1.1", label="Stationary combustion", vertical_dist=vertical_dist
    )
    cs1.codes.create(
        code="1.2", label="Fugitive emissions", vertical_dist=vertical_dist
    )
    cs1.codes.create(code="1.3", label="Road traffic")
    cs1.codes.create(code="1.3.1", label="Light vehicles")
    cs1.codes.create(code="1.3.2", label="Heavy vehicles")
    cs1.codes.create(code="2", label="Industrial processes")
    cs1.codes.create(code="2.1", label="Mobile combustion")
    cs1.codes.create(code="2.2", label="Other")
    cs1.codes.create(code="3", label="Diffuse sources")
    cs2 = models.CodeSet.objects.create(name="codeset2", slug="codeset2")
    cs2.codes.create(code="A", label="Bla bla")
    return (cs1, cs2)


@pytest.fixture()
def test_flowtimevar(db):
    # array representing daytime activity
    daytime_profile = np.ones((24, 7)) * 100
    daytime_profile[:7, :] = 0
    daytime_profile[23:, :] = 0
    test_flowtimevar = models.FlowTimevar.objects.create(
        name="daytime", typeday=str(daytime_profile.tolist())
    )
    return test_flowtimevar


@pytest.fixture()
def test_flowtimevar_constant(db):
    # array representing daytime activity
    constant_profile = np.ones((24, 7)) * 100
    test_flowtimevar = models.FlowTimevar.objects.create(
        name="constant", typeday=str(constant_profile.tolist())
    )
    return test_flowtimevar


@pytest.fixture()
def test_coldstarttimevar(db):
    # array representing constant timevar
    daytime_profile = np.ones((24, 7)) * 100
    test_timevar = models.ColdstartTimevar.objects.create(
        name="daytime", typeday=str(daytime_profile.tolist())
    )
    return test_timevar


@pytest.fixture()
def vehicle_fuels(db):
    petrol = VehicleFuel.objects.create(name="petrol")
    diesel = VehicleFuel.objects.create(name="diesel")
    return (petrol, diesel)


@pytest.fixture()
def vehicles(db):
    car = models.Vehicle.objects.create(name="car", isheavy=False)
    truck = models.Vehicle.objects.create(name="truck", isheavy=True)
    return (car, truck)


@pytest.fixture()
def vehicle_ef(vehicles, vehicle_fuels):
    substances = list(Substance.objects.filter(slug__in={"NOx", "SOx"}))
    # add emission factors for vehicles in different traffic situations
    efs = []
    for roadtype in ROADTYPES:
        for speed in SPEEDS:
            ts = models.TrafficSituation.objects.create(ts_id=f"{roadtype}_{speed}")
            for subst in substances:
                for veh in vehicles:
                    for fuel in vehicle_fuels:
                        efs.append(
                            models.VehicleEF(
                                traffic_situation=ts,
                                substance=subst,
                                vehicle=veh,
                                fuel=fuel,
                                freeflow=vehicle_ef_unit_to_si(100.0, "mg", "km"),
                                heavy=vehicle_ef_unit_to_si(200.0, "mg", "km"),
                                saturated=vehicle_ef_unit_to_si(300.0, "mg", "km"),
                                stopngo=vehicle_ef_unit_to_si(400.0, "mg", "km"),
                                coldstart=vehicle_ef_unit_to_si(10.0, "mg", "km"),
                            )
                        )
    models.VehicleEF.objects.bulk_create(efs)
    efs = models.VehicleEF.objects.all()
    return efs


@pytest.fixture
def roadclasses(vehicles, vehicle_fuels, vehicle_ef):
    rca_roadtype = models.RoadAttribute.objects.create(
        name="road type", slug="roadtype", order=1
    )
    rca_speed = models.RoadAttribute.objects.create(name="speed", slug="speed", order=2)

    def create_road_class(roadtype, speed):
        return rc

    roadclasses = []
    for roadtype in ROADTYPES:
        for speed in SPEEDS:
            # if adding vehicle_ef as argument, ts already created
            ts = models.TrafficSituation.objects.get(ts_id=f"{roadtype}_{speed}")
            # ts = models.TrafficSituation.objects.create(ts_id=f"{roadtype}_{speed}")
            rc = models.RoadClass.objects.create(traffic_situation=ts)

            rc.attribute_values.add(
                models.RoadAttributeValue.objects.get_or_create(
                    attribute=rca_roadtype, value=roadtype
                )[0]
            )
            rc.attribute_values.add(
                models.RoadAttributeValue.objects.get_or_create(
                    attribute=rca_speed, value=speed
                )[0]
            )
            rc.save()
            roadclasses.append(rc)
    return roadclasses


@pytest.fixture()
def fleets(
    vehicles,
    code_sets,
    test_flowtimevar_constant,
    test_flowtimevar,
    test_coldstarttimevar,
    vehicle_fuels,
):
    """Create templates for fleet composition."""

    car, truck = vehicles[:2]

    ac1 = dict([(ac.code, ac) for ac in code_sets[0].codes.all()])
    constant_flow = test_flowtimevar_constant
    coldstart_timevar = test_coldstarttimevar
    daytime_flow = test_flowtimevar

    (petrol, diesel) = vehicle_fuels

    VehicleFuelComb.objects.create(fuel=petrol, vehicle=car, activitycode1=ac1["1.3.1"])
    VehicleFuelComb.objects.create(fuel=diesel, vehicle=car, activitycode1=ac1["1.3.1"])
    VehicleFuelComb.objects.create(
        fuel=diesel, vehicle=truck, activitycode1=ac1["1.3.2"]
    )
    VehicleFuelComb.objects.create(
        fuel=petrol, vehicle=truck, activitycode1=ac1["1.3.2"]
    )

    Fleet.objects.create(name="fleet1", default_heavy_vehicle_share=0.5)
    fleet1 = Fleet.objects.get(name="fleet1")
    fleet_member1 = fleet1.vehicles.create(
        vehicle=car,
        timevar=constant_flow,
        fraction=1.0,
        coldstart_timevar=coldstart_timevar,
        coldstart_fraction=0.2,
    )
    fleet_member1.fuels.create(fuel=diesel, fraction=0.2)
    fleet_member1.fuels.create(fuel=petrol, fraction=0.8)

    fleet_member2 = fleet1.vehicles.create(
        vehicle=truck,
        timevar=daytime_flow,
        fraction=1.0,
        coldstart_timevar=coldstart_timevar,
        coldstart_fraction=0.2,
    )
    fleet_member2.fuels.create(fuel=diesel, fraction=0.2)
    fleet_member2.fuels.create(fuel=petrol, fraction=0.8)

    Fleet.objects.create(name="fleet2", default_heavy_vehicle_share=0.9)
    fleet2 = Fleet.objects.get(name="fleet2")
    fleet_member3 = fleet2.vehicles.create(
        vehicle=car,
        timevar=constant_flow,
        fraction=1.0,
        coldstart_timevar=coldstart_timevar,
        coldstart_fraction=0.2,
    )
    fleet_member3.fuels.create(fuel=diesel, fraction=1.0)
    fleet_member4 = fleet2.vehicles.create(
        vehicle=truck,
        timevar=daytime_flow,
        fraction=1.0,
        coldstart_timevar=coldstart_timevar,
        coldstart_fraction=0.2,
    )
    fleet_member4.fuels.create(fuel=diesel, fraction=1.0)
    return [fleet1, fleet2]


@pytest.fixture()
def roadsources(roadclasses, fleets):
    """Create road sources."""
    fleet1, fleet2 = fleets[:2]
    # array representing heavy level of service
    test_profile = np.ones((24, 7)) * 1
    test_profile[:7, :] = 2
    test_profile[23:, :] = 2
    models.CongestionProfile.objects.create(
        name="free-flow", traffic_condition=str(test_profile.tolist())
    )
    models.CongestionProfile.objects.create(
        name="heavy", traffic_condition=str(test_profile.tolist())
    )
    freeflow = models.CongestionProfile.objects.get(name="free-flow")
    heavy = models.CongestionProfile.objects.get(name="heavy")
    road1 = models.RoadSource.objects.create(
        name="road1",
        geom=LineString((17.1, 52.5), (17.15, 52.5), (17.152, 52.6), srid=WGS84_SRID),
        tags={"tag2": "B"},
        aadt=1000,
        speed=80,
        width=20,
        roadclass=roadclasses[0],
        fleet=fleet1,
        congestion_profile=freeflow,
    )

    road2 = models.RoadSource.objects.create(
        name="road2",
        geom=LineString((17.1, 52.5), (17.15, 52.5), (17.152, 52.6), srid=WGS84_SRID),
        aadt=2000,
        speed=70,
        width=15,
        roadclass=roadclasses[0],
        fleet=fleet2,
        congestion_profile=heavy,
    )

    road3 = models.RoadSource.objects.create(
        name="road3",
        geom=LineString((16.1, 52.5), (16.15, 52.5), (16.152, 52.6), srid=WGS84_SRID),
        aadt=2000,
        speed=70,
        width=15,
        roadclass=roadclasses[0],
        fleet=fleet2,
        heavy_vehicle_share=0.5,
        congestion_profile=heavy,
        tags={"test1": "tag 1"},
    )

    return [road1, road2, road3]


@pytest.fixture
def roadefset(db):
    RoadAttribute.objects.create(name="Road type", slug="roadtype", order=1)
    RoadAttribute.objects.create(name="Posted speed", slug="speed", order=2)
    attr1 = RoadAttribute.objects.get(name="Road type")
    attr2 = RoadAttribute.objects.get(name="Posted speed")

    roadclass_attr1_vals = ["0", "1", "2", "3", "4", "5", "6"]
    roadclass_attr2_vals = [
        "0",
        "5",
        "10",
        "20",
        "30",
        "40",
        "50",
        "60",
        "70",
        "80",
        "90",
        "100",
        "110",
        "120",
    ]
    for val in roadclass_attr1_vals:
        attr1.values.create(value=val)

    for val in roadclass_attr2_vals:
        attr2.values.create(value=val)

    TrafficSituation.objects.create(ts_id="default")
    traffic_situation = TrafficSituation.objects.get(ts_id="default")

    for v1 in roadclass_attr1_vals:
        for v2 in roadclass_attr2_vals:
            RoadClass.objects.create_from_attributes(
                {"roadtype": v1, "speed": v2}, traffic_situation=traffic_situation
            )
    return roadefset


@pytest.fixture()
def congestionprofiles():
    # array representing heavy level of service
    test_profile = np.ones((24, 7)) * 1
    test_profile[:7, :] = 2
    test_profile[23:, :] = 2
    congestion_profile1 = CongestionProfile.objects.create(
        name="free-flow", traffic_condition=str(test_profile.tolist())
    )
    congestion_profile2 = CongestionProfile.objects.create(
        name="heavy", traffic_condition=str(test_profile.tolist())
    )
    return [congestion_profile1, congestion_profile2]


@pytest.fixture()
def pointsources(activities, code_sets, testsettings):
    code_set1, code_set2 = code_sets
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    ac1 = dict([(ac.code, ac) for ac in code_set1.codes.all()])
    ac2 = dict([(ac.code, ac) for ac in code_set2.codes.all()])
    src1 = models.PointSource.objects.create(
        name="pointsource1",
        geom=Point(x=17.1, y=51.1, srid=WGS84_SRID),
        tags={"tag1": "A", "tag2": "A"},
        activitycode1=ac1["1"],
    )
    src2 = models.PointSource.objects.create(
        name="pointsource2",
        geom=Point(x=17.1, y=51.1, srid=WGS84_SRID),
        tags={"tag1": "A", "tag2": "B"},
        activitycode1=ac1["1.1"],
    )
    src3 = models.PointSource.objects.create(
        name="pointsource3",
        geom=Point(x=17.1, y=51.1, srid=WGS84_SRID),
        tags={"tag1": "A", "tag2": "B"},
        activitycode1=ac1["1.2"],
    )
    src4 = models.PointSource.objects.create(
        name="pointsource4",
        geom=Point(x=17.1, y=51.1, srid=WGS84_SRID),
        tags={"tag1": "A", "tag2": "B"},
        activitycode1=ac1["1.2"],
        activitycode2=ac2["A"],
    )
    # some substance emissions with varying attributes
    src1.substances.create(substance=NOx, value=emission_unit_to_si(1000, "ton/year"))
    src1.substances.create(substance=SOx, value=emission_unit_to_si(2000, "ton/year"))
    src2.substances.create(substance=SOx, value=emission_unit_to_si(1000, "ton/year"))
    src3.substances.create(substance=SOx, value=emission_unit_to_si(1000, "ton/year"))
    # some emission factor emissions
    src1.activities.create(
        activity=activities[0], rate=activity_rate_unit_to_si(1000, "m3/year")
    )
    return (src1, src2, src3, src4)


@pytest.fixture()
def areasources(activities, code_sets):
    NOx = Substance.objects.get(slug="NOx")
    SOx = Substance.objects.get(slug="SOx")

    # ac1 = dict([(ac.code, ac) for ac in inv1.base_set.code_set1.codes.all()])
    ac1 = code_sets[0]

    src1 = models.AreaSource.objects.create(
        name="areasource1",
        geom=Polygon(
            ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
            srid=WGS84_SRID,
        ),
        tags={"tag1": "A", "tag2": "B"},
        activitycode1=ac1.codes.get(code="1.2"),
    )

    # some substance emissions with varying attributes
    src1.substances.create(substance=NOx, value=emission_unit_to_si(1000, "ton/year"))
    src1.substances.create(substance=SOx, value=emission_unit_to_si(2000, "ton/year"))

    src2 = models.AreaSource.objects.create(
        name="areasource2",
        geom=Polygon(
            ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
            srid=WGS84_SRID,
        ),
        tags={"tag1": "A"},
        activitycode1=ac1.codes.get(code="2.2"),
    )

    # some emission factor emissions
    src2.activities.create(
        activity=activities[0], rate=activity_rate_unit_to_si(1000, "m3/year")
    )

    src3 = models.AreaSource.objects.create(
        name="areasource3",
        geom=Polygon(
            ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
            srid=WGS84_SRID,
        ),
    )
    src4 = models.AreaSource.objects.create(
        name="areasource4",
        geom=Polygon(
            ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
            srid=WGS84_SRID,
        ),
    )
    src5 = models.AreaSource.objects.create(
        name="areasource5",
        geom=Polygon(
            ((18.7, 51.1), (18.8, 51.1), (18.8, 51.0), (18.7, 51.0), (18.7, 51.1)),
            srid=WGS84_SRID,
        ),
    )
    src6 = models.AreaSource.objects.create(
        name="areasource6",
        geom=Polygon(
            ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
            srid=WGS84_SRID,
        ),
    )
    src7 = models.AreaSource.objects.create(
        name="areasource7",
        geom=Polygon(
            ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
            srid=WGS84_SRID,
        ),
    )

    # inv3 is related to source ef set 2
    src8 = models.AreaSource.objects.create(
        name="areasource8",
        geom=Polygon(
            ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
            srid=WGS84_SRID,
        ),
    )
    return (src1, src2, src3, src4, src5, src6, src7, src8)


@pytest.fixture()
def gridsource_raster(tmpdir, transactional_db):
    nrows = 2
    ncols = 2
    x1, y1, x2, y2 = (0, 0, 1000, 1000)
    name = "raster1"
    data = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)

    transform = rio.transform.from_bounds(x1, y1, x2, y2, width=ncols, height=nrows)
    rasterfile = str(os.path.join(tmpdir, "gridsource_raster.tiff"))
    with rio.open(
        rasterfile,
        "w",
        **GTiffProfile(),
        width=ncols,
        height=nrows,
        transform=transform,
        crs=3006,
    ) as dset:
        dset.write(data, 1)
    with rio.open(rasterfile, "r") as raster:
        write_gridsource_raster(raster, name)
    return name


@pytest.fixture()
def gridsources(activities, code_sets, gridsource_raster):
    NOx = Substance.objects.get(slug="NOx")
    SOx = Substance.objects.get(slug="SOx")
    code_set1, code_set2 = code_sets
    ac1 = dict([(ac.code, ac) for ac in code_set1.codes.all()])
    src1 = models.GridSource.objects.create(
        name="gridsource1",
        tags={"tag1": "A", "tag2": "B"},
        activitycode1=ac1["3"],
    )
    src1.substances.create(
        substance=NOx,
        value=emission_unit_to_si(500.0, "ton/year"),
        raster=gridsource_raster,
    )
    src1.substances.create(
        substance=SOx,
        value=emission_unit_to_si(300.0, "ton/year"),
        raster=gridsource_raster,
    )
    src1.activities.create(
        activity=activities[0],
        rate=activity_rate_unit_to_si(1000, "m3/year"),
        raster=gridsource_raster,
    )
    return [src1]
