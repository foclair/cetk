"""Unit and regression tests for the EDB app's fleet models."""

import pytest
from pytest_django.asserts import assertNumQueries

from cetk.edb.models import Fleet, Vehicle, VehicleFuel, VehicleFuelComb


@pytest.fixture
def inventory(db):
    Vehicle.objects.bulk_create(
        [
            Vehicle(name="car", isheavy=False),
            Vehicle(name="truck", isheavy=True),
            Vehicle(name="bus", isheavy=True),
        ]
    )
    car = Vehicle.objects.get(name="car")
    truck = Vehicle.objects.get(name="truck")
    bus = Vehicle.objects.get(name="bus")
    # Vehicle.save
    VehicleFuel.objects.bulk_create(
        [
            VehicleFuel(name="petrol"),
            VehicleFuel(name="CNG"),
            VehicleFuel(name="diesel"),
        ]
    )
    petrol = VehicleFuel.objects.get(name="petrol")
    cng = VehicleFuel.objects.get(name="CNG")
    diesel = VehicleFuel.objects.get(name="diesel")
    # VehicleFuel.save
    VehicleFuelComb.objects.bulk_create(
        [
            VehicleFuelComb(vehicle=car, fuel=petrol),
            VehicleFuelComb(vehicle=car, fuel=diesel),
            VehicleFuelComb(vehicle=truck, fuel=diesel),
            VehicleFuelComb(vehicle=bus, fuel=cng),
        ]
    )
    return inventory


class TestFleet:
    @pytest.fixture
    def fleetdata(self, test_flowtimevar, test_coldstarttimevar):
        # TODO now two identical timevars, check gadgets timevar in ifactory
        timevar1 = test_flowtimevar
        timevar2 = test_flowtimevar
        coldstart_timevar = test_coldstarttimevar
        return [
            {
                "name": "my fleet",
                "default_heavy_vehicle_share": 0.05,
                "tags": {"tag_key": "tag_value"},
                "members": [
                    {
                        "fraction": 1,
                        "coldstart_fraction": 0.1,
                        "vehicle": "car",
                        "timevar": timevar1,
                        "coldstart_timevar": coldstart_timevar,
                        "fuels": [
                            {"fraction": 0.8, "fuel": "petrol"},
                            {"fraction": 0.2, "fuel": "diesel"},
                        ],
                    },
                    {
                        "fraction": 0.7,
                        "vehicle": "truck",
                        "timevar": timevar2,
                        "fuels": [{"fraction": 1, "fuel": "diesel"}],
                    },
                    {
                        "fraction": 0.3,
                        "vehicle": "bus",
                        "timevar": timevar2,
                        "fuels": [{"fraction": 1, "fuel": "CNG"}],
                    },
                ],
            },
            {
                "name": "empty fleet",
                "default_heavy_vehicle_share": 0,
                "members": [],
            },
        ]

    def test_bulk_create_from_dicts(self, inventory, fleetdata):
        inv1 = inventory  # noqa
        with assertNumQueries(8):
            # 1 get vehicles, 1 get fuels, 1 get vehicle/fuel combs,
            # 1 create fleets, 1 create fleet members, 1 create fleet member fuels
            # 2 extra to avoid error unsaved related object fleet(_member)
            Fleet.objects.bulk_create_from_dicts(fleetdata)
        fleets = Fleet.objects.all()
        assert len(fleets) == 2
        for fleet, data in zip(fleets, fleetdata):
            assert fleet.name == data["name"]
            assert (
                fleet.default_heavy_vehicle_share == data["default_heavy_vehicle_share"]
            )
            assert fleet.tags == data.get("tags", {})
            members = fleet.vehicles.order_by("-fraction")
            assert len(members) == len(data["members"])
            for member, memberdata in zip(members, data["members"]):
                assert member.fraction == memberdata["fraction"]
                assert member.coldstart_fraction == memberdata.get(
                    "coldstart_fraction", 0
                )
                assert member.vehicle.name == memberdata["vehicle"]
                assert member.timevar == memberdata["timevar"]
                assert member.coldstart_timevar == memberdata.get("coldstart_timevar")
                fuels = member.fuels.order_by("-fraction")
                assert len(fuels) == len(memberdata["fuels"])
                for fuel, fueldata in zip(fuels, memberdata["fuels"]):
                    assert fuel.fraction == fueldata["fraction"]
                    assert fuel.fuel.name == fueldata["fuel"]

    def test_bulk_create_from_dicts_with_invalid_vehicle_fuel_comb(
        self, inventory, fleetdata
    ):
        fleetdata[0]["members"][0]["fuels"][0]["fuel"] = "CNG"
        with pytest.raises(ValueError, match="not a valid vehicle/fuel combination"):
            Fleet.objects.bulk_create_from_dicts(fleetdata)
