import copy
import logging
from collections import OrderedDict
from operator import itemgetter
from pathlib import Path

import numpy as np  # noqa
import pandas as pd
from django.contrib.gis.gdal import (  # noqa
    AxisOrder,
    CoordTransform,
    DataSource,
    SpatialReference,
)
from django.contrib.gis.geos import Point, Polygon  # noqa
from django.core.exceptions import ObjectDoesNotExist, ValidationError  # noqa
from django.core.management.base import CommandError  # noqa
from django.db import IntegrityError  # noqa

from etk.edb.const import WGS84_SRID
from etk.edb.models import (  # noqa
    CodeSet,
    ColdstartTimevar,
    CongestionProfile,
    Fleet,
    FleetMemberFuel,
    FlowTimevar,
    PrefetchRoadClassAttributes,
    RoadAttribute,
    RoadClass,
    RoadSource,
    Substance,
    Timevar,
    TrafficSituation,
    Vehicle,
    VehicleEF,
    VehicleFuel,
    VehicleFuelComb,
    get_valid_road_attribute_values,
)
from etk.edb.units import emission_unit_to_si, vehicle_ef_unit_to_si  # noqa
from etk.utils import inbatch

log = logging.getLogger(__name__)


STATIC_ROAD_ATTRIBUTES = [
    "aadt",
    "nolanes",
    "name",
    "speed",
    "width",
    "median_strip_width",
    "heavy_vehicle_share",
    "slope",
]


def handle_msg(messages, msg, *, fail_early=False):
    """handle repeated error without bloating stderr/stdout.

    args
        messages: dict where messages are accumulated
        msg: message string
        fail_early: exit directly
    """

    if fail_early:
        raise ImportError(msg)

    if msg not in messages:
        log.debug(f"debug: {msg}")
        messages[msg] = 1
    else:
        messages[msg] += 1


def filter_out(feature, exclude):
    """filter roads by attribute."""

    for attr_name, val in exclude.items():
        if isinstance(val, (str, int, float)):
            if feature.get(attr_name) != val:
                return False
        elif str(feature.get(attr_name)) not in list(val):
            return False
    return True


