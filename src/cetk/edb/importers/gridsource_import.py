import logging
from os.path import dirname

import numpy as np
import pandas as pd
import rasterio as rio
from openpyxl import load_workbook

from cetk.edb.cache import cache_queryset
from cetk.edb.models import (
    Activity,
    GridSource,
    Substance,
    Timevar,
    drop_gridsource_raster,
    list_gridsource_rasters,
    write_gridsource_raster,
)
from cetk.edb.units import activity_rate_unit_to_si, emission_unit_to_si

from .utils import (
    cache_codesets,
    get_activity_rate_columns,
    get_substance_emission_columns,
    nan2None,
    worksheet_to_dataframe,
)
from .validation import (
    data_to_raster,
    validate_activity,
    validate_activitycodes,
    validate_columns,
    validate_emission,
    validate_raster,
    validate_timevar,
    validate_unit,
    with_rownr_and_substance,
)

REQUIRED_COLUMNS_GRID = ["name", "rastername", "timevar", "path", "emission_unit"]


log = logging.getLogger(__name__)


def read_csv(filepath, encoding=None):
    with open(filepath, encoding=encoding or "utf-8") as csvfile:
        log.debug("reading point-sources from csv-file")
        df = pd.read_csv(
            csvfile,
            sep=";",
            skip_blank_lines=True,
            comment="#",
            dtype=np._str,
        )
        for col in REQUIRED_COLUMNS_GRID:
            if col not in df.columns:
                raise ImportError(f"Missing required column '{col}'")
    return df


def read_xlsx(filepath):
    try:
        workbook = load_workbook(filename=filepath, data_only=True, read_only=True)
    except Exception as exc:
        raise ImportError(f"could not read workbook: {exc}")
    if "GridSource" not in workbook:
        raise ImportError("no 'GridSource' sheet found")

    worksheet = workbook["GridSource"]
    data = worksheet.values
    df = worksheet_to_dataframe(data)
    df = df.astype(dtype="string")
    workbook.close()
    return df


def read_import_file(filepath, encoding=None):
    """read import file."""
    if filepath.suffix == ".csv":
        df = read_csv(filepath, encoding=encoding)
    elif filepath.suffix == ".xlsx":
        df = read_xlsx(filepath)
    else:
        raise ImportError("only xlsx and csv files are supported for import")
    if "name" not in df.columns:
        raise ImportError("Missing column 'name' for in GridSource sheet")
    df = df.set_index("name")
    return df


def validate_gridsources(df, timevars, code_sets, raster_names, datadir):
    """validate grid-sources in dataframe but do not write to database.
    returns (rasters, messages)
    where rasters is a nested dict with all gridsource rasters
    and messages is a list of all validation error messages.
    """
    row_nr = 2
    rasters = {}
    messages = []
    act_cols = get_activity_rate_columns(df)
    subst_cols = get_substance_emission_columns(df)
    for _, row in df.iterrows():
        row_dict = nan2None(row.to_dict())
        messages += validate_activitycodes(row_dict, code_sets, row_nr=row_nr)
        messages += validate_timevar(row_dict, timevars, row_nr=row_nr)
        messages += validate_unit(row_dict, row_nr)
        for col in filter(lambda x: row_dict[x] is not None, subst_cols):
            subst_slug = col[6:]
            messages += validate_raster(
                row_dict, raster_names, datadir, rasters, row_nr, subst_slug
            )
            messages += validate_emission(row_dict, row_nr, subst_slug)
            # if sum is specified instead of an emission total, the emission value
            # is calculated as the sum of the emission raster
            if row_dict[col] == "sum" and row_dict["path"] is None:
                messages.append(
                    with_rownr_and_substance(
                        "raster path required for emission specified by 'sum'",
                        row_nr,
                        subst_slug,
                    )
                )
        for col in filter(lambda x: row_dict[x] is not None, act_cols):
            act_name = col[4:].strip()
            messages += validate_raster(
                row_dict, raster_names, datadir, rasters, row_nr, subst_slug
            )
            messages += validate_activity(row_dict, row_nr, act_name)
            # if sum is specified instead of an emission total, the emission value
            # is calculated as the sum of the emission raster
            if row_dict[col] == "sum" and row_dict["path"] is None:
                messages.append(
                    with_rownr_and_substance(
                        "raster path required for activity rate specified by 'sum'",
                        row_nr,
                        act_name,
                    )
                )
        row_nr += 1
    return rasters, messages


