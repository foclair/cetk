"""Calculate emissions."""

import pandas as pd
from django.db import connection

from cetk.edb.const import DEFAULT_EMISSION_UNIT
from cetk.edb.models import CodeSet, Settings, Substance
from cetk.edb.units import emis_conversion_factor_from_si
from cetk.emissions.queries import (
    create_aggregate_emis_query,
    create_source_emis_query,
    create_used_substances_query,
)


def get_used_substances():
    """return list of substances with emissions or emission factors."""
    sql = create_used_substances_query()
    cur = connection.cursor()
    return [Substance.objects.get(slug=rec[0]) for rec in cur.execute(sql).fetchall()]


def calculate_source_emissions(
    sourcetype,
    substances=None,
    srid=None,
    name=None,
    ids=None,
    tags=None,
    polygon=None,
    unit=DEFAULT_EMISSION_UNIT,
):
    settings = Settings.get_current()
    srid = srid or settings.srid
    sql = create_source_emis_query(
        sourcetype=sourcetype,
        srid=srid,
        substances=substances,
        name=name,
        ids=ids,
        tags=tags,
        polygon=polygon,
    )
    cur = connection.cursor()
    cur.execute(sql)
    return cur


def calculate_source_emissions_df(
    sourcetype,
    substances=None,
    name=None,
    ids=None,
    tags=None,
    polygon=None,
    unit=DEFAULT_EMISSION_UNIT,
):
    cur = calculate_source_emissions(
        sourcetype=sourcetype,
        substances=substances,
        name=name,
        ids=ids,
        tags=tags,
        polygon=polygon,
        unit=unit,
    )
    df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    if sourcetype == "grid":
        df.set_index(["source_id", "substance", "raster"], inplace=True)
    elif sourcetype == "road":
        df.set_index(["source_id", "substance", "vehicle"], inplace=True)
        traffic_work = df.loc[(slice(None), "traffic_work"), :]["emis"]
        traffic_work.name = "traffic_work"
        traffic_work.index = traffic_work.index.droplevel("substance")
        df.drop(level="substance", labels=["traffic_work"], inplace=True)
        df = df.join(traffic_work)
        df = df.reorder_levels(["source_id", "substance", "vehicle"])
    else:
        df.set_index(["source_id", "substance"], inplace=True)
    df.loc[:, "emis"] *= emis_conversion_factor_from_si(unit)
    df.sort_index(inplace=True)
    return df


def aggregate_emissions(
    substances=None,
    sourcetypes=None,
    codeset=None,
    polygon=None,
    tags=None,
    point_ids=None,
    area_ids=None,
    unit=DEFAULT_EMISSION_UNIT,
    name=None,
):

    settings = Settings.get_current()
    codeset_index = None if codeset is None else settings.get_codeset_index(codeset)
    sql = create_aggregate_emis_query(
        substances=substances,
        sourcetypes=sourcetypes,
        codeset_index=codeset_index,
        polygon=polygon,
        name=name,
        tags=tags,
        point_ids=point_ids,
        area_ids=area_ids,
    )
    cur = connection.cursor()
    cur.execute(sql)
    df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    if codeset is not None:
        try:
            codeset = CodeSet.objects.get(slug=codeset)
        except CodeSet.DoesNotExist:
            raise ValueError(f"Codeset {codeset} does not exist, choose valid slug.")
    if codeset is not None:
        # add code labels to dataframe
        df.insert(1, "activity", "")
        code_labels = dict(codeset.codes.values_list("code", "label"))
        for ind in df.index:
            code = df.loc[ind, "activitycode"]
            if code is not None:
                df.loc[ind, "activity"] = code_labels[code]
        # add to index (to remain also after pivoting)
        df.set_index(["activitycode", "activity"], inplace=True)
        df = df.pivot(columns="substance")
    else:
        df.insert(1, "activity", "total")
        df.set_index(["activity"], inplace=True)
        df = df.pivot(columns="substance")
    df.columns = df.columns.set_names(["quantity", "substance"])
    if "traffic_work" in df.columns.get_level_values("substance"):
        # set quantity to traffic if substance is traffic_work
        df.columns = pd.MultiIndex.from_tuples(
            [
                (q, s) if s != "traffic_work" else ("traffic", "veh*km")
                for q, s in df.columns
            ]
        )
        df.columns.names = ["quantity", "substance"]
        # convert from veh*m to veh*km
        df.loc[:, ("traffic", "veh*km")] /= 1000.0

    # convert emission unit
    if len(df) > 0:
        df.loc[:, ("emission", slice(None))] *= emis_conversion_factor_from_si(unit)
    return df
