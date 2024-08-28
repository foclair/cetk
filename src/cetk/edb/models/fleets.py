"""Database models to describe road fleets."""

import itertools

from django.db import models
from django.db.models import Q

from cetk.edb.const import CHAR_FIELD_LENGTH

from .road_models import Vehicle, VehicleFuel, VehicleFuelComb


class FleetManager(models.Manager):
    """Custom database manager for the Fleet model."""

    use_in_migrations = True

    def bulk_create_from_dicts(self, data):
        vehicles = {v.name: v for v in Vehicle.objects.all()}
        fuels = {f.name: f for f in VehicleFuel.objects.all()}
        validcombinations = {
            (vfc.vehicle.name, vfc.fuel.name)
            for vfc in VehicleFuelComb.objects.select_related("vehicle", "fuel")
        }
        for f in data:
            for m in f["members"]:
                for fu in m["fuels"]:
                    # breakpoint()
                    if (m["vehicle"], fu["fuel"]) not in validcombinations:
                        raise ValueError(
                            f"{m['vehicle']}/{fu['fuel']} is not a valid vehicle/fuel"
                            + " combination"
                        )

        fleets = [
            self.model(
                name=f["name"],
                default_heavy_vehicle_share=f["default_heavy_vehicle_share"],
                tags=f.get("tags", {}),
            )
            for f in data
        ]
        self.model.objects.bulk_create(fleets)
        fleets = self.model.objects.all()

        membermodel = self.model._meta.get_field("vehicles").related_model
        members = [
            membermodel(
                fraction=m["fraction"],
                coldstart_fraction=m.get("coldstart_fraction", 0),
                vehicle=vehicles[m["vehicle"]],
                timevar=m["timevar"],
                coldstart_timevar=m.get("coldstart_timevar"),
                fleet=fleet,
            )
            for fleet, f in zip(fleets, data)
            for m in f["members"]
        ]
        membermodel.objects.bulk_create(members)
        members = membermodel.objects.all()

        memberfuelmodel = membermodel._meta.get_field("fuels").related_model
        memberfuels = [
            memberfuelmodel(
                fraction=fu["fraction"], fuel=fuels[fu["fuel"]], fleet_member=member
            )
            for member, m in zip(
                members, itertools.chain.from_iterable(f["members"] for f in data)
            )
            for fu in m["fuels"]
        ]
        memberfuelmodel.objects.bulk_create(memberfuels)

        return fleets


class Fleet(models.Model):
    """A composition of vehicles."""

    name = models.CharField(max_length=CHAR_FIELD_LENGTH, unique=True)
    default_heavy_vehicle_share = models.FloatField()
    tags = models.JSONField(blank=True, default=dict)

    objects = FleetManager()

    class Meta:
        default_related_name = "fleets"
        constraints = [
            models.CheckConstraint(
                check=Q(default_heavy_vehicle_share__range=(0, 1)),
                name="fleet_default_heavy_vehicle_share_between_0_and_1",
            ),
        ]

    def __str__(self):
        """Unicode representation of fleet."""
        return self.name

    @property
    def default_light_vehicle_share(self):
        """Default share of light vehicles in fleet."""
        return 1 - self.default_heavy_vehicle_share


class FleetMember(models.Model):
    """A member vehicle of a fleet."""

    # share represented by vehicle (sums to 1.0 for the fleet)
    fraction = models.FloatField(default=0.0)
    coldstart_fraction = models.FloatField(default=0.0)
    vehicle = models.ForeignKey("Vehicle", on_delete=models.PROTECT, related_name="+")
    timevar = models.ForeignKey(
        "FlowTimevar",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    coldstart_timevar = models.ForeignKey(
        "ColdstartTimevar",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    fleet = models.ForeignKey(Fleet, on_delete=models.CASCADE, related_name="vehicles")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("fleet", "vehicle"), name="fleetmember_unique_vehicle_in_fleet"
            ),
        ]

    def __str__(self):
        """Unicode representation of fleet member vehicle."""
        return self.vehicle.name


class FleetMemberFuel(models.Model):
    """A fuel used by a fleet member."""

    # share of fleet member represented by fuel (sums to 1.0 for fleet member)
    fraction = models.FloatField(default=0.0)
    fuel = models.ForeignKey("VehicleFuel", on_delete=models.PROTECT, related_name="+")
    fleet_member = models.ForeignKey(
        FleetMember, on_delete=models.CASCADE, related_name="fuels"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("fleet_member", "fuel"),
                name="fleetmemberfuel_unique_fuel_in_fleetmember",
            ),
        ]

    def __str__(self):
        """Unicode representation of fleet member fuel."""
        return self.fuel.name
