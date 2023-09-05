"""Global pytest configuration."""

# import numpy as np
import pytest
import sys

if sys.argv[0] != "pytest" and "--help" not in sys.argv:
    from etk.edb.models.source_models import CodeSet, Domain  # , Substance

# from django.contrib.auth import get_user_model
# from django.contrib.gis.gdal import GDALRaster
# from django.contrib.gis.geos import LineString, Point, Polygon


# from etk.edb.units import (
#     activity_ef_unit_to_si,
#     activity_rate_unit_to_si,
#     emission_unit_to_si,
#     vehicle_ef_unit_to_si,
# )

# SPEEDS = ["20", "30", "40", "50", "60", "70", "80", "90", "100", "110", "120", "130"]

# ROADTYPES = ["highway", "primary", "secondary", "tertiary", "residential", "busway"]
# SWEREF99_TM_SRID = 3006
# WGS84_SRID = 4326
# DUMMY_SRID = 3857


# @pytest.fixture()
# def activities(db, source_ef_sets):
#     subst1 = Substance.objects.get(slug="NOx")
#     subst2 = Substance.objects.get(slug="SOx")
#     sefs1 = source_ef_sets[0]
#     act1 = models.Activity.objects.create(
#         base_set=sefs1.base_set, name="activity1", unit="m3"
#     )
#     act1.emissionfactors.create(
#         substance=subst1, factor=activity_ef_unit_to_si(10.0, "kg/m3"), ef_set=sefs1
#     )
#     act1.emissionfactors.create(
#         substance=subst2, factor=activity_ef_unit_to_si(1.0, "kg/m3"), ef_set=sefs1
#     )
#     return (act1,)


# @pytest.fixture()
# def users(db):
#     user1 = get_user_model().objects.create(username="user1")
#     user2 = get_user_model().objects.create(username="user2")
#     return (user1, user2)


@pytest.fixture()
def domains(db):
    extent = (
        "MULTIPOLYGON ((("
        "10.95 50.33, 24.16 50.33, 24.16 69.06, 10.95 69.06, 10.95 50.33"
        ")))"
    )
    dmn1 = Domain.objects.create(
        name="Domain 1",
        slug="domain-1",
        srid=3006,
        extent=extent,
        timezone="Europe/Stockholm",
    )
    dmn2 = Domain.objects.create(
        name="Domain 2",
        slug="domain-2",
        srid=3006,
        extent=extent,
        timezone="Europe/Stockholm",
    )
    return (dmn1, dmn2)


@pytest.fixture()
def vertical_dist(domains):
    dmn1 = domains[0]
    vdist = dmn1.vertical_dists.create(
        name="vdist1", weights="[[5.0, 0.4], [10.0, 0.6]]"
    )
    return vdist


# @pytest.fixture()
# def base_sets(users, domains, ifactory, code_sets):
#     # don't use project fixture as base_set in simair may belong to a superset, this
#     # way base_set is not belonging to the same project as e.g. road_ef_sets fixture
#     user1, user2 = users
#     dmn1, dmn2 = domains[:2]
#     codeset1, codeset2 = code_sets

#     proj1 = ifactory.core.project(manager=user1, domain=dmn1)
#     proj2 = ifactory.core.project(manager=user2, domain=dmn1)

#     base_set1 = ifactory.edb.baseset(
#         project=proj1, code_set1=codeset1, code_set2=codeset2
#     )
#     base_set2 = ifactory.edb.baseset(project=proj2)

#     for base_set in (base_set1, base_set2):
#         base_set.vehicle_fuels.create(name="petrol")
#         base_set.vehicle_fuels.create(name="diesel")

#     return (base_set1, base_set2)


# @pytest.fixture()
# def road_ef_sets(users, base_sets, ifactory):
#     user1, user2 = users
#     base1, base2 = base_sets

#     road_ef_set1 = models.RoadEFSet.objects.create(
#         name="Road EF Set 1", owner=user1, project=proj1, year=2016, base_set=base1
#     )

#     road_ef_set2 = models.RoadEFSet.objects.create(
#         name="Road EF Set 2", owner=user1, year=2016, project=proj1, base_set=base1
#     )

#     road_ef_set3 = models.RoadEFSet.objects.create(
#         name="Road EF Set 3", owner=user2, project=proj2, year=2016, base_set=base2
#     )

#     return (road_ef_set1, road_ef_set2, road_ef_set3)


