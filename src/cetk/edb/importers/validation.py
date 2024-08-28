import os
from os.path import basename, splitext

import pandas as pd
import rasterio as rio

from cetk.edb.units import emission_unit_to_si


def with_rownr(msg, row_nr):
    return f"{msg}, at row {row_nr}"


def with_rownr_and_substance(msg, row_nr, substance):
    return f"{msg}, for '{substance}' at row {row_nr}"


def validate_columns(
    df, required_cols, code_sets=None, substances=None, activities=None
):
    messages = []
    missing_cols = [
        col for col in required_cols if col not in df.columns and df.index.name != col
    ]
    if len(missing_cols) > 0:
        messages.append(
            f"GridSource: Missing required columns: '{', '.join(missing_cols)}'"
        )

    if code_sets is not None:
        for codeset_slug in code_sets:
            col_name = f"activitycode_{codeset_slug}"
            if col_name not in df.columns:
                messages.append(
                    f"GridSource: Missing column for code-set '{codeset_slug}'"
                )
    if substances is not None:
        expected_substances = {
            col[6:] for col in df.columns if col.startswith("subst:")
        }
        invalid_substances = expected_substances.difference(substances.keys())
        if len(invalid_substances) > 0:
            messages.append(f"GridSource: Invalid substances: {invalid_substances}")

    if activities is not None:
        expected_activities = {
            col[4:].strip() for col in df.columns if col.startswith("act:")
        }
        invalid_activities = expected_activities.difference(activities.keys())
        if len(invalid_activities) > 0:
            messages.append(f"GridSource: Invalid activities: {invalid_activities}")
    return messages


def validate_unit(values, row_nr):
    """validate substance emission unit."""
    messages = []
    unit = values["emission_unit"]
    try:
        emission_unit_to_si(1.0, unit)
    except (KeyError, ValueError) as err:
        messages.append(with_rownr(f"GridSource: invalid unit, {err}", row_nr))
    return messages


def validate_activitycodes(values, code_sets, row_nr, src=None):
    """validate and set activity codes."""
    messages = []
    # get activitycodes
    for code_ind, (codeset_slug, codes) in enumerate(code_sets.items(), 1):
        code_attribute = f"activitycode{code_ind}"
        code_col = f"activitycode_{codeset_slug}"
        code = values[code_col]
        if code is None:
            messages.append(f"GridSource: missing value in column '{code_col}'")
        try:
            activitycode = codes[code]
        except KeyError:
            messages.append(f"GridSource: unknown code '{code}' in column '{code_col}'")
        if src is not None:
            setattr(src, code_attribute, activitycode)
    return [with_rownr(msg, row_nr) for msg in messages]


def validate_timevar(values, timevars, row_nr, src=None):
    """validate and set timevar."""
    timevar_name = values["timevar"]
    messages = []
    if pd.notna(timevar_name):
        try:
            timevar = timevars[timevar_name]
        except KeyError:
            messages.append(f"GridSource: timevar '{timevar_name}' does not exist")
    else:
        timevar = None
    if src is not None:
        src.timevar = timevar
    return [with_rownr(msg, row_nr) for msg in messages]


def data_to_raster(raster_name, raster_path, datadir, substance):
    if raster_path is not None:
        # generate raster name form path
        if raster_name is None:
            raster_name = splitext(basename(raster_path))[0]
        # if placeholder is used for substance in path
        # the raster-name will be given a suffix

        if "{subst}" in raster_path:
            if "{subst}" not in raster_name:
                raster_name += "-{subst}"
            rpath = raster_path.format(subst=substance)
            rname = raster_name.format(subst=substance)
        else:
            rpath = raster_path
            rname = raster_name

        if not os.path.isabs(rpath):
            rpath = os.path.join(datadir, rpath)
    else:
        rpath = None
        rname = (
            raster_name.format(subst=substance)
            if "{subst}" in raster_name
            else raster_name
        )
    return rname, rpath


def validate_raster(
    values: dict,
    raster_names: list,
    datadir: str,
    raster_dict: dict,
    row_nr: int,
    substance: str,
):
    messages = []
    rasters_without_path = []
    raster_path = values["path"] if not pd.isna(values["path"]) else None
    raster_name = values["rastername"] if not pd.isna(values["rastername"]) else None
    if raster_name is None and raster_path is None:
        messages.append("neither rastername nor path specified")
    rname, rpath = data_to_raster(raster_name, raster_path, datadir, substance)
    if rpath is not None:
        if not os.path.exists(rpath):
            messages.append(f"raster with path {rpath} does not exist")
        elif rname not in raster_dict:
            with rio.open(rpath, "r") as dset:
                try:
                    _ = int(dset.crs.to_authority()[1])
                except ValueError:
                    messages.append(
                        "raster coordinate reference system has no epsg code"
                    )
                rdata = dset.read()
            raster_dict.setdefault(rname, {})["sum"] = rdata[rdata != dset.nodata].sum()
            raster_dict[rname]["path"] = rpath
    else:
        rasters_without_path.append(rname)

    for rname in rasters_without_path:
        if rname not in raster_names and rname not in raster_dict:
            messages.append(
                f"raster '{rname}' not found in database, and no path specified"
            )

    return [with_rownr_and_substance(msg, row_nr, substance) for msg in messages]


def validate_emission(values, row_nr, substance):
    """validate emission value"""
    messages = []
    emis_value = values[f"subst:{substance}"]
    if emis_value != "sum":
        try:
            val = float(emis_value)
            if val < 0:
                messages.append(
                    with_rownr_and_substance("emission value < 0", row_nr, substance)
                )
        except ValueError:
            messages.append(
                with_rownr_and_substance(
                    f"Invalid emission value '{emis_value}'", row_nr, substance
                )
            )
    return messages


def validate_activity(values, row_nr, activity):
    """validate emission value"""
    messages = []
    rate = values[f"act:{activity}"]
    if rate != "sum":
        try:
            if float(rate) < 0:
                messages.append(
                    with_rownr_and_substance("activity rate < 0", row_nr, activity)
                )
        except ValueError:
            messages.append(
                with_rownr_and_substance(
                    f"invalid activity rate '{rate}'", row_nr, activity
                )
            )
    return messages
