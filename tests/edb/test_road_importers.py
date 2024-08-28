import ast
from contextlib import ExitStack
from importlib import resources

import pytest
from ruamel.yaml import YAML

from cetk.edb.importers import fleet_excel_to_dict  # noqa
from cetk.edb.importers import (
    import_congestion_profiles,
    import_fleets,
    import_roadclasses,
    import_roads,
    import_timevars,
    import_vehicles,
    roadclass_excel_to_dict,
    roadsource_excel_to_dict,
    vehicles_excel_to_dict,
)
from cetk.edb.models import ColdstartTimevar  # noqa
from cetk.edb.models import (
    CongestionProfile,
    Fleet,
    FlowTimevar,
    RoadClass,
    RoadSource,
    Timevar,
    Vehicle,
    VehicleFuel,
)


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


def test_import_vehicles(code_sets, get_data_file):
    """test importing vehicles from csv."""
    code_set1, code_set2 = code_sets[:2]
    vehiclefile = get_data_file("vehicles.csv")
    vehiclesettings = get_yaml_data("vehicles.yaml")
    import_vehicles(vehiclefile, vehiclesettings, unit="kg/m", encoding="utf-8")
    assert VehicleFuel.objects.filter(name="diesel").exists()
    assert VehicleFuel.objects.filter(name="petrol").exists()
    assert Vehicle.objects.filter(name="car").exists()
    assert Vehicle.objects.filter(name="lorry").exists()

    car = Vehicle.objects.get(name="car")
    lorry = Vehicle.objects.get(name="lorry")
    assert car.emissionfactors.filter(substance__slug="NOx").count() == 2
    assert car.emissionfactors.filter(substance__slug="SOx").count() == 2
    ef = car.emissionfactors.get(
        substance__slug="NOx",
        fuel__name="diesel",
        traffic_situation__ts_id="1a",
    )
    assert ef.freeflow == 1
    assert ef.heavy == 2
    assert ef.saturated == 3
    assert ef.stopngo == 4
    assert ef.coldstart == 5

    settingsfile = get_data_file("vehicle_settings.xlsx")
    vehiclesettings = vehicles_excel_to_dict(settingsfile)
    import_vehicles(
        vehiclefile, vehiclesettings, unit="kg/m", encoding="utf-8", overwrite=True
    )
    assert car.emissionfactors.filter(substance__slug="SOx").count() == 2

    car_petrol = car.vehiclefuelcombs.get(fuel__name="petrol")
    car_diesel = car.vehiclefuelcombs.get(fuel__name="diesel")
    lorry_diesel = lorry.vehiclefuelcombs.get(fuel__name="diesel")

    assert car_petrol.activitycode1.code == "1.3.1"
    assert car_diesel.activitycode2.code == "A"

    assert lorry_diesel.activitycode1.code == "1.3.2"
    assert lorry_diesel.activitycode2.code == "A"


def test_import_vehicles_xlsx(code_sets, get_data_file):
    """test importing vehicles from xlsx."""

    code_set1, code_set2 = code_sets[:2]
    vehiclefile = get_data_file("vehicles.xlsx")
    vehiclesettings = get_yaml_data("vehicles.yaml")
    import_vehicles(vehiclefile, vehiclesettings, unit="kg/m", encoding="utf-8")
    assert VehicleFuel.objects.filter(name="diesel").exists()


def test_import_roadclasses(code_sets, get_data_file):
    """test importing roadclasses."""
    assert RoadClass.objects.count() == 0
    code_set1, code_set2 = code_sets[:2]
    assert RoadClass.objects.count() == 0
    vehiclefile = get_data_file("vehicles.csv")
    vehiclesettings = get_yaml_data("vehicles.yaml")
    import_vehicles(vehiclefile, vehiclesettings, unit="kg/m", encoding="utf-8")
    assert RoadClass.objects.count() == 0
    roadclassfile = get_data_file("roadclasses.csv")
    roadclass_settings = get_yaml_data("roadclasses.yaml")
    import_roadclasses(roadclassfile, roadclass_settings, encoding="utf-8")
    assert RoadClass.objects.count() == 2
    # set more asserts now that roadclasstree removed
    # assert rc_tree["attribute"] == "roadtype"
    # assert "motorway" in rc_tree["values"]
    # assert rc_tree["values"]["motorway"]["attribute"] == "speed"
    # assert "90" in rc_tree["values"]["motorway"]["values"]
    # assert "primary road" in rc_tree["values"]
    # assert rc_tree["values"]["primary road"]["attribute"] == "speed"
    # assert "70" in rc_tree["values"]["primary road"]["values"]

    # test excel
    roadclass_settings, _ = roadclass_excel_to_dict(
        get_data_file("roadclass_settings.xlsx")
    )
    # test overwrite
    import_roadclasses(
        get_data_file("roadclass_settings.xlsx"),
        roadclass_settings,
        encoding="utf-8",
        overwrite=True,
    )
    assert RoadClass.objects.all().count() == 6


def test_import_roadclasses_1attr(code_sets, get_data_file):
    code_set1, code_set2 = code_sets[:2]
    vehiclefile = get_data_file("vehicles.csv")
    vehiclesettings = get_yaml_data("vehicles.yaml")
    import_vehicles(vehiclefile, vehiclesettings, unit="kg/m", encoding="utf-8")

    roadclassfile = get_data_file("roadclasses_1attr.csv")
    roadclass_settings = get_yaml_data("roadclasses_1attr.yaml")
    import_roadclasses(roadclassfile, roadclass_settings, encoding="utf-8")

    assert RoadClass.objects.all().count() == 2
    # set more asserts now that rctree removed
    # assert rc_tree["attribute"] == "roadtype"
    # assert "motorway" in rc_tree["values"]
    # assert "primary road" in rc_tree["values"]

    # test overwrite
    import_roadclasses(
        roadclassfile,
        roadclass_settings,
        encoding="utf-8",
        overwrite=True,
    )
    assert RoadClass.objects.all().count() == 2