# @pytest.fixture()
# def source_ef_sets(users, base_sets, ifactory):
#     user1, user2 = users
#     base1, base2 = base_sets

#     source_ef_set1 = models.SourceEFSet.objects.create(
#         name="Source EF Set 1", owner=user1, project=proj1, year=2016, base_set=base1
#     )

#     source_ef_set2 = models.SourceEFSet.objects.create(
#         name="Source EF Set 2", owner=user1, year=2016, project=proj1, base_set=base1
#     )

#     source_ef_set3 = models.SourceEFSet.objects.create(
#         name="Source EF Set 3", owner=user2, project=proj2, year=2016, base_set=base2
#     )

#     for base_set in models.BaseSet.objects.all():
#         ifactory.edb.fuel(base_set=base_set, name="diesel")
#         ifactory.edb.fuel(base_set=base_set, name="petrol")

#     return source_ef_set1, source_ef_set2, source_ef_set3


@pytest.fixture()
def code_sets(domains, vertical_dist):
    domain = domains[0]
    cs1 = CodeSet.objects.create(name="codeset1", slug="codeset1", domain=domain)
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

    cs2 = CodeSet.objects.create(name="codeset2", slug="codeset2", domain=domain)
    cs2.codes.create(code="A", label="Bla bla")

    return (cs1, cs2)


# @pytest.fixture()
# def vehicles(base_sets, road_ef_sets, ifactory):
#     road_ef_set1, road_ef_set2 = road_ef_sets[:2]

#     substances = list(Substance.objects.filter(slug__in=("NOx", "SOx")))
#     base_set = base_sets[0]

#     # create test vehicles
#     veh1 = models.Vehicle.objects.create(base_set=base_set, name="car", isheavy=False)
#     veh2 = models.Vehicle.objects.create(base_set=base_set, name="truck",
#  isheavy=True)
#     vehicles = [veh1, veh2]

#     # add emission factors for vehicles in different traffic situations
#     efs = []

#     for roadtype in ROADTYPES:
#         for speed in SPEEDS:
#             ts = models.TrafficSituation.objects.create(
#                 base_set=base_set, ts_id=f"{roadtype}_{speed}"
#             )
#             for subst in substances:
#                 for veh in vehicles:
#                     for fuel in base_set.vehicle_fuels.all():
#                         efs.append(
#                             models.VehicleEF(
#                                 ef_set=road_ef_set1,
#                                 traffic_situation=ts,
#                                 substance=subst,
#                                 vehicle=veh,
#                                 fuel=fuel,
#                                 freeflow=vehicle_ef_unit_to_si(100.0, "mg", "km"),
#                                 heavy=vehicle_ef_unit_to_si(200.0, "mg", "km"),
#                                 saturated=vehicle_ef_unit_to_si(300.0, "mg", "km"),
#                                 stopngo=vehicle_ef_unit_to_si(400.0, "mg", "km"),
#                                 coldstart=vehicle_ef_unit_to_si(10.0, "mg", "km"),
#                             )
#                         )
#                         efs.append(
#                             models.VehicleEF(
#                                 ef_set=road_ef_set2,
#                                 traffic_situation=ts,
#                                 substance=subst,
#                                 vehicle=veh,
#                                 fuel=fuel,
#                                 freeflow=vehicle_ef_unit_to_si(100.0, "mg", "km"),
#                                 heavy=vehicle_ef_unit_to_si(200.0, "mg", "km"),
#                                 saturated=vehicle_ef_unit_to_si(300.0, "mg", "km"),
#                                 stopngo=vehicle_ef_unit_to_si(400.0, "mg", "km"),
#                                 coldstart=vehicle_ef_unit_to_si(10.0, "mg", "km"),
#                             )
#                         )
#     models.VehicleEF.objects.bulk_create(efs)
#     return vehicles


# @pytest.fixture
# def roadclasses(vehicles):
#     base_set = vehicles[0].base_set

#     rca_roadtype = models.RoadAttribute.objects.create(
#         base_set=base_set, name="road type", slug="roadtype", order=1
#     )
#     rca_speed = models.RoadAttribute.objects.create(
#         base_set=base_set, name="speed", slug="speed", order=2
#     )

#     def create_road_class(roadtype, speed):
#         return rc

#     roadclasses = []
#     for roadtype in ROADTYPES:
#         for speed in SPEEDS:
#             ts = models.TrafficSituation.objects.get(ts_id=f"{roadtype}_{speed}")
#             rc = models.RoadClass.objects.create(traffic_situation=ts)