def import_vehicles(  # noqa: C901, PLR0912, PLR0915
    vehicles_file,
    config,
    year,
    *,
    only_ef=False,
    overwrite=False,
    unit="mg/km",
    encoding="utf-8",
):
    """Import vehicles, fuels and traffic situations to ef-set.

    args
        vehicles_file: a csv-file with vehicles and emission-factors
        config: a dict with definitions of vehicle, fuels and codes
        year: filter emission-factors to load by year

    optional
        only_ef: if True, only load emission factors - do not modify base-set tables
        overwrite: if True, existing instances will be ovewritten
        unit: unit of emission-factors to import, default is "mg/km"
    """

    # cache valid activity codes
    valid_codes = OrderedDict()
    code_sets = [None, None, None]
    config = copy.deepcopy(config)

    # cache activity-codes for code-sets specified in config file
    for i in range(3):
        code_nr = i + 1
        code_sets[i] = config.pop(f"code_set{code_nr}", None)

        if code_sets[i] is not None:
            try:
                code_sets[i] = CodeSet.objects.get(slug=code_sets[i])
            except ObjectDoesNotExist:
                raise ImportError(f"Invalid codeset slug: {code_sets[i]}")

            valid_codes[code_sets[i].slug] = {
                ac.code: ac for ac in code_sets[i].codes.all()
            }

    def validate_ac(code_data, valid_codes):
        if "activitycode1" in code_data and len(valid_codes) == 0:
            raise ImportError("no activity codes defined, but codes given for vehicle")

        code_nr = 1
        for code_set_name, codes in valid_codes.items():
            try:
                ac = code_data[f"activitycode{code_nr}"]
            except KeyError:
                raise ImportError(
                    f"no value specified for activity code {code_nr} ({code_set_name})"
                    f" of vehicle/fuel combination '{vehicle_name}' - '{fuel_name}'"
                )
            if ac not in codes:
                raise ImportError(
                    f"invalid value '{ac}' for activity code "
                    f"{code_nr} ({code_set_name})"
                    f" of vehicle/fuel combination '{vehicle_name}' - '{fuel_name}'"
                )
            code_nr += 1

    try:
        mass_unit, length_unit = unit.split("/")
    except ValueError:
        log.error(f"invalid emission-factor unit {unit} specified in config-file")
        raise
    log.info(f"emission factor units is: {unit}")

    messages = {}
    with Path(vehicles_file).open(encoding=encoding) as veh_file:
        log.info("reading emission-factor table")
        df = pd.read_csv(
            veh_file,
            sep=";",
            dtype={
                "year": int,
                "vehicle": str,
                "fuel": str,
                "traffic_situation": str,
                "substance": str,
                "freeflow": float,
                "heavy": float,
                "saturated": float,
                "stopngo": float,
                "coldstart": float,
            },
        )
        # indexes are set after reading csv in order to allow
        # specification of dtypes for index columns
        try:
            df = df.set_index(
                ["year", "vehicle", "fuel", "traffic_situation", "substance"]
            )
        except KeyError as err:
            raise ImportError(f"Invalid csv-file: {err}")
        try:
            df = df.loc[year]
        except KeyError:
            raise ImportError(f"year {year} not found in emission factor csv-file")

        if df.size == 0:
            raise ImportError(f"no emission factors found for year {year}")

        for col in ("freeflow", "heavy", "saturated", "stopngo", "coldstart"):
            if col not in df.columns:
                raise ImportError(
                    f"Required column '{col}' not found in file '{vehicles_file}"
                )

        log.debug("checking that all substance exist in the database")
        substances = {}
        for subst in df.index.get_level_values(3).unique():
            try:
                substances[subst] = Substance.objects.get(slug=subst)
            except ObjectDoesNotExist:
                msg = f"substance {subst} does not exist in database"
                raise ImportError(msg)

        # create vehicles
        vehicle_defs = config.get("vehicles", [])
        if len(vehicle_defs) > 0:
            log.debug("processing vehicles")
        df_vehicles = df.index.get_level_values(0).unique()
        for veh in vehicle_defs:
            veh_tmp = copy.deepcopy(veh)
            fuel_defs = veh_tmp.pop("fuels", {})
            try:
                vehicle_name = veh_tmp.pop("name")
                if overwrite and not only_ef:
                    (_, created,) = Vehicle.objects.update_or_create(
                        name=vehicle_name, defaults=veh_tmp
                    )
                    if created:
                        log.debug(f"created vehicle {vehicle_name}")
                elif not only_ef:
                    try:
                        (_, created) = Vehicle.objects.get_or_create(
                            name=vehicle_name, defaults=veh_tmp
                        )
                    except IntegrityError:
                        raise ImportError(
                            "either duplicate specification or vehicle "
                            f"'{vehicle_name}' already exists."
                        )
                    if created:
                        log.debug(f"created vehicle {vehicle_name}")
                elif not Vehicle.objects.filter(name=vehicle_name).exists():
                    raise ImportError(  # noqa: TRY301
                        f"vehicle '{vehicle_name}' does not exist "
                    )
            except Exception as err:
                raise ImportError(
                    f"invalid specification of vehicle in config-file: {err}"
                )
            if vehicle_name not in df_vehicles:
                log.warning(
                    "warning: no emission-factors specified for vehicle"
                    f" '{vehicle_name}'"
                )

            vehicles = {veh.name: veh for veh in Vehicle.objects.all()}

            for fuel_name, code_data in fuel_defs.items():
                # fuel model only has a name, so overwrite/updating is not relevant

                if not only_ef:
                    # allow modification of base-set tables
                    fuel, _ = VehicleFuel.objects.get_or_create(name=fuel_name)
                else:
                    # only verify that fuel exist
                    try:
                        fuel = VehicleFuel.objects.get(name=fuel_name)
                    except ObjectDoesNotExist:
                        raise ImportError(
                            f"fuel {fuel_name} does not exist in database"
                        )
                validate_ac(code_data, valid_codes)

                # get activity code model instances for each activity code
                ac_codes = [None, None, None]
                for i in range(3):
                    code_nr = i + 1
                    ac_codes[i] = code_data.get(f"activitycode{code_nr}", None)
                    if ac_codes[i] is not None:
                        ac_codes[i] = valid_codes[code_sets[i].slug][ac_codes[i]]
                    else:
                        ac_codes[i] = None

                if overwrite and not only_ef:
                    _, created = VehicleFuelComb.objects.update_or_create(
                        vehicle=vehicles[vehicle_name],
                        fuel=fuel,
                        defaults={
                            "activitycode1": ac_codes[0],
                            "activitycode2": ac_codes[1],
                            "activitycode3": ac_codes[2],
                        },
                    )
                    if created:
                        log.debug(
                            "created vehicle-fuel combination "
                            f"'{vehicle_name}' - '{fuel_name}'"
                        )

                elif not only_ef:
                    VehicleFuelComb.objects.get_or_create(
                        vehicle=vehicles[vehicle_name],
                        fuel=fuel,
                        defaults={
                            "activitycode1": ac_codes[0],
                            "activitycode2": ac_codes[1],
                            "activitycode3": ac_codes[2],
                        },
                    )
                elif not VehicleFuelComb.objects.filter(
                    vehicle=vehicles[vehicle_name], fuel=fuel
                ).exists():
                    raise ImportError(
                        "vehicle/fuel combination "
                        f"'{vehicle_name}' - '{fuel_name}' "
                        "does not exist."
                    )
        fuels = {fuel.name: fuel for fuel in VehicleFuel.objects.all()}
        veh_fuel_combs = {
            (comb.vehicle.name, comb.fuel.name)
            for comb in VehicleFuelComb.objects.all().select_related("vehicle", "fuel")
        }

    # check that all combinations of vehicle/fuel in ef-table exist in db
    for vehicle_name, fuel_name in {row[:2] for row in df.index}:
        if not VehicleFuelComb.objects.filter(
            fuel__name=fuel_name, vehicle__name=vehicle_name
        ).exists():
            msg = (
                f"emission-factors for undefined vehicle/fuel combination "
                f"'{vehicle_name}' - '{fuel_name}' will not be loaded."
            )
            if msg not in messages:
                messages[msg] = 1
            else:
                messages[msg] += 1

    # create traffic situations
    log.debug("creating traffic-situations")
    existing_traffic_situations = {
        ts.ts_id: ts for ts in TrafficSituation.objects.all()
    }

    # check if there are any new traffic-situations in ef table
    traffic_situations = []
    for ts_id in df.index.get_level_values(2).unique():
        if ts_id not in existing_traffic_situations:
            # traffic-situations are defined by ts_id only
            # this means overwriting/updating is not relevant
            if only_ef:
                raise ImportError(f"traffic-situation {ts_id} does not exist.")
            traffic_situations.append(TrafficSituation(ts_id=ts_id))
    # create any new traffic-situations
    if len(traffic_situations) > 0:
        TrafficSituation.objects.bulk_create(traffic_situations)

    # update look-up dict for traffic-situations
    updated_traffic_situations = {ts.ts_id: ts for ts in TrafficSituation.objects.all()}

    # create/update all vehicle emission factors
    log.debug("creating/updating emission factors")

    # get all pre-existing emission factors in ef-set
    # store in dict with (veh, fuel, ts, subst) as keys
    # and instance id as values
    existing_ef_keys = {
        vals[1:]: vals[0]
        for vals in VehicleEF.objects.all().values_list(
            "id",
            "vehicle__name",
            "fuel__name",
            "traffic_situation__ts_id",
            "substance__slug",
        )
    }

    efs_to_create = []
    efs_to_update = []
    for index, row in df.iterrows():
        vehicle_name, fuel_name, ts_id, subst_slug = index
        valid_ef = True

        # check if ef already exists
        key = (vehicle_name, fuel_name, ts_id, subst_slug)
        traffic_situation = updated_traffic_situations[ts_id]

        try:
            vehicle = vehicles[vehicle_name]
        except KeyError:
            msg = f"undefined vehicle '{vehicle_name}' found in emission factor table"
            valid_ef = False

        try:
            fuel = fuels[fuel_name]
        except KeyError:
            msg = f"undefined fuel '{fuel_name}' found in emission factor table"
            valid_ef = False

        if (vehicle_name, fuel_name) not in veh_fuel_combs:
            msg = (
                f"emission-factors for undefined vehicle/fuel combination "
                f"'{vehicle_name}' - '{fuel_name}' will not be loaded."
            )
            valid_ef = False

        if not valid_ef:
            if msg not in messages:
                messages[msg] = 1
            else:
                messages[msg] += 1
            continue

        substance = substances[subst_slug]

        def get_ef(val):
            if pd.isna(val):
                return 0
            return vehicle_ef_unit_to_si(val, mass_unit, length_unit)

        if key in existing_ef_keys:
            efs_to_update.append(
                VehicleEF(
                    id=existing_ef_keys[key],
                    traffic_situation=traffic_situation,
                    substance=substance,
                    vehicle=vehicle,
                    fuel=fuel,
                    freeflow=get_ef(row.freeflow),
                    heavy=get_ef(row.heavy),
                    saturated=get_ef(row.saturated),
                    stopngo=get_ef(row.stopngo),
                    coldstart=get_ef(row.coldstart),
                )
            )
        else:
            efs_to_create.append(
                VehicleEF(
                    traffic_situation=traffic_situation,
                    substance=substance,
                    vehicle=vehicle,
                    fuel=fuel,
                    freeflow=get_ef(row.freeflow),
                    heavy=get_ef(row.heavy),
                    saturated=get_ef(row.saturated),
                    stopngo=get_ef(row.stopngo),
                    coldstart=get_ef(row.coldstart),
                )
            )

    if not overwrite and len(efs_to_update) > 0:
        msg = "\n".join(
            (
                f"{ef.vehicle.name}, {ef.fuel.name}, "
                f"{ef.traffic_situation.ts_id}, {ef.substance.slug}"
            )
            for ef in efs_to_update
        )
        raise ImportError(
            f"The following emission factors already exist in the ef-set: {msg}"
        )

    if len(efs_to_update) > 0:
        VehicleEF.objects.bulk_update(
            efs_to_update,
            ("freeflow", "heavy", "saturated", "stopngo", "coldstart"),
        )
        log.info(f"updated {len(efs_to_update)} emission-factors")
    for msg, nr in messages.items():
        log.warning("warning: " + msg + f": {nr}")

    try:
        VehicleEF.objects.bulk_create(efs_to_create)
        log.info(f"wrote {len(efs_to_create)} emission-factors")
    except IntegrityError:
        for ef in efs_to_create:
            try:
                ef.save()
            except IntegrityError:
                raise ImportError(
                    "duplicate emission-factors for: "
                    f"substance '{ef.substance.slug}, "
                    f"vehicle: '{ef.vehicle.name}', "
                    f"fuel:  '{ef.fuel.name}', "
                    f"traffic-situation: '{ef.traffic_situation.ts_id}'"
                )