def test_import_timevars(db, get_data_file):
    timevarfile = get_data_file("timevars.yaml")
    import_timevars(get_yaml_data(timevarfile))
    assert FlowTimevar.objects.all().count() == 2
    turist = FlowTimevar.objects.get(name="tourist (heavy)")
    turist_typeday = ast.literal_eval(turist.typeday)
    assert turist_typeday[1][1] == 253
    assert ColdstartTimevar.objects.all().count() == 1
    kall = ColdstartTimevar.objects.get(name="all")
    kall_typeday = ast.literal_eval(kall.typeday)
    assert kall_typeday[1][1] == 1154
    assert Timevar.objects.all().count() == 1

    # test overwriting
    import_timevars(get_yaml_data(timevarfile), overwrite=True)
    assert FlowTimevar.objects.all().count() == 2
    assert ColdstartTimevar.objects.all().count() == 1
    assert Timevar.objects.all().count() == 1


def test_import_congestion_profiles(db, get_data_file):
    congestionprofile_file = get_data_file("congestion_profiles.yaml")
    profile_data = get_yaml_data(congestionprofile_file)
    import_congestion_profiles(profile_data)
    assert CongestionProfile.objects.all().count() == 2
    profile = CongestionProfile.objects.get(name="busy")
    assert ast.literal_eval(profile.traffic_condition)[6][0] == 2

    # test overwriting
    import_congestion_profiles(profile_data, overwrite=True)
    assert CongestionProfile.objects.all().count() == 2


def test_import_fleets(db, get_data_file):
    ColdstartTimevar.objects.create(name="constant")
    FlowTimevar.objects.create(name="constant")
    VehicleFuel.objects.create(name="petrol")
    VehicleFuel.objects.create(name="diesel")
    Vehicle.objects.create(name="car")
    Vehicle.objects.create(name="lorry", isheavy=True)

    fleetfile = get_data_file("fleets.yaml")
    fleet_data = get_yaml_data(fleetfile)
    import_fleets(fleet_data)

    assert Fleet.objects.all().count() == 2
    fleet1 = Fleet.objects.get(name="europavägar tätort")
    fleet2 = Fleet.objects.get(name="europavägar landsbygd")

    assert fleet1.vehicles.all().count() == 2
    car1 = fleet1.vehicles.get(vehicle__name="car")
    car1_petrol = car1.fuels.get(fuel__name="petrol")
    car1_diesel = car1.fuels.get(fuel__name="diesel")

    assert car1_petrol.fraction == 0.7
    assert car1_diesel.fraction == 0.3

    lorry1 = fleet1.vehicles.get(vehicle__name="lorry")
    lorry1_diesel = lorry1.fuels.get(fuel__name="diesel")

    assert lorry1_diesel.fraction == 1.0

    assert car1.coldstart_timevar.name == "constant"
    assert car1.timevar.name == "constant"
    assert car1.coldstart_fraction == 0.27

    assert fleet1.default_heavy_vehicle_share == 0.1
    assert fleet2.vehicles.all().count() == 1

    # test overwrite

    fleet_data2, _ = fleet_excel_to_dict(get_data_file("fleets.xlsx"))
    import_fleets(fleet_data2, overwrite=True)
    fleet1 = Fleet.objects.get(name="europavägar tätort")
    assert fleet1.vehicles.all().count() == 2
    assert fleet1.vehicles.get(vehicle__name="car").fuels.all().count() == 2


class TestImportRoads:
    def test_import_roads(self, roadefset, get_data_file):
        config = get_yaml_data("roads.yaml")
        import_roads(get_data_file("roaddata.gpkg"), config)

        assert RoadSource.objects.all().count() == 26
        road1 = RoadSource.objects.get(name="Nynäsvägen")
        assert road1.speed == 90
        assert road1.width == 11.5
        assert road1.nolanes == 2
        assert road1.aadt == 24053
        assert road1.fleet.name == "default"
        assert road1.congestion_profile is None
        assert road1.roadclass.attributes == {"roadtype": "1", "speed": "90"}

        config2 = roadsource_excel_to_dict(get_data_file("roads.xlsx"))
        import_roads(get_data_file(config2["filepath"]), config2)
        assert RoadSource.objects.all().count() == 2 * 26
        # roadsources are not updated as other sources are

    def test_import_roads_exclude(self, roadefset, get_data_file):
        config = get_yaml_data("roads.yaml")
        import_roads(
            get_data_file("roaddata.gpkg"),
            config,
            exclude={"KOMMUNKOD": "0126"},
        )

        assert RoadSource.objects.all().count() == 25
        with pytest.raises(RoadSource.DoesNotExist):
            RoadSource.objects.get(name="Nynäsvägen")

    def test_import_roads_only(self, roadefset, get_data_file):
        config = get_yaml_data("roads.yaml")
        import_roads(
            get_data_file("roaddata.gpkg"),
            config,
            only={"KOMMUNKOD": "0126"},
        )

        nroads = RoadSource.objects.all().count()
        assert nroads > 0
        assert RoadSource.objects.filter(tags__KOMMUNKOD="0126").count() == nroads