#             rc.attribute_values.add(
#                 models.RoadAttributeValue.objects.get_or_create(
#                     attribute=rca_roadtype, value=roadtype
#                 )[0]
#             )
#             rc.attribute_values.add(
#                 models.RoadAttributeValue.objects.get_or_create(
#                     attribute=rca_speed, value=speed
#                 )[0]
#             )
#             rc.save()
#             roadclasses.append(rc)
#     return roadclasses


# @pytest.fixture()
# def fleets(inventories, vehicles):
#     """Create templates for fleet composition."""

#     inv1 = inventories[0]
#     base_set = inv1.base_set
#     car, truck = vehicles[:2]

#     ac1 = dict([(ac.code, ac) for ac in base_set.code_set1.codes.all()])
#     constant_flow = inv1.flow_timevars.get(name="constant")
#     coldstart_timevar = inv1.coldstart_timevars.first()
#     daytime_flow = inv1.flow_timevars.get(name="daytime")
#     petrol = inv1.base_set.vehicle_fuels.get(name="petrol")
#     diesel = inv1.base_set.vehicle_fuels.get(name="diesel")

#     base_set.vehiclefuelcombs.create(
#         fuel=petrol, vehicle=car, activitycode1=ac1["1.3.1"]
#     )
#     base_set.vehiclefuelcombs.create(
#         fuel=diesel, vehicle=car, activitycode1=ac1["1.3.1"]
#     )
#     base_set.vehiclefuelcombs.create(
#         fuel=diesel, vehicle=truck, activitycode1=ac1["1.3.2"]
#     )
#     base_set.vehiclefuelcombs.create(
#         fuel=petrol, vehicle=truck, activitycode1=ac1["1.3.2"]
#     )

#     fleet1 = models.Fleet.objects.create(
#         inventory=inv1, name="fleet1", default_heavy_vehicle_share=0.5
#     )
#     fleet_member1 = fleet1.vehicles.create(
#         vehicle=car,
#         timevar=constant_flow,
#         fraction=1.0,
#         coldstart_timevar=coldstart_timevar,
#         coldstart_fraction=0.2,
#     )
#     fleet_member1.fuels.create(fuel=diesel, fraction=0.2)
#     fleet_member1.fuels.create(fuel=petrol, fraction=0.8)

#     fleet_member2 = fleet1.vehicles.create(
#         vehicle=truck,
#         timevar=daytime_flow,
#         fraction=1.0,
#         coldstart_timevar=coldstart_timevar,
#         coldstart_fraction=0.2,
#     )
#     fleet_member2.fuels.create(fuel=diesel, fraction=0.2)
#     fleet_member2.fuels.create(fuel=petrol, fraction=0.8)

#     fleet2 = models.Fleet.objects.create(
#         inventory=inv1, name="fleet2", default_heavy_vehicle_share=0.9
#     )
#     fleet_member3 = fleet2.vehicles.create(
#         vehicle=car,
#         timevar=constant_flow,
#         fraction=1.0,
#         coldstart_timevar=coldstart_timevar,
#         coldstart_fraction=0.2,
#     )
#     fleet_member3.fuels.create(fuel=diesel, fraction=1.0)
#     fleet_member4 = fleet2.vehicles.create(
#         vehicle=truck,
#         timevar=daytime_flow,
#         fraction=1.0,
#         coldstart_timevar=coldstart_timevar,
#         coldstart_fraction=0.2,
#     )
#     fleet_member4.fuels.create(fuel=diesel, fraction=1.0)
#     return [fleet1, fleet2]


# @pytest.fixture()
# def roadsources(inventories, roadclasses, fleets):
#     """Create road sources."""

#     inv1 = inventories[0]
#     fleet1, fleet2 = fleets[:2]
#     freeflow = inv1.congestion_profiles.get(name="free-flow")
#     heavy = inv1.congestion_profiles.get(name="heavy")
#     road1 = models.RoadSource.objects.create(
#         name="road1",
#         geom=LineString((17.1, 52.5), (17.15, 52.5), (17.152, 52.6), srid=WGS84_SRID),
#         tags={"tag2": "B"},
#         inventory=inv1,
#         aadt=1000,
#         speed=80,
#         width=20,
#         roadclass=roadclasses[0],
#         fleet=fleet1,
#         congestion_profile=freeflow,
#     )

