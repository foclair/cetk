import copy
import logging
import os
from collections import OrderedDict
from operator import itemgetter
from pathlib import Path

# need to import fiona before geopandas due to gpd bug causing circular imports.
import fiona  # noqa
import geopandas as gpd
import numpy as np  # noqa
import pandas as pd
from django.contrib.gis.gdal import CoordTransform  # noqa
from django.contrib.gis.gdal import SpatialReference
from django.contrib.gis.gdal.geometries import LineString as GDALLineString
from django.contrib.gis.geos import Point, Polygon  # noqa
from django.core.exceptions import ObjectDoesNotExist, ValidationError  # noqa
from django.core.management.base import CommandError  # noqa
from django.db import IntegrityError  # noqa
from openpyxl import load_workbook

from cetk.edb.const import WGS84_SRID
from cetk.edb.models import ColdstartTimevar  # noqa
from cetk.edb.models import (
    CodeSet,
    CongestionProfile,
    Fleet,
    FleetMemberFuel,
    FlowTimevar,
    PrefetchRoadClassAttributes,
    RoadAttribute,
    RoadClass,
    RoadSource,
    Substance,
    TrafficSituation,
    Vehicle,
    VehicleEF,
    VehicleFuel,
    VehicleFuelComb,
    get_valid_road_attribute_values,
)
from cetk.edb.units import emission_unit_to_si, vehicle_ef_unit_to_si  # noqa
from cetk.utils import inbatch

from .timevar_import import import_timevarsheet
from .utils import import_error, worksheet_to_dataframe

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


def vehicles_excel_to_dict(file_path):
    dtype_dict = {"name": str, "isheavy": bool, "info": str, "fuel": str}
    for cs in CodeSet.objects.all():
        dtype_dict["activitycode_" + cs.slug] = str
    df = pd.read_excel(file_path, sheet_name="VehicleFuel", dtype=dtype_dict).fillna("")

    # Extract the code sets from the DataFrame
    activity_columns = [col for col in df.columns if col.startswith("activitycode_")]
    code_sets = {
        f"code_set{i+1}": col.split("_")[1] for i, col in enumerate(activity_columns)
    }

    data = {**code_sets, "vehicles": []}
    vehicles = []
    for index, row in df.iterrows():
        activitycodes = {}
        for col in activity_columns:
            ac_id = CodeSet.objects.get(slug=col.replace("activitycode_", "")).id
            activitycodes[f"activitycode{ac_id}"] = row[col]
        # Check if the vehicle already exists in the data dictionary
        if row["name"] in vehicles:
            vehicle = next(
                (
                    vehicle
                    for vehicle in data["vehicles"]
                    if vehicle["name"] == row["name"]
                ),
                None,
            )
            # vehicle exists, set fuel type
            # first check that fuel type didn't exist yet
            vehicle["fuels"][row["fuel"]] = activitycodes
        else:
            vehicle_data = {
                "name": row["name"],
                "isheavy": row["isheavy"],
                "info": row["info"],
                "fuels": {},
            }
            vehicle_data["fuels"][row["fuel"]] = activitycodes
            data["vehicles"].append(vehicle_data)
            vehicles.append(row["name"])
    return data


def roadclass_excel_to_dict(file_path, validation=False):
    msg = []
    df = pd.read_excel(file_path, sheet_name="RoadAttribute")
    df_values = pd.read_excel(file_path, sheet_name="TrafficSituation", dtype=str)
    data = {"attributes": []}
    for index, row in df.iterrows():
        try:
            unique_values = list(set(df_values["attr:" + row["slug"]]))
            data["attributes"].append(
                {"name": row["name"], "slug": row["slug"], "values": unique_values}
            )
        except KeyError:
            msg = import_error(
                f"Attribute not found in TrafficSituation sheet: {row['slug']}",
                validation=validation,
            )
    return data, msg