def create_or_update_rasters(rasters, raster_names):
    """
    Write all rasters with a path specified to the database.
    Existing rasters will be replaced.
    """
    for raster_name, raster_data in rasters.items():
        if raster_data["path"] is not None:
            if raster_name in raster_names:
                drop_gridsource_raster(raster_name)
            with rio.open(raster_data["path"]) as raster:
                write_gridsource_raster(raster, raster_name)


def import_gridsources(filepath, encoding=None):
    """validate and/or import grid-sources from file."""

    substances = cache_queryset(Substance.objects.all(), "slug")
    timevars = cache_queryset(Timevar.objects.all(), "name")
    code_sets = cache_codesets()
    activities = cache_queryset(Activity.objects.all(), "name")
    raster_names = list_gridsource_rasters()
    datadir = dirname(filepath)

    try:
        df = read_import_file(filepath, encoding)
    except ImportError as err:
        return {}, [f"{err}"]

    messages = []
    messages += validate_columns(
        df,
        REQUIRED_COLUMNS_GRID,
        substances=substances,
        activities=activities,
        code_sets=code_sets,
    )
    if len(messages) > 0:
        messages += ["Could not validate gridsources, due to error in columns."]
        return {}, messages

    row_nr = 2
    rasters, messages_sources = validate_gridsources(
        df, timevars, code_sets, raster_names, datadir
    )
    messages += messages_sources
    if len(messages) > 0:
        return {}, messages

    create_or_update_rasters(rasters, raster_names)
    nr_created_sources = 0
    nr_updated_sources = 0

    subst_cols = get_substance_emission_columns(df)
    act_cols = get_activity_rate_columns(df)
    for name, row in df.iterrows():
        row_dict = nan2None(row.to_dict())
        src, created = GridSource.objects.get_or_create(name=name)
        if created:
            nr_created_sources += 1
        else:
            nr_updated_sources += 1
        # set tags
        tag_keys = [key for key in row_dict.keys() if key.startswith("tag:")]
        src.tags = {
            key[4:]: row_dict[key] for key in tag_keys if row_dict[key] is not None
        }
        validate_activitycodes(row_dict, code_sets, row_nr, src)
        validate_timevar(row_dict, timevars, row_nr, src)
        src.save()

        # remove any existing emissions
        if not created:
            src.substances.all().delete()
            src.activities.all().delete()

        for col in filter(lambda x: row_dict[x] is not None, subst_cols):
            subst = col[6:]
            # if sum is specified instead of an emission total,
            # the emission value is calculated as the sum of the raster
            rname, rpath = data_to_raster(
                row_dict["rastername"], row_dict["path"], datadir, subst
            )
            emis = {"substance": substances[subst], "raster": rname}
            emis_value = row_dict[col]
            unit = row_dict["emission_unit"]
            if emis_value == "sum":
                emis["value"] = emission_unit_to_si(rasters[rname]["sum"], unit)
            else:
                emis["value"] = emission_unit_to_si(float(emis_value), unit)
            src.substances.create(**emis)

        for col in filter(lambda x: row_dict[x] is not None, act_cols):
            activity_name = col[4:]
            rname, rpath = data_to_raster(
                row_dict["rastername"], row_dict["path"], datadir, subst
            )
            emis = {"activity": activities[activity_name], "raster": rname}
            rate = row_dict[col]
            if rate == "sum":
                emis["rate"] = activity_rate_unit_to_si(
                    rasters[rname]["sum"], emis["activity"].unit
                )
            else:
                emis["rate"] = activity_rate_unit_to_si(
                    float(rate), emis["activity"].unit
                )
            src.activities.create(**emis)

        row_nr += 1
    db_updates = {
        "gridsources": {"updated": nr_updated_sources, "created": nr_created_sources}
    }
    return db_updates, messages
