from contextlib import ExitStack
from importlib import resources

import pytest
from ruamel.yaml import YAML

from etk.edb.importers import (  # noqa
    import_congestion_profiles,
    import_fleets,
    import_roadclasses,
    import_roads,
    import_vehicles,
)
from etk.edb.models import (  # noqa
    CodeSet,
    ColdstartTimevar,
    CongestionProfile,
    FleetMemberFuel,
    FlowTimevar,
    PrefetchRoadClassAttributes,
    RoadClass,
    RoadSource,
    Substance,
    Timevar,
    TrafficSituation,
    Vehicle,
    VehicleEF,
    VehicleFuel,
    VehicleFuelComb,
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
    import_vehicles(vehiclefile, vehiclesettings, 2019, unit="kg/m", encoding="utf-8")
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

    import_vehicles(
        vehiclefile,
        vehiclesettings,
        2019,
        unit="kg/m",
        encoding="utf-8",
        overwrite=True,
    )
    assert car.emissionfactors.filter(substance__slug="SOx").count() == 2

    car_petrol = car.vehiclefuelcombs.get(fuel__name="petrol")
    car_diesel = car.vehiclefuelcombs.get(fuel__name="diesel")
    lorry_diesel = lorry.vehiclefuelcombs.get(fuel__name="diesel")

    assert car_petrol.activitycode1.code == "1.3.1"
    assert car_diesel.activitycode2.code == "A"

    assert lorry_diesel.activitycode1.code == "1.3.2"
    assert lorry_diesel.activitycode2.code == "A"


def test_import_roadclasses(code_sets, get_data_file):
    """test importing roadclasses."""
    assert RoadClass.objects.all().count() == 0
    code_set1, code_set2 = code_sets[:2]

    vehiclefile = get_data_file("vehicles.csv")
    vehiclesettings = get_yaml_data("vehicles.yaml")
    import_vehicles(vehiclefile, vehiclesettings, 2019, unit="kg/m", encoding="utf-8")

    roadclassfile = get_data_file("roadclasses.csv")
    roadclass_settings = get_yaml_data("roadclasses.yaml")
    import_roadclasses(roadclassfile, roadclass_settings, encoding="utf-8")

    assert RoadClass.objects.all().count() == 2
    # set more asserts now that roadclasstree removed
    # assert rc_tree["attribute"] == "roadtype"
    # assert "motorway" in rc_tree["values"]
    # assert rc_tree["values"]["motorway"]["attribute"] == "speed"
    # assert "90" in rc_tree["values"]["motorway"]["values"]
    # assert "primary road" in rc_tree["values"]
    # assert rc_tree["values"]["primary road"]["attribute"] == "speed"
    # assert "70" in rc_tree["values"]["primary road"]["values"]

    # test overwrite
    import_roadclasses(
        roadclassfile,
        roadclass_settings,
        encoding="utf-8",
        overwrite=True,
    )
    assert RoadClass.objects.all().count() == 2


def test_import_roadclasses_1attr(db, get_data_file):
    vehiclefile = get_data_file("vehicles.csv")
    vehiclesettings = get_yaml_data("vehicles.yaml")
    import_vehicles(vehiclefile, vehiclesettings, 2019, unit="kg/m", encoding="utf-8")

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