def import_roadclasses(  # noqa: C901, PLR0912, PLR0915
    roadclass_file, config, *, overwrite=False, **kwargs
):
    """import roadclasses (traffic-situations must already exist in database)."""

    encoding = kwargs.get("encoding", "utf-8")
    try:
        attributes = config["attributes"]
    except KeyError:
        raise ImportError("keyword 'attributes' not found in config")

    log.info("create road attributes")

    # created objects are stored in a nested dict
    defined_attributes = OrderedDict()
    for ind, attr_dict in enumerate(attributes):
        attr_dict_tmp = copy.deepcopy(attr_dict)
        try:
            values = attr_dict_tmp.pop("values")
        except KeyError:
            raise ImportError("keyword 'values' not found for in config")

        try:
            attr, _ = RoadAttribute.objects.get_or_create(
                name=attr_dict_tmp["name"], slug=attr_dict_tmp["slug"], order=ind
            )
        except IntegrityError as err:
            raise ImportError(
                f"invalid or duplicate road class attribute: {attr_dict['name']}: {err}"
            )

        defined_attributes[attr] = {"attribute": attr}
        for val in values:
            defined_attributes[attr][val], _ = attr.values.get_or_create(value=val)
    valid_attributes = get_valid_road_attribute_values()
    for attr, values in valid_attributes.items():
        if attr not in defined_attributes:
            if overwrite:
                attr.delete()
            else:
                raise ImportError(
                    "Unused road attribute '{attr.slug}' found in base-set"
                )
        for label, value in values.items():
            if label not in defined_attributes[attr]:
                if overwrite:
                    value.delete()
                else:
                    raise ImportError(
                        "Unused road attribute value '{label}' found in base-set"
                    )

    # cache all existing traffic situations and road-classes
    traffic_situations = {ts.ts_id: ts for ts in TrafficSituation.objects.all()}

    existing_roadclasses = {
        tuple(rc.attributes.values()): rc.id
        for rc in RoadClass.objects.prefetch_related(PrefetchRoadClassAttributes())
    }

    log.info("reading roadclass table")
    with Path(roadclass_file).open(encoding=encoding) as roadclass_stream:
        roadclass_attributes = [a.slug for a in defined_attributes]
        column_names = [*roadclass_attributes, "traffic_situation"]
        try:
            df = pd.read_csv(
                roadclass_stream, sep=";", dtype=str, usecols=column_names
            ).set_index([a.slug for a in defined_attributes])
        except Exception as err:
            raise ImportError(
                "could not read csv, are all roadclass attributes "
                f"{roadclass_attributes} and 'traffic_situation' "
                f"given as columns? (error message: {err})"
            )

        invalid_traffic_situations = []
        roadclasses_to_create = []
        roadclasses_to_update = []
        row_nr = 0
        for index, row in df.iterrows():
            row_nr += 1
            attribute_values = OrderedDict()
            indexes = [index] if isinstance(index, str) else index
            for attr, val in zip(defined_attributes, indexes):
                if val not in defined_attributes[attr]:
                    raise ImportError(
                        f"Invalid value '{val}' for road attribute '{attr.slug}'"
                    )
                attribute_values[attr] = defined_attributes[attr][val]

            try:
                ts = traffic_situations[row.traffic_situation]
            except KeyError:
                invalid_traffic_situations.append(row.traffic_situation)
                continue
            rc = RoadClass(traffic_situation=ts)
            try:
                rc.id = existing_roadclasses[
                    tuple([v.value for v in attribute_values.values()])
                ]
                roadclasses_to_update.append((rc, attribute_values.values()))
            except KeyError:
                roadclasses_to_create.append((rc, attribute_values.values()))

        if len(invalid_traffic_situations) > 0:
            raise ImportError(
                "invalid traffic-situations:\n"
                + "\n  ".join(invalid_traffic_situations)
            )

        if len(roadclasses_to_update) > 0:
            for rc, attribute_values in roadclasses_to_update:
                if overwrite:
                    rc.save()
                    rc.attribute_values.set(attribute_values)
                else:
                    raise ImportError(f"roadclass '{rc}' already exists.")
        if len(roadclasses_to_create) > 0:
            # count=0
            RoadClass.objects.bulk_create(map(itemgetter(0), roadclasses_to_create))
            # count =2
            for rctuple in roadclasses_to_create:
                rctuple[0].save()
            # count=4, so something goes wrong here!
            # need to do assignment of roadclass in another way to make sure no problem
            # unsaved related bojects
            through_model = RoadClass.attribute_values.through
            # need to somehow redefine roadclasses_to_create without creating new ones
            # breakpoint()
            values = [
                through_model(roadclass=rc, roadattributevalue=v)
                for rc, vals in roadclasses_to_create
                for v in vals
            ]

            through_model.objects.bulk_create(values)


