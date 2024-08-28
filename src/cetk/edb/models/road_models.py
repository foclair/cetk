"""Database models related to road-traffic."""

import ast
from itertools import groupby

import numpy as np
import pandas as pd
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from cetk.edb.const import CHAR_FIELD_LENGTH, CODE_FIELD_LENGTH, WGS84_SRID

from .common_models import Settings, Substance
from .source_models import SourceBase
from .timevar_models import FlowTimevar

# FlowTimeVar in fleets.py, import from there?


VELOCITY_CHOICES = list(range(20, 150, 10))


class RoadClassValidationError(Exception):
    pass


def default_congestion_profile_data():
    return str(24 * [7 * [1]])


class CongestionProfile(models.Model):
    """A level of service time profile."""

    class LevelOfService(models.IntegerChoices):
        FREEFLOW = 1, _("freeflow")
        HEAVY = 2, _("heavy")
        SATURATED = 3, _("saturated")
        STOPNGO = 4, _("stopngo")

    name = models.CharField(
        verbose_name="name of congestion profile",
        max_length=CHAR_FIELD_LENGTH,
        unique=True,
    )
    # traffic_condition: a 2d-field representing level of service
    # typical conditions given for a typeweek
    # hours are rows and days are columns

    traffic_condition = models.CharField(
        max_length=CODE_FIELD_LENGTH,
        default=default_congestion_profile_data,
    )

    class Meta:
        default_related_name = "congestion_profiles"

    def __str__(self):
        return self.name

    def get_fractions(self, timevar):
        """Return the fraction of each condition.
        args:
           timevar: time-variation to estimate fractions for
        """

        cond = np.array(ast.literal_eval(self.traffic_condition))
        flow = np.array(ast.literal_eval(timevar.typeday))
        flow_sum = flow.sum()
        return {
            los.name.lower(): np.where(cond == los, flow, 0).sum() / flow_sum
            for los in self.LevelOfService
        }

    def to_series(self, time_index, timezone=None):
        if timezone is None:
            timezone = Settings.get_current().timezone
        traffic_condition = np.array(ast.literal_eval(self.traffic_condition))
        local_time_index = time_index.tz_convert(timezone)
        return pd.Series(
            traffic_condition[local_time_index.hour, local_time_index.weekday],
            index=time_index,
        )


class TrafficSituation(models.Model):
    """A traffic situation."""

    ts_id = models.CharField(
        max_length=CODE_FIELD_LENGTH, verbose_name="traffic situation id", unique=True
    )

    class Meta:
        default_related_name = "traffic_situations"


class VehicleEF(models.Model):
    """An emission factor for a vehicle on a specific roadclass."""

    # note! emission factors for vehicle exhaust are stored in si-units kg/(veh*m)
    freeflow = models.FloatField(default=0)
    heavy = models.FloatField(default=0)
    saturated = models.FloatField(default=0)
    stopngo = models.FloatField(default=0)
    coldstart = models.FloatField(default=0)
    traffic_situation = models.ForeignKey(TrafficSituation, on_delete=models.PROTECT)
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT, related_name="+")
    vehicle = models.ForeignKey("Vehicle", on_delete=models.PROTECT)
    fuel = models.ForeignKey("VehicleFuel", on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("vehicle", "fuel", "substance", "traffic_situation"),
                name="vehicleef_unique_in_efset",
            ),
        ]
        default_related_name = "emissionfactors"
        verbose_name_plural = "Vehicle emission factors"


class Vehicle(models.Model):
    """A vehicle."""

    name = models.CharField(max_length=CHAR_FIELD_LENGTH, unique=True)
    info = models.CharField(max_length=CHAR_FIELD_LENGTH, null=True, blank=True)
    isheavy = models.BooleanField(default=False)
    max_speed = models.IntegerField(
        null=True,
        blank=True,
        default=130,
        choices=((s, f"{s}") for s in VELOCITY_CHOICES),
    )

    class Meta:
        default_related_name = "vehicles"

    def __str__(self):
        """Unicode representation of vehicle."""
        return self.name