#     road2 = models.RoadSource.objects.create(
#         name="road2",
#         inventory=inv1,
#         geom=LineString((17.1, 52.5), (17.15, 52.5), (17.152, 52.6), srid=WGS84_SRID),
#         aadt=2000,
#         speed=70,
#         width=15,
#         roadclass=roadclasses[0],
#         fleet=fleet2,
#         congestion_profile=heavy,
#     )

#     road3 = models.RoadSource.objects.create(
#         name="road3",
#         inventory=inv1,
#         geom=LineString((16.1, 52.5), (16.15, 52.5), (16.152, 52.6), srid=WGS84_SRID),
#         aadt=2000,
#         speed=70,
#         width=15,
#         roadclass=roadclasses[0],
#         fleet=fleet2,
#         heavy_vehicle_share=0.5,
#         congestion_profile=heavy,
#         tags={"test1": "tag 1"},
#     )

#     return [road1, road2, road3]


# @pytest.fixture()
# def pointsources(inventories, activities):
#     inv1, inv2, inv3, inv4 = inventories[:4]
#     NOx = Substance.objects.get(slug="NOx")
#     SOx = Substance.objects.get(slug="SOx")
#     ac1 = dict([(ac.code, ac) for ac in inv1.base_set.code_set1.codes.all()])
#     ac2 = dict([(ac.code, ac) for ac in inv1.base_set.code_set2.codes.all()])
#     src1 = models.PointSource.objects.create(
#         name="pointsource1",
#         inventory=inv1,
#         geom=Point(x=17.1, y=51.1, srid=WGS84_SRID),
#         tags={"tag1": "A", "tag2": "A"},
#         activitycode1=ac1["1"],
#     )

#     src2 = models.PointSource.objects.create(
#         name="pointsource2",
#         inventory=inv1,
#         geom=Point(x=17.1, y=51.1, srid=WGS84_SRID),
#         tags={"tag1": "A", "tag2": "B"},
#         activitycode1=ac1["1.1"],
#     )

#     src3 = models.PointSource.objects.create(
#         name="pointsource3",
#         inventory=inv1,
#         geom=Point(x=17.1, y=51.1, srid=WGS84_SRID),
#         tags={"tag1": "A", "tag2": "B"},
#         activitycode1=ac1["1.2"],
#     )

#     src4 = models.PointSource.objects.create(
#         name="pointsource4",
#         inventory=inv1,
#         geom=Point(x=17.1, y=51.1, srid=WGS84_SRID),
#         tags={"tag1": "A", "tag2": "B"},
#         activitycode1=ac1["1.2"],
#         activitycode2=ac2["A"],
#     )

#     # some substance emissions with varying attributes
#     src1.substances.create(substance=NOx, value=1000)
#     src1.substances.create(substance=SOx, value=emission_unit_to_si(2000, "ton/year"))
#     src2.substances.create(substance=SOx, value=emission_unit_to_si(1000, "ton/year"))
#     src3.substances.create(substance=SOx, value=emission_unit_to_si(1000, "ton/year"))

#     # some emission factor emissions
#     src1.activities.create(
#         activity=activities[0], rate=activity_rate_unit_to_si(1000, "m3/year")
#     )

#     src5 = models.PointSource.objects.create(
#         name="pointsource5", geom=Point(x=17.2, y=51.1, srid=WGS84_SRID)
#     )
#     src6 = models.PointSource.objects.create(
#         name="pointsource6", geom=Point(x=17.3, y=51.1, srid=WGS84_SRID)
#     )
#     src7 = models.PointSource.objects.create(
#         name="pointsource7", geom=Point(x=17.4, y=51.1, srid=WGS84_SRID)
#     )
#     src8 = models.PointSource.objects.create(
#         name="pointsource8", geom=Point(x=17.5, y=51.1, srid=WGS84_SRID)
#     )
#     src9 = models.PointSource.objects.create(
#         name="pointsource9", geom=Point(x=17.6, y=51.1, srid=WGS84_SRID)
#     )
#     src10 = models.PointSource.objects.create(
#         name="pointsource10",
#         inventory=inv4,
#         geom=Point(x=17.7, y=51.1, srid=WGS84_SRID),
#     )
#     # inv3 isrelated to source ef-set 2
#     src11 = models.PointSource.objects.create(
#         name="pointsource11",
#         inventory=inv3,
#         geom=Point(x=17.7, y=51.1, srid=WGS84_SRID),
#     )
#     return (src1, src2, src3, src4, src5, src6, src7, src8, src9, src10, src11)