def fleet_excel_to_dict(file_path, validation=False):
    df = pd.read_excel(file_path, sheet_name="Fleet")
    data = {}
    fuel_columns = [col for col in df.columns if col.startswith("fuel:")]
    msg = []
    for index, row in df.iterrows():
        fuels = {}
        for i, col in enumerate(fuel_columns):
            if row[col] > 0:
                fuels[col[5:]] = row[col]
        vehicle_data = {
            "fraction": row["vehicle_fraction"],
            "coldstart_fraction": row["coldstart_fraction"],
            "timevar": row["flow_timevar"],
            "coldstart_timevar": row["coldstart_timevar"],
            "fuels": fuels,
        }
        if row["name"] in data.keys():
            if row["vehicle"] in data[row["name"]]["vehicles"].keys():
                msg = import_error(
                    f"duplicated vehicle {row['vehicle']} for fleet {row['name']}",
                    validation=validation,
                )
            else:
                data[row["name"]]["vehicles"][row["vehicle"]] = vehicle_data
        else:
            data[row["name"]] = {
                "default_heavy_vehicle_share": row["default_heavy_vehicle_share"],
                "vehicles": {row["vehicle"]: vehicle_data},
            }
    return data, msg


def roadsource_excel_to_dict(file_path):
    df = pd.read_excel(file_path, sheet_name="RoadSource")
    attribute_columns = [col for col in df.columns if col.startswith("attr:")]
    attributes = {col[5:]: str(df[col].values[0]) for col in attribute_columns}
    tag_columns = [col for col in df.columns if col.startswith("tag:")]
    tags = {col[4:]: str(df[col].values[0]) for col in tag_columns}
    data = {
        col: str(df[col].values[0])
        for col in df.columns
        if not (
            col.startswith("attr:")
            or col.startswith("tag:")
            or pd.isnull(df[col].values[0])
        )
    }
    data["roadclass"] = attributes
    data["tags"] = tags
    return data


def import_traffic(filename, sheets, validation=False):
    # in case the excel file is a big file, using workbook as argument instead
    # of filename would be a good way to optimize import
    workbook = load_workbook(filename=filename, data_only=True, read_only=True)
    return_dict = {}
    return_message = []
    if "VehicleFuel" in sheets:
        vehiclesettings = vehicles_excel_to_dict(filename)
    elif "VehicleEmissionFactor" in sheets:
        log.error(
            "Cannot import or validate vehicle emfacs if VehicleFuel "
            "is not set in the same file."
        )
        raise ImportError
    if "VehicleEmissionFactor" in sheets:
        df = worksheet_to_dataframe(workbook["VehicleEmissionFactor"].values)
        unit = set(df["unit"])
        if len(unit) > 1:
            return_message.append(
                import_error(
                    "Several units found for import " f"{unit}, can only use one",
                    validation=validation,
                )
            )
        unit = str(list(unit)[0])
        updates = import_vehicles(
            filename,
            vehiclesettings,
            unit=unit,  # "kg/m"
            encoding="utf-8",
            overwrite=True,
            validation=validation,
        )
        return_dict.update(updates)
    if ("RoadAttribute" in sheets) and ("TrafficSituation" in sheets):
        roadclass_settings, msg = roadclass_excel_to_dict(filename, validation)
        return_message += msg
        import_roadclasses(
            filename,
            roadclass_settings,
            encoding="utf-8",
            overwrite=True,
            validation=validation,
        )
    elif ("RoadAttribute" in sheets) and ("TrafficSituation" in sheets):
        raise ImportError(
            "Have to import TrafficSituation and RoadAttribute simultaneously."
        )
    if "CongestionProfile" in sheets:
        _, msg = import_congestionsheet(workbook, validation=validation)
        return_message += msg
    if "FlowTimevar" in sheets:
        _, msg = import_timevarsheet(workbook, validation, sheetname="FlowTimevar")
        return_message += msg
    if "ColdstartTimevar" in sheets:
        _, msg = import_timevarsheet(workbook, validation, sheetname="ColdstartTimevar")
        return_message += msg
    if "Fleet" in sheets:
        try:
            fleet_data, msg = fleet_excel_to_dict(filename, validation)
            return_message += msg
            _, msg = import_fleets(fleet_data, overwrite=True, validation=validation)
            return_message += msg
        except ImportError as err:
            return {}, [f"{err}"]
    if "RoadSource" in sheets:
        try:
            config = roadsource_excel_to_dict(filename)
            roadfile_path = config["filepath"]
            if not os.path.isabs(roadfile_path):
                datadir = os.path.dirname(filename)
                roadfile_path = os.path.join(datadir, roadfile_path)
            updates, msg = import_roads(roadfile_path, config, validation=validation)
            return_dict.update(updates)
            return_message += msg
        except ImportError as err:
            return {}, [f"{err}"]
    workbook.close()
    return return_dict, return_message  # update dict and messages