def import_congestion_profiles(profile_data, *, overwrite=False):
    """import congestion profiles."""

    # Profile instances must not be created by bulk_create as the save function
    # is overloaded to calculate the normation constant.
    def make_profiles(data):
        retdict = {}
        for name, timevar_data in data.items():
            try:
                traffic_condition = timevar_data["traffic_condition"]
                if overwrite:
                    newobj = CongestionProfile.objects.update_or_create(
                        name=name,
                        defaults={"traffic_condition": traffic_condition},
                    )
                else:
                    try:
                        newobj = CongestionProfile.objects.create(
                            name=name,
                            traffic_condition=traffic_condition,
                        )
                    except IntegrityError:
                        raise IntegrityError(
                            f"Congestion-profile {name} " f"already exist in inventory "
                        )
                retdict[name] = newobj
            except KeyError:
                raise ImportError(
                    f"Invalid specification of congestion-profile {name}"
                    f", is 'traffic_condition' specified?"
                )
        return retdict

    profiles = {}
    profiles["profiles"] = make_profiles(profile_data)
    return profiles


def import_fleets(data, *, overwrite=False):  # noqa: C901, PLR0912, PLR0915
    """import fleets

    args
        data: a dict with fleets

    optional
        overwrite: True means existing instances will be overwritten

    """

    existing_fuels = {fuel.name: fuel for fuel in VehicleFuel.objects.all()}
    existing_vehicles = {vehicle.name: vehicle for vehicle in Vehicle.objects.all()}
    existing_flow_timevars = {tvar.name: tvar for tvar in FlowTimevar.objects.all()}
    existing_coldstart_timevars = {
        tvar.name: tvar for tvar in ColdstartTimevar.objects.all()
    }

    fleets = {}
    for name, fleet_data in data.items():
        fleet_data_tmp = copy.deepcopy(fleet_data)
        try:
            members_data = fleet_data_tmp.pop("vehicles", [])
            default_heavy_vehicle_share = fleet_data_tmp["default_heavy_vehicle_share"]
        except KeyError:
            raise ImportError(
                f"no 'default_heavy_vehicle_share' specified for fleet '{name}'"
            )
        if overwrite:
            fleets[name], _ = Fleet.objects.update_or_create(
                name=name,
                defaults={
                    "default_heavy_vehicle_share": default_heavy_vehicle_share,
                },
            )
        else:
            try:
                fleets[name] = Fleet.objects.create(
                    name=name,
                    default_heavy_vehicle_share=default_heavy_vehicle_share,
                )
            except IntegrityError:
                raise ImportError(
                    f"either duplicate specification in file or "
                    f"fleet '{name}' already exist in inventory"
                )

        members = OrderedDict()
        heavy_member_sum = 0
        light_member_sum = 0
        for vehicle_name, member_data in members_data.items():
            fuels_data = member_data.pop("fuels", [])
            timevar_name = member_data.pop("timevar")
            coldstart_timevar_name = member_data.pop("coldstart_timevar")

            veh = existing_vehicles[vehicle_name]

            # accumulate member fractions to ensure they sum up to 1.0
            if veh.isheavy:
                heavy_member_sum += member_data["fraction"]
            else:
                light_member_sum += member_data["fraction"]

            if timevar_name is not None:
                try:
                    member_data["timevar"] = existing_flow_timevars[timevar_name]
                except KeyError:
                    raise ImportError(
                        f"timevar '{timevar_name}' specified for vehicle "
                        f"'{vehicle_name}' in fleet '{name}' does not "
                        f"exist in inventory"
                    )
            else:
                member_data["timevar"] = None

            if coldstart_timevar_name is not None:
                try:
                    member_data["coldstart_timevar"] = existing_coldstart_timevars[
                        coldstart_timevar_name
                    ]
                except KeyError:
                    raise ImportError(
                        f"coldstart timevar '{coldstart_timevar_name}' specified for "
                        f"vehicle '{vehicle_name}' "
                        f"in fleet '{name}' does not exist in inventory"
                    )
            else:
                member_data["coldstart_timevar"] = None

            try:
                if overwrite:
                    members[vehicle_name], new = fleets[name].vehicles.update_or_create(
                        vehicle=existing_vehicles[vehicle_name], defaults=member_data
                    )
                    # if updating fleet member, remove any old fleet member fuels
                    # this allows overwriting with fewer fuels than before
                    # and avoids remaining obsolete member fuels
                    if not new:
                        members[vehicle_name].fuels.all().delete()
                else:
                    try:
                        members[vehicle_name] = fleets[name].vehicles.create(
                            vehicle=existing_vehicles[vehicle_name], **member_data
                        )
                    except IntegrityError:
                        raise ImportError(
                            "Either duplicate specification of fleet member in"
                            "config-file, or fleet-member already exist in inventory"
                        )
            except (KeyError, TypeError):
                raise ImportError(
                    f"invalid specification of vehicle '{vehicle_name}' in "
                    f"fleet '{name}', must specify 'timevar' "
                    "'coldstart_timevar', fraction, 'coldstart_fraction' and 'fuels'"
                )

            fuel_sum = 0
            member_fuels = []
            if not isinstance(fuels_data, dict):
                raise ImportError(
                    f"invalid specification of fuels for '{vehicle_name}'"
                    f"in fleet '{name}', fuels should be specified as:\n"
                    f"fuels:\n  fuel1: 0.4\n  fuel2: 0.6"
                )
            for fuel_name, fuel_fraction in fuels_data.items():
                fuel_sum += fuel_fraction
                member_fuels.append(
                    FleetMemberFuel(
                        fuel=existing_fuels[fuel_name],
                        fleet_member=members[vehicle_name],
                        fraction=fuel_fraction,
                    )
                )
            if fuel_sum != 1.0:
                raise ImportError(
                    f"sum of fuel fractions does not sum up to 1.0 (sum={fuel_sum}) "
                    f"for '{vehicle_name}s' of fleet '{name}' in inventory "
                )
            FleetMemberFuel.objects.bulk_create(member_fuels)
        if heavy_member_sum > 0 and abs(heavy_member_sum - 1.0) >= 0.005:
            raise ImportError(
                f"sum of heavy fleet members does not sum up to 1.0 "
                f"(sum={heavy_member_sum}) "
                f"for fleet '{name}' in inventory "
            )
        if light_member_sum > 0 and abs(light_member_sum - 1.0) >= 0.005:
            raise ImportError(
                f"sum of light fleet members does not sum up to 1.0 "
                f"(sum={light_member_sum}) "
                f"for fleet '{name}' in inventory "
            )
    return len(fleets)