# @pytest.fixture()
# def areasources(source_ef_sets, inventories, activities):
#     inv1, inv2, inv3, inv4 = inventories[:4]
#     NOx = Substance.objects.get(slug="NOx")
#     SOx = Substance.objects.get(slug="SOx")

#     ac1 = dict([(ac.code, ac) for ac in inv1.base_set.code_set1.codes.all()])

#     src1 = models.AreaSource.objects.create(
#         name="areasource1",
#         inventory=inv1,
#         geom=Polygon(
#             ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
#             srid=WGS84_SRID,
#         ),
#         tags={"tag1": "A", "tag2": "B"},
#         activitycode1=ac1["1.2"],
#     )

#     # some substance emissions with varying attributes
#     src1.substances.create(substance=NOx, value=emission_unit_to_si(1000, "ton/year"))
#     src1.substances.create(substance=SOx, value=emission_unit_to_si(2000, "ton/year"))

#     src2 = models.AreaSource.objects.create(
#         name="areasource2",
#         inventory=inv1,
#         geom=Polygon(
#             ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
#             srid=WGS84_SRID,
#         ),
#         tags={"tag1": "A"},
#         activitycode1=ac1["2.2"],
#     )

#     # some emission factor emissions
#     src2.activities.create(
#         activity=activities[0], rate=activity_rate_unit_to_si(1000, "m3/year")
#     )

#     src3 = models.AreaSource.objects.create(
#         name="areasource3",
#         inventory=inv2,
#         geom=Polygon(
#             ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
#             srid=WGS84_SRID,
#         ),
#     )
#     src4 = models.AreaSource.objects.create(
#         name="areasource4",
#         inventory=inv1,
#         geom=Polygon(
#             ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
#             srid=WGS84_SRID,
#         ),
#     )
#     src5 = models.AreaSource.objects.create(
#         name="areasource5",
#         inventory=inv1,
#         geom=Polygon(
#             ((18.7, 51.1), (18.8, 51.1), (18.8, 51.0), (18.7, 51.0), (18.7, 51.1)),
#             srid=WGS84_SRID,
#         ),
#     )
#     src6 = models.AreaSource.objects.create(
#         name="areasource6",
#         inventory=inv1,
#         geom=Polygon(
#             ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
#             srid=WGS84_SRID,
#         ),
#     )
#     src7 = models.AreaSource.objects.create(
#         name="areasource7",
#         inventory=inv4,
#         geom=Polygon(
#             ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
#             srid=WGS84_SRID,
#         ),
#     )

#     # inv3 is related to source ef set 2
#     src8 = models.AreaSource.objects.create(
#         name="areasource8",
#         inventory=inv3,
#         geom=Polygon(
#             ((17.7, 51.1), (17.8, 51.1), (17.8, 51.0), (17.7, 51.0), (17.7, 51.1)),
#             srid=WGS84_SRID,
#         ),
#     )
#     return (src1, src2, src3, src4, src5, src6, src7, src8)


# @pytest.fixture()
# def gridsources(inventories, activities):
#     NOx = Substance.objects.get(slug="NOx")
#     SOx = Substance.objects.get(slug="SOx")

#     inv1, inv2, inv3, inv4 = inventories[:4]
#     ac1 = dict([(ac.code, ac) for ac in inv1.base_set.code_set1.codes.all()])
#     # scale is cellsize (should be negative in y direction as in GDAL
#     # standard) origin is upper left corner
#     gdal_raster = GDALRaster(
#         {
#             "srid": DUMMY_SRID,
#             "width": 2,
#             "height": 2,
#             "datatype": 6,
#             "scale": (100, -100),
#             "origin": (0, 1000),
#             "bands": [{"data": [0.1, 0.2, 0.3, 0.4]}],
#         }
#     )
#     raster = models.GridSourceRaster.objects.create(
#         name="test raster1", inventory=inv1, srid=3006, geom=gdal_raster
#     )

#     src1 = models.GridSource.objects.create(
#         name="gridsource1",
#         inventory=inv1,
#         tags={"tag1": "A", "tag2": "B"},
#         activitycode1=ac1["3"],
#     )
#     src1.substances.create(substance=NOx, value=5.0, raster=raster)
#     src1.substances.create(substance=SOx, value=3.0, raster=raster)
#     src1.activities.create(activity=activities[0], rate=10, raster=raster)

#     return [src1]