def import_vehicles(  # noqa: C901, PLR0912, PLR0915
    vehicles_file,
    config,
    *,
    only_ef=False,
    overwrite=False,
    validation=False,
    unit="mg/km",
    encoding="utf-8",
):
    """Import vehicles, fuels and traffic situations to ef-set.

    args
        vehicles_file: a csv-file or xlsx-file with vehicles and emission-factors
        config: a dict with definitions of vehicle, fuels and codes

    optional
        only_ef: if True, only load emission factors - do not modify base-set tables
        overwrite: if True, existing instances will be ovewritten
        unit: unit of emission-factors to import, default is "mg/km"
    """

    # cache valid activity codes
    valid_codes = OrderedDict()
    code_sets = [None, None, None]
    config = copy.deepcopy(config)
    return_message = []

    # cache activity-codes for code-sets specified in config file
    for i in range(3):
        code_nr = i + 1
        code_sets[i] = config.pop(f"code_set{code_nr}", None)

        if code_sets[i] is not None:
            try:
                code_sets[i] = CodeSet.objects.get(slug=code_sets[i])
            except ObjectDoesNotExist:
                return_message.append(
                    import_error(
                        f"Invalid codeset slug: {code_sets[i]}",
                        validation=validation,
                    )
                )

            valid_codes[code_sets[i].slug] = {
                ac.code: ac for ac in code_sets[i].codes.all()
            }

    def validate_ac(code_data, valid_codes, validation=False, return_message=[]):
        if "activitycode1" in code_data and len(valid_codes) == 0:
            return_message.append(
                import_error(
                    "no activity codes defined, but codes given for vehicle",
                    validation=validation,
                )
            )

        for code_set_name, codes in valid_codes.items():
            code_nr = CodeSet.objects.get(slug=code_set_name).id
            try:
                ac = code_data[f"activitycode{code_nr}"]
            except KeyError:
                return_message.append(
                    import_error(
                        f"no value specified for activity code {code_nr}"
                        f" ({code_set_name}) of vehicle/fuel combination "
                        f"'{vehicle_name}' - '{fuel_name}'",
                        validation=validation,
                    )
                )
            if ac not in codes and ac != "":
                return_message.append(
                    import_error(
                        f"invalid value '{ac}' for activity code "
                        f"{code_nr} ({code_set_name})"
                        f" of vehicle/fuel combination "
                        f"'{vehicle_name}' - '{fuel_name}'",
                        validation=validation,
                    )
                )
            code_nr += 1
        return return_message

    try:
        mass_unit, length_unit = unit.split("/")
    except ValueError:
        log.error(f"invalid emission-factor unit {unit} specified in config-file")
        raise
    log.debug(f"emission factor units is: {unit}")

    messages = {}
    with Path(vehicles_file).open(encoding=encoding) as veh_file:
        log.debug("reading emission-factor table")
        dtype_dict = {
            "vehicle": str,
            "fuel": str,
            "traffic_situation": str,
            "substance": str,
            "freeflow": float,
            "heavy": float,
            "saturated": float,
            "stopngo": float,
            "coldstart": float,
        }
        if Path(vehicles_file).suffix == ".csv":
            df = pd.read_csv(
                veh_file,
                sep=";",
                dtype=dtype_dict,
            )
        elif Path(vehicles_file).suffix == ".xlsx":
            df = pd.read_excel(
                vehicles_file, dtype=dtype_dict, sheet_name="VehicleEmissionFactor"
            )
        else:
            raise ValueError(
                "File for import vehicle emissions factors should be " + ".csv or .xlsx"
            )
        # indexes are set after reading csv in order to allow
        # specification of dtypes for index columns
        try:
            df = df.set_index(["vehicle", "fuel", "traffic_situation", "substance"])
        except KeyError as err:
            raise ImportError(f"Invalid csv-file: {err}")

        for col in ("freeflow", "heavy", "saturated", "stopngo", "coldstart"):
            if col not in df.columns:
                raise ImportError(
                    f"Required column '{col}' not found in file '{vehicles_file}"
                )

        log.debug("checking that all substances exist in the database")
        substances = {}
        for subst in df.index.get_level_values(3).unique():
            try:
                substances[subst] = Substance.objects.get(slug=subst)
            except ObjectDoesNotExist:
                msg = f"substance {subst} does not exist in database"
                return_message.append(import_error(msg), validation=validation)

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
                        return_message.append(
                            import_error(
                                "either duplicate specification or vehicle "
                                f"'{vehicle_name}' already exists.",
                                validation=validation,
                            )
                        )
                    if created:
                        log.debug(f"created vehicle {vehicle_name}")
                elif not Vehicle.objects.filter(name=vehicle_name).exists():
                    return_message.append(
                        import_error(  # noqa: TRY301
                            f"vehicle '{vehicle_name}' does not exist ",
                            validation=validation,
                        )
                    )
            except Exception as err:
                return_message.append(
                    import_error(
                        f"invalid specification of vehicle in config-file: {err}",
                        validation=validation,
                    )
                )
            if vehicle_name not in df_vehicles:
                log.warning(
                    "warning: no emission-factors specified for vehicle"
                    f" '{vehicle_name}'",
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
                        return_message.append(
                            import_error(
                                f"fuel {fuel_name} does not exist in database",
                                validation=validation,
                            )
                        )
                return_message.append(
                    validate_ac(code_data, valid_codes, validation=validation)
                )

                # get activity code model instances for each activity code
                ac_codes = [None, None, None]
                for i in range(3):
                    code_nr = i + 1
                    ac_codes[i] = code_data.get(f"activitycode{code_nr}", None)
                    if ac_codes[i] is not None and ac_codes[i] != "":
                        try:
                            ac_codes[i] = valid_codes[
                                CodeSet.objects.get(id=code_nr).slug
                            ][ac_codes[i]]
                        except KeyError:
                            return_message.append(
                                import_error(
                                    f"Found invalid activitycode {ac_codes[i]}",
                                    validation=validation,
                                )
                            )
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
                    return_message.append(
                        import_error(
                            "vehicle/fuel combination "
                            f"'{vehicle_name}' - '{fuel_name}' "
                            "does not exist.",
                            validation=validation,
                        )
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
                return_message.append(
                    import_error(
                        f"traffic-situation {ts_id} does not exist.",
                        validation=validation,
                    )
                )
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
        return_message.append(
            import_error(
                f"The following emission factors already exist in the ef-set: {msg}",
                validation=validation,
            )
        )

    if len(efs_to_update) > 0:
        VehicleEF.objects.bulk_update(
            efs_to_update,
            ("freeflow", "heavy", "saturated", "stopngo", "coldstart"),
        )
        log.debug(f"updated {len(efs_to_update)} emission-factors")
        return_dict = {"vehicle_emission_factors": {"updated": len(efs_to_update)}}
    else:
        return_dict = {"vehicle_emission_factors": {"updated": 0}}
    for msg, nr in messages.items():
        log.warning("warning: " + msg + f": {nr}")

    if len(efs_to_create) > 0:
        try:
            VehicleEF.objects.bulk_create(efs_to_create)
            log.debug(f"wrote {len(efs_to_create)} emission-factors")
            return_dict["vehicle_emission_factors"]["created"] = len(efs_to_create)
        except IntegrityError:
            for ef in efs_to_create:
                try:
                    ef.save()
                except IntegrityError:
                    return_message.append(
                        import_error(
                            "duplicate emission-factors for: "
                            f"substance '{ef.substance.slug}, "
                            f"vehicle: '{ef.vehicle.name}', "
                            f"fuel:  '{ef.fuel.name}', "
                            f"traffic-situation: '{ef.traffic_situation.ts_id}'",
                            validation=validation,
                        )
                    )
    else:
        return_dict["vehicle_emission_factors"]["created"] = 0
    return return_dict


def import_roadclasses(  # noqa: C901, PLR0912, PLR0915
    roadclass_file, config, *, overwrite=False, validation=False, **kwargs
):
    """import roadclasses (traffic-situations must already exist in database)."""
    return_message = []
    encoding = kwargs.get("encoding", "utf-8")
    try:
        attributes = config["attributes"]
    except KeyError:
        ImportError("keyword 'attributes' not found in config")

    log.debug("create road attributes")

    # created objects are stored in a nested dict
    defined_attributes = OrderedDict()
    for ind, attr_dict in enumerate(attributes):
        attr_dict_tmp = copy.deepcopy(attr_dict)
        try:
            values = attr_dict_tmp.pop("values")
        except KeyError:
            ImportError("keyword 'values' not found for in config")

        try:
            attr = RoadAttribute.objects.get(
                name=attr_dict_tmp["name"], slug=attr_dict_tmp["slug"]
            )
        except RoadAttribute.DoesNotExist:
            try:
                attr = RoadAttribute.objects.create(
                    name=attr_dict_tmp["name"], slug=attr_dict_tmp["slug"], order=ind
                )
            except IntegrityError as err:
                return_message.append(
                    import_error(
                        "invalid or duplicate road class attribute: "
                        f"{attr_dict['name']}: {err}",
                        validation=validation,
                    )
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
                return_message.append(
                    import_error(
                        "Unused road attribute '{attr.slug}' found",
                        validation=validation,
                    )
                )
        for label, value in values.items():
            if label not in defined_attributes[attr]:
                if overwrite:
                    value.delete()
                else:
                    return_message.append(
                        import_error(
                            "Unused road attribute value '{label}' found",
                            validation=validation,
                        )
                    )

    # cache all existing traffic situations and road-classes
    traffic_situations = {ts.ts_id: ts for ts in TrafficSituation.objects.all()}

    existing_roadclasses = {
        tuple(rc.attributes.values()): rc.id
        for rc in RoadClass.objects.prefetch_related(PrefetchRoadClassAttributes())
    }

    log.debug("reading roadclass table")
    with Path(roadclass_file).open(encoding=encoding) as roadclass_stream:
        roadclass_attributes = [a.slug for a in defined_attributes]
        if Path(roadclass_file).suffix == ".csv":
            try:
                column_names = [*roadclass_attributes, "traffic_situation"]
                df = pd.read_csv(
                    roadclass_stream, sep=";", dtype=str, usecols=column_names
                ).set_index([a.slug for a in defined_attributes])
            except Exception as err:
                ImportError(
                    "could not read csv, are all roadclass attributes "
                    f"{roadclass_attributes} and 'traffic_situation' "
                    f"given as columns? (error message: {err})"
                )
        elif Path(roadclass_file).suffix == ".xlsx":
            try:
                column_names = ["attr:" + rc for rc in roadclass_attributes]
                column_names.append("traffic_situation")
                df = pd.read_excel(
                    roadclass_file,
                    dtype=str,
                    sheet_name="TrafficSituation",
                    usecols=column_names,
                )
                df.rename(
                    columns={"attr:" + rc: rc for rc in roadclass_attributes},
                    inplace=True,
                )
                df.set_index([a.slug for a in defined_attributes], inplace=True)
            except Exception as err:
                raise ImportError(
                    "could not read xlsx, are all roadclass attributes "
                    f"{roadclass_attributes} and 'traffic_situation' "
                    "given as columns? and does the sheet TrafficSituation exist? "
                    f"(error message: {err})"
                )
        else:
            raise ImportError(
                "File for import vehicle emissions factors should be " + ".csv or .xlsx"
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
                    return_message.append(
                        import_error(
                            f"Invalid value '{val}' for road attribute '{attr.slug}'",
                            validation=validation,
                        )
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
            return_message.append(
                import_error(
                    "invalid traffic-situations:\n"
                    + "\n  ".join(invalid_traffic_situations),
                    validation=validation,
                )
            )

        if len(roadclasses_to_update) > 0:
            for rc, attribute_values in roadclasses_to_update:
                if overwrite:
                    rc.save()
                    rc.attribute_values.set(attribute_values)
                else:
                    return_message.append(
                        import_error(
                            f"roadclass '{rc}' already exists.", validation=validation
                        )
                    )
        if len(roadclasses_to_create) > 0:
            RoadClass.objects.bulk_create(map(itemgetter(0), roadclasses_to_create))
            # list of saved roadclasses to avoid problem unsaved related attributes
            roadclasses_to_create_saved = []
            # created roadclasses should only be those who have no attribute values yet!
            # this could go wrong if none of the roadclasses has attributes
            # but then does not make sense to have several roadclasses anyhow.
            created_roadclasses = RoadClass.objects.filter(attribute_values=None)
            for i, rc in enumerate(created_roadclasses):
                roadclasses_to_create_saved.append((rc, roadclasses_to_create[i][1]))

            through_model = RoadClass.attribute_values.through

            values = [
                through_model(roadclass=rc, roadattributevalue=v)
                for rc, vals in roadclasses_to_create_saved
                for v in vals
            ]

            through_model.objects.bulk_create(values)


def import_congestionsheet(workbook, sheetname="CongestionProfile", validation=False):
    congestion_data = workbook[sheetname].values
    df_congestion = worksheet_to_dataframe(congestion_data)
    congestion_dict = {}
    # NB this only works if Excel file has exact same format
    nr_profiles = (len(df_congestion["ID"]) + 1) // 25
    for i in range(nr_profiles):
        label = df_congestion["ID"][i * 25]
        typeday = np.asarray(
            df_congestion[
                [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                ]
            ][i * 25 : i * 25 + 24]
        )
        congestion_dict[label] = {"traffic_condition": typeday}
    return_dict, return_message = import_congestion_profiles(
        congestion_dict, overwrite=True, validation=validation
    )
    return_dict = {"congestion": {"updated or created": len(congestion_dict)}}
    return return_dict, return_message


def import_congestion_profiles(profile_data, *, overwrite=False, validation=False):
    """import congestion profiles."""
    return_message = []
    # Profile instances must not be created by bulk_create as the save function
    # is overloaded to calculate the normation constant.

    def make_profiles(data):
        retdict = {}
        for name, timevar_data in data.items():
            try:
                traffic_condition = timevar_data["traffic_condition"]
                if type(traffic_condition) == list:
                    traffic_condition = str(traffic_condition)
                else:
                    traffic_condition = np.array2string(
                        traffic_condition, separator=","
                    ).replace("\n", "")
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
                return_message.append(
                    import_error(
                        f"Invalid specification of congestion-profile {name}"
                        f", is 'traffic_condition' specified?",
                        validation=validation,
                    )
                )
        return retdict, return_message

    profiles = {}
    profiles["profiles"], return_message = make_profiles(profile_data)
    return profiles, return_message


def import_fleets(
    data, *, overwrite=False, validation=False
):  # noqa: C901, PLR0912, PLR0915
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
    return_message = []
    for name, fleet_data in data.items():
        fleet_data_tmp = copy.deepcopy(fleet_data)
        try:
            members_data = fleet_data_tmp.pop("vehicles", [])
            default_heavy_vehicle_share = fleet_data_tmp["default_heavy_vehicle_share"]
        except KeyError:
            return_message.append(
                import_error(
                    f"no 'default_heavy_vehicle_share' specified for fleet '{name}'",
                    validation=validation,
                )
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
                return_message.append(
                    import_error(
                        f"either duplicate specification in file or "
                        f"fleet '{name}' already exist in inventory",
                        validation=validation,
                    )
                )

        members = OrderedDict()
        heavy_member_sum = 0
        light_member_sum = 0
        for vehicle_name, member_data in members_data.items():
            fuels_data = member_data.pop("fuels", [])
            timevar_name = member_data.pop("timevar")
            coldstart_timevar_name = member_data.pop("coldstart_timevar")

            try:
                veh = existing_vehicles[vehicle_name]
            except KeyError:
                return_message.append(
                    import_error(
                        f"Vehicle {vehicle_name} specified in sheet Fleet "
                        "does not exist in sheet VehicleFuel.",
                        validation=validation,
                    )
                )
                continue
            # accumulate member fractions to ensure they sum up to 1.0
            if veh.isheavy:
                heavy_member_sum += member_data["fraction"]
            else:
                light_member_sum += member_data["fraction"]

            if timevar_name is not None:
                try:
                    member_data["timevar"] = existing_flow_timevars[timevar_name]
                except KeyError:
                    return_message.append(
                        import_error(
                            f"timevar '{timevar_name}' specified for vehicle "
                            f"'{vehicle_name}' in fleet '{name}' does not "
                            f"exist in inventory",
                            validation=validation,
                        )
                    )
            else:
                member_data["timevar"] = None

            if coldstart_timevar_name is not None:
                try:
                    member_data["coldstart_timevar"] = existing_coldstart_timevars[
                        coldstart_timevar_name
                    ]
                except KeyError:
                    return_message.append(
                        import_error(
                            f"coldstart timevar '{coldstart_timevar_name}' "
                            f"specified for vehicle '{vehicle_name}' "
                            f"in fleet '{name}' does not exist in inventory",
                            validation=validation,
                        )
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
                        return_message.append(
                            import_error(
                                "Either duplicate specification of fleet member in"
                                "config, or fleetmember already exist in inventory",
                                validation=validation,
                            )
                        )
            except (KeyError, TypeError):
                return_message.append(
                    import_error(
                        f"invalid specification of vehicle '{vehicle_name}' in "
                        f"fleet '{name}', must specify 'timevar','coldstart_timevar', "
                        "fraction, 'coldstart_fraction' and 'fuels'",
                        validation=validation,
                    )
                )

            fuel_sum = 0
            member_fuels = []
            if not isinstance(fuels_data, dict):
                return_message.append(
                    import_error(
                        f"invalid specification of fuels for '{vehicle_name}'"
                        f"in fleet '{name}', fuels should be specified as:\n"
                        f"fuels:\n  fuel1: 0.4\n  fuel2: 0.6",
                        validation=validation,
                    )
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
                return_message.append(
                    import_error(
                        f"sum of fuel fractions does not sum up to 1.0 (sum={fuel_sum})"
                        f" for '{vehicle_name}s' of fleet '{name}' in inventory ",
                        validation=validation,
                    )
                )
            FleetMemberFuel.objects.bulk_create(member_fuels)
        if heavy_member_sum > 0 and abs(heavy_member_sum - 1.0) >= 0.005:
            return_message.append(
                import_error(
                    f"sum of heavy fleet members does not sum up to 1.0 "
                    f"(sum={heavy_member_sum}) "
                    f"for fleet '{name}' in inventory ",
                    validation=validation,
                )
            )
        if light_member_sum > 0 and abs(light_member_sum - 1.0) >= 0.005:
            return_message.append(
                import_error(
                    f"sum of light fleet members does not sum up to 1.0 "
                    f"(sum={light_member_sum}) "
                    f"for fleet '{name}' in inventory ",
                    validation=validation,
                )
            )
    return len(fleets), return_message


def import_roads(  # noqa: C901, PLR0912, PLR0915
    roadfile,
    config,
    exclude=None,
    only=None,
    chunksize=1000,
    progress_callback=None,
    validation=False,
):
    """Import a road network."""
    return_message = []
    datasource = gpd.read_file(roadfile)

    if "srid" in config:
        src_proj = SpatialReference(config["srid"])
    else:
        src_proj = SpatialReference(datasource.crs.to_epsg())
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
                return_message.append(
                    import_error(
                        "default congestin profile "
                        f"'{default_congestion_profile_name}' does not exist",
                        validation=validation,
                    )
                )

    valid_values = get_valid_road_attribute_values()
    # get valid roadclass attributes
    if "roadclass" in defaults:
        default_roadclass_attributes = {}
        for attr, values in valid_values.items():
            value = defaults["roadclass"][attr.slug]
            if attr.slug not in defaults["roadclass"]:
                return_message.append(
                    import_error(
                        f"incomplete default roadclass attribute mappings,"
                        f" missing '{attr.slug}'",
                        validation=validation,
                    )
                )
            if value not in values:
                return_message.append(
                    import_error(
                        f"invalid roadclass attribute value {value} for"
                        f" attribute {attr.slug}",
                        validation=validation,
                    )
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
                return_message.append(
                    import_error(
                        "incomplete roadclass attribute mappings,"
                        + f" missing '{attr.slug}'",
                        validation=validation,
                    )
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
        source_geom = feature.geometry

        if np.shape(source_geom.xy)[1] < 2:
            msg = "invalid geometry (< 2 nodes), instance not imported"
            handle_msg(messages, msg)
            raise ValidationError(msg)

        gdalgeom = GDALLineString(source_geom.wkt)
        gdalgeom.coord_dim = 2
        gdalgeom.transform(trans)
        geom = gdalgeom.geos
        road_data = {"geom": geom}

        for target_name, source_name in attr_dict.items():
            default_value = defaults.get(target_name, None)
            if source_name is not None:
                try:
                    val = feature.get(source_name)
                except UnicodeDecodeError:
                    return_message.append(
                        import_error(
                            f"could not decode string in field {source_name}, "
                            "only encoding utf-8 is supported",
                            validation=validation,
                        )
                    )
                except KeyError:
                    return_message.append(
                        import_error(
                            f"No field named '{source_name}' found in "
                            f"input file '{roadfile}'",
                            validation=validation,
                        )
                    )
                if pd.isnull(val):
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

        if "width" in road_data and (
            road_data["width"] == 0 or road_data["width"] == ""
        ):
            road_data["width"] = RoadSource._meta.get_field("width").default
            handle_msg(
                messages,
                "invalid value (0m) for road width, "
                f"using default value {road_data['width']}m",
            )

        if (
            "width" in road_data
            and type(road_data["width"]) == str
            and ("m" in road_data["width"])
        ):
            try:
                road_data["width"] = float(road_data["width"].replace("m", ""))
            except ValueError:
                road_data["width"] = RoadSource._meta.get_field("width").default
                handle_msg(
                    messages,
                    "invalid value (including unit m) for road width, "
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
                return_message.append(
                    import_error(
                        f"No field named '{roadclass_attr_dict[attr.slug]}' found in "
                        f"input file '{roadfile}'",
                        validation=validation,
                    )
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
                return_message.append(
                    import_error(
                        f"No field named '{field_name}' found "
                        f"in input file '{roadfile}'",
                        validation=validation,
                    )
                )
            except KeyError:
                return_message.append(
                    import_error(
                        f"No field named '{field_name}' found "
                        f"in input file '{roadfile}'",
                        validation=validation,
                    )
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
                return_message.append(
                    import_error(
                        f"No field named '{field_name}' found "
                        f"in input file '{roadfile}'",
                        validation=validation,
                    )
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
                        return_message.append(
                            import_error(
                                f"No field named '{source_name}' found in "
                                f"input file '{roadfile}'",
                                validation=validation,
                            )
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
    nroads = len(datasource)
    old_progress = -1
    ncreated = 0
    for features in inbatch(datasource.iterrows(), chunksize):
        for feature in features:
            count += 1

            progress = count / nroads * 100
            if int(progress) > old_progress:
                if not validation:
                    log.debug(f"done {int(progress)}%")
                old_progress = int(progress)

            if exclude is not None and filter_out(feature[1], exclude):
                continue
            if only is not None and not filter_out(feature[1], only):
                continue

            try:
                road = make_road(feature[1])
            except ValidationError:
                continue
            roads.append(road)
        RoadSource.objects.bulk_create(roads)
        ncreated += len(roads)
        roads = []
        if progress_callback:
            progress_callback(count)
    log.debug(f"created {ncreated} roads")
    return_dict = {"roads": {"created": ncreated, "updated": 0}}
    if len(messages) > 0:
        log.warning("Summary: ")
        for msg, nr in messages.items():
            log.warning("- " + msg + f": {nr} roads")

    return return_dict, return_message