class VehicleFuel(models.Model):
    """A vehicle fuel or energy source."""

    name = models.CharField(max_length=CHAR_FIELD_LENGTH, unique=True)

    class Meta:
        default_related_name = "vehicle_fuels"

    def __str__(self):
        return self.name


class VehicleFuelComb(models.Model):
    """A valid combination of fuel and vehicle."""

    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    fuel = models.ForeignKey(VehicleFuel, on_delete=models.PROTECT)
    activitycode1 = models.ForeignKey(
        "ActivityCode",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    activitycode2 = models.ForeignKey(
        "ActivityCode",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    activitycode3 = models.ForeignKey(
        "ActivityCode",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("vehicle", "fuel"),
                name="vehiclefuelcomb_vehicle_fuel_unique_together",
            ),
        ]
        default_related_name = "vehiclefuelcombs"
        indexes = [
            models.Index(fields=("vehicle", "fuel")),
        ]


class RoadSource(SourceBase):
    """A road source."""

    sourcetype = "road"

    aadt = models.IntegerField("Annual average day traffic", default=0)
    nolanes = models.IntegerField("Number of lanes", default=2)
    SPEED_CHOICES = [(v, str(v)) for v in range(20, 150, 10)]
    speed = models.IntegerField(
        "Road sign speed [km/h]", default=70, choices=SPEED_CHOICES
    )
    width = models.FloatField("Road width [meters]", default=20.0)
    median_strip_width = models.FloatField(default=0)
    slope = models.IntegerField(
        "Slope [°]", default=0, choices=((s, f"{s}") for s in range(-10, 10))
    )
    heavy_vehicle_share = models.FloatField(null=True, blank=True)
    geom = models.LineStringField(
        "the road coordinates", srid=WGS84_SRID, geography=True, db_index=True
    )
    roadclass = models.ForeignKey(
        "RoadClass", on_delete=models.PROTECT, related_name="+"
    )
    fleet = models.ForeignKey(
        "Fleet", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    congestion_profile = models.ForeignKey(
        CongestionProfile,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        default_related_name = "roadsources"
        constraints = [
            models.CheckConstraint(check=Q(aadt__gte=0), name="road_source_aadt_gte_0"),
            models.CheckConstraint(
                check=Q(nolanes__gt=0), name="road_source_nolanes_gt_0"
            ),
            models.CheckConstraint(check=Q(width__gt=0), name="road_source_width_gt_0"),
            models.CheckConstraint(
                check=(
                    Q(median_strip_width__gte=0) & Q(median_strip_width__lt=F("width"))
                ),
                name="road_source_median_strip_width_between_0_and_width",
            ),
            models.CheckConstraint(
                check=Q(heavy_vehicle_share__range=(0, 1)),
                name="road_source_heavy_vehicle_share_between_0_and_1",
            ),
        ]

    @property
    def light_vehicle_share(self):
        if self.heavy_vehicle_share is None:
            return None
        return 1 - self.heavy_vehicle_share

    @property
    def drivable_width(self):
        return self.width - self.median_strip_width

    def get_heavy_vehicle_share(self):
        if self.heavy_vehicle_share is None:
            return self.fleet.default_heavy_vehicle_share
        return self.heavy_vehicle_share

    def get_segments(self, rel_dist, *, polar=True):
        """Get segments for a road given a normalized distribution.

        args:
            rel_dist: sequence of relative receptor distances

        returns:
            tuple: (center_point_of_segment, orientation)
        """
        srid = Settings.get_current().srid
        geom = self.geom.transform(srid, clone=True)
        # calculate absolute distribution along road
        dist = np.array(rel_dist) * geom.length
        # create an array of nodes with any consecutive duplicates removed
        nodes = np.array([k for k, g in groupby(geom.coords)])
        # create cross sections along road
        node_dist = np.zeros(nodes.shape[0])

        i = 0  # index for road node
        j = 0  # index for distance along road
        for p2 in nodes[1:]:
            p1 = nodes[i, :]
            seg = p2 - p1  # segment vector
            seg_length = np.linalg.norm(seg)
            seg_dir = seg / seg_length  # normalized segment direction
            node_dist[i + 1] = node_dist[i] + seg_length  # node dist
            while j < len(dist) and dist[j] <= node_dist[i + 1]:
                coords = p1 + seg_dir * (dist[j] - node_dist[i])
                if polar:
                    seg_dir_degrees = 90 - np.degrees(
                        np.arctan2(seg_dir[1], seg_dir[0])
                    )
                    if seg_dir_degrees < 0:
                        seg_dir_degrees += 360
                    yield (
                        Point(*coords, srid=srid).transform(4326, clone=True),
                        seg_dir_degrees,
                    )
                else:
                    yield (p1, p2)
                j += 1
            i += 1

    def emission(  # noqa: C901, PLR0912
        self,
        *,
        by_vehicle=True,
        substance=None,
        ac1=None,
        ac2=None,
        ac3=None,
    ):
        """Calculate emission for a roadsource.

        Default is to calculate emissions for all substances and vehicles

        optional:
            substance: only calculate emissions for this substance
            by_vehicle: If False, sum of emissions for all vehicles is returned
            ac1: a list of activitycode instances
            ac2: a list of activitycode instances
            ac3: a list of activitycode instances
        """

        vehicle_fuel_combs = {}
        for rec in VehicleFuelComb.objects.all():
            vehicle_fuel_combs[(rec.vehicle_id, rec.fuel_id)] = (
                rec.activitycode1,
                rec.activitycode2,
                rec.activitycode3,
            )
        srid = Settings.get_current().srid
        emis_by_veh_and_subst = {}
        for fleet_member in self.fleet.vehicles.all():
            veh = fleet_member.vehicle
            if self.congestion_profile is None:
                conditions = {
                    "freeflow": 1.0,
                    "heavy": 0.0,
                    "saturated": 0.0,
                    "stopngo": 0.0,
                }
            else:
                timevar = fleet_member.timevar or FlowTimevar()
                conditions = self.congestion_profile.get_fractions(timevar)

            for fleet_member_fuel in fleet_member.fuels.all():
                try:
                    activitycodes = vehicle_fuel_combs[
                        (veh.id, fleet_member_fuel.fuel_id)
                    ]
                except KeyError:
                    # if vehicle fuel combination is not valid
                    # no emissions are calculated
                    continue

                # Check if activity codes matches code filters
                # if not, the vehicle-fuel combination is excluded
                for ac, ac_filter in zip(activitycodes, (ac1, ac2, ac3)):
                    if ac_filter is not None and (
                        ac is None or not ac.matches(ac_filter)
                    ):
                        continue

                efs = self.roadclass.traffic_situation.emissionfactors.filter(
                    vehicle=veh,
                    fuel=fleet_member_fuel.fuel,
                )
                if substance is not None:
                    efs = efs.filter(substance=substance)
                for ef in efs:
                    heavy_share = (
                        self.heavy_vehicle_share
                        or self.fleet.default_heavy_vehicle_share
                    )
                    fleet_share = heavy_share if veh.isheavy else 1 - heavy_share

                    emis = (
                        self.aadt
                        * fleet_share
                        * fleet_member.fraction
                        * fleet_member_fuel.fraction
                        * self.geom.transform(  # annual average day vehicle flow
                            srid, clone=True
                        ).length
                        * (
                            ef.coldstart * fleet_member.coldstart_fraction
                            + ef.freeflow * conditions["freeflow"]
                            + ef.heavy * conditions["heavy"]
                            + ef.saturated * conditions["saturated"]
                            + ef.stopngo * conditions["stopngo"]
                        )
                        / (3600 * 24)  # convert day⁻¹ to s⁻¹
                    )
                    if veh not in emis_by_veh_and_subst:
                        emis_by_veh_and_subst[veh] = {}
                    if ef.substance not in emis_by_veh_and_subst[veh]:
                        emis_by_veh_and_subst[veh][ef.substance] = emis
                    else:
                        emis_by_veh_and_subst[veh][ef.substance] += emis

        if by_vehicle is False:
            agg_emis = {}
            for substances in emis_by_veh_and_subst.values():
                for subst, emis in substances.items():
                    agg_emis[subst] = agg_emis.get(subst, 0) + emis
            return agg_emis

        return emis_by_veh_and_subst