def import_roads(  # noqa: C901, PLR0912, PLR0915
    roadfile,
    config,
    exclude=None,
    only=None,
    chunksize=1000,
    progress_callback=None,
):
    """Import a road network."""

    datasource = DataSource(roadfile)

    layer = datasource[0]
    src_proj = SpatialReference(config["srid"]) if "srid" in config else layer.srs
    target_proj = SpatialReference(WGS84_SRID)
    trans = CoordTransform(src_proj, target_proj)

    # get attribute mappings from road input file to road-source fields
    # get dict of static attributes to read from road file
    attr_dict = {
        attr: config.get(attr) for attr in STATIC_ROAD_ATTRIBUTES if attr in config
    }

    defaults = config.pop("defaults", {})

    if "fleet" in config:
        # prefetch fleets and store in dict for quick lookups
        fleets = {fleet.name: fleet for fleet in Fleet.objects.all()}
    else:
        fleet_name = defaults.get("fleet", "default")
        default_fleet, created = Fleet.objects.get_or_create(
            name=fleet_name, defaults={"default_heavy_vehicle_share": 0.05}
        )
        if created:
            log.warning(
                "no entry for 'fleet' in road import config file"
                ", assigning an empty default fleet for all imported roads"
            )
        else:
            log.warning(
                f"assigning default fleet '{fleet_name}' for all imported roads"
            )

    # prefetch congestion profiles and store in dict for quick lookups
    congestion_profiles = {prof.name: prof for prof in CongestionProfile.objects.all()}
    default_congestion_profile_name = defaults.get("congestion_profile")
    default_congestion_profile = None
    if config.get("congestion_profile") is None:
        if default_congestion_profile_name is None:
            log.warning(
                "no field specified for 'congestion_profile' in road import config"
                " and no default specified"
                ", no congestion profile will be specified for imported roads"
            )
        else:
            log.warning(
                "no field specified  for 'congestion_profile' in road import config"
                f", default congestion profile '{default_congestion_profile_name}' "
                "will be used for all imported roads"
            )
            try:
                default_congestion_profile = congestion_profiles[
                    default_congestion_profile_name
                ]
            except KeyError:
                raise ImportError(
                    "default congestin profile "
                    f"'{default_congestion_profile_name}' does not exist"
                )

    valid_values = get_valid_road_attribute_values()
    # get valid roadclass attributes
    if "roadclass" in defaults:
        default_roadclass_attributes = {}
        for attr, values in valid_values.items():
            value = defaults["roadclass"][attr.slug]
            if attr.slug not in defaults["roadclass"]:
                raise ImportError(
                    f"incomplete default roadclass attribute mappings,"
                    f" missing '{attr.slug}'"
                )
            if value not in values:
                raise ImportError(
                    f"invalid roadclass attribute value {value} for"
                    f" attribute {attr.slug}"
                )
            default_roadclass_attributes[attr.slug] = value
    else:
        default_roadclass_attributes = {
            a.slug: a.values.first().value for a in valid_values
        }

    def generate_key(attribute_values, defined_attributes):
        return tuple([attribute_values[attr.slug] for attr in defined_attributes])

    roadclasses = {
        generate_key(rc.attributes, valid_values): rc
        for rc in RoadClass.objects.prefetch_related(
            PrefetchRoadClassAttributes()
        ).all()
    }
    if "roadclass" in config:
        # get attribute mappings for roadclass attributes
        roadclass_attr_dict = config["roadclass"]
        # prefetch roadclasses and store in dict for quick lookups
        for attr in valid_values:
            if attr.slug not in roadclass_attr_dict:
                raise ImportError(
                    f"incomplete roadclass attribute mappings, missing '{attr.slug}'"
                )
    else:
        log.warning(
            "no entry 'roadclass' found in config "
            "for road import, assigning a default roadclass to all imported roads"
        )
        roadclass_attr_dict = None

        # if no mappings are specified for roadclass attributes,
        # a default roadclass and traffic situation will be created

        default_ts, created = TrafficSituation.objects.get_or_create(ts_id="default")
        if created:
            log.warning(
                "a 'default' traffic situation is created fo the default roadclass"
            )
        try:
            default_roadclass = roadclasses[
                generate_key(default_roadclass_attributes, valid_values)
            ]
        except KeyError:
            default_roadclass = RoadClass.objects.create_from_attributes(
                default_roadclass_attributes, traffic_situation=default_ts
            )

    # get dict of tags to read from road file
    tags_dict = config.get("tags", None)
    tag_defaults = defaults.pop("tags", {})
    messages = {}

    def make_road(feature):  # noqa: C901, PLR0912, PLR0915
        source_geom = feature.geom
        if len(source_geom) < 2:
            msg = "invalid geometry (< 2 nodes), instance not imported"
            handle_msg(messages, msg)
            raise ValidationError(msg)
        source_geom.coord_dim = 2
        source_geom.transform(trans)
        geom = source_geom.geos
        road_data = {"geom": geom}

        for target_name, source_name in attr_dict.items():
            default_value = defaults.get(target_name, None)
            if source_name is not None:
                try:
                    val = feature.get(source_name)
                except UnicodeDecodeError:
                    raise ImportError(
                        f"could not decode string in field {source_name}, "
                        "only encoding utf-8 is supported"
                    )
                except KeyError:
                    raise ImportError(
                        f"No field named '{source_name}' found in "
                        f"input file '{roadfile}'"
                    )
                if val is None:
                    val = default_value
            else:
                msg = f"no source field specified for target field {target_name}"
                if default_value is not None:
                    msg += f", using default value '{default_value}'"
                else:
                    msg += " and no default value specified"
                handle_msg(messages, msg)
                val = default_value

            if val is None:
                handle_msg(messages, f"field {target_name} of road is None")
                if target_name == "name":
                    road_data[target_name] = ""
            else:
                road_data[target_name] = val

        if "width" in road_data and road_data["width"] == 0:
            road_data["width"] = RoadSource._meta.get_field("width").default
            handle_msg(
                messages,
                "invalid value (0m) for road width, "
                f"using default value {road_data['width']}m",
            )

        road = RoadSource(**road_data)

        if "roadclass" in config:
            try:
                rc_key = tuple(
                    [
                        str(feature.get(roadclass_attr_dict[attr.slug])) or "-"
                        for attr in valid_values
                    ]
                )
            except (ValueError, IndexError):
                raise ImportError(
                    f"No field named '{roadclass_attr_dict[attr.slug]}' found in "
                    f"input file '{roadfile}'"
                )

            try:
                road.roadclass = roadclasses[rc_key]
            except KeyError:
                handle_msg(
                    messages,
                    f"no roadclass with attribute values {rc_key} in inventory ",
                    fail_early=True,
                )
                raise ValidationError(msg)
        else:
            road.roadclass = default_roadclass

        if "congestion_profile" in config:
            try:
                field_name = config["congestion_profile"]
                name = feature.get(field_name) if field_name is not None else None
            except ValueError:
                raise ImportError(
                    f"No field named '{field_name}' found in input file '{roadfile}'"
                )
            except KeyError:
                raise ImportError(
                    f"No field named '{field_name}' found in input file '{roadfile}'"
                )
            if name is None:
                road.congestion_profile = default_congestion_profile
            elif name not in congestion_profiles:
                handle_msg(
                    messages,
                    f"no congestion profile with name '{name}' in inventory ",
                    fail_early=True,
                )
                raise ValidationError(msg)
            else:
                road.congestion_profile = congestion_profiles[name]
        else:
            road.congestion_profile = default_congestion_profile

        if "fleet" in config:
            try:
                field_name = config["fleet"]
                name = feature.get(field_name)
            except (KeyError, IndexError):
                raise ImportError(
                    f"No field named '{field_name}' found in input file '{roadfile}'"
                )

            if name is None or name not in fleets:
                handle_msg(
                    messages,
                    f"no fleet with name '{name}' in inventory ",
                    fail_early=True,
                )
                raise ValidationError(msg)
            road.fleet = fleets[name]
        else:
            road.fleet = default_fleet

        if tags_dict is not None:
            tag_data = {}
            for tag_key, source_name in tags_dict.items():
                tag_default = tag_defaults.get(tag_key, None)

                if source_name is not None:
                    try:
                        val = feature.get(source_name)
                    except KeyError:
                        raise ImportError(
                            f"No field named '{source_name}' found in "
                            f"input file '{roadfile}'"
                        )
                else:
                    val = None

                if val is not None:
                    tag_data[tag_key] = val
                elif tag_default is not None:
                    tag_data[tag_key] = tag_default
                    handle_msg(messages, f"road lack a value for tag '{tag_key}'")
            road.tags = tag_data
        return road

    roads = []
    count = 0
    nroads = len(layer)
    old_progress = -1
    ncreated = 0
    for features in inbatch(layer, chunksize):
        for feature in features:
            count += 1

            progress = count / nroads * 100
            if int(progress) > old_progress:
                log.info(f"done {int(progress)}%")
                old_progress = int(progress)

            if exclude is not None and filter_out(feature, exclude):
                continue
            if only is not None and not filter_out(feature, only):
                continue

            try:
                road = make_road(feature)
            except ValidationError:
                continue
            roads.append(road)
        RoadSource.objects.bulk_create(roads)
        ncreated += len(roads)
        roads = []
        if progress_callback:
            progress_callback(count)
    log.info(f"created {ncreated} roads")
    if len(messages) > 0:
        log.warning("Summary: ")
        for msg, nr in messages.items():
            log.warning("- " + msg + f": {nr} roads")
