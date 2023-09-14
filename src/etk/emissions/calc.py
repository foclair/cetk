"""Calculate emissions."""

import pandas as pd
from django.db import connection

from etk.edb.models import Settings, Substance
from etk.edb.units import emis_conversion_factor_from_si
from etk.emissions.queries import (
    create_aggregate_emis_query,
    create_pointsource_emis_query,
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
    name=None,
    ids=None,
    tags=None,
    polygon=None,
    unit="kg/year",
):
    cur = connection.cursor()
    settings = Settings.get_current()
    if sourcetype == "point":
        # create point source emission view
        sql = create_pointsource_emis_query(
            srid=settings.srid,
            substances=substances,
            name=name,
            ids=ids,
            tags=tags,
            polygon=polygon,
        )
    else:
        raise NotImplementedError("only implemented for point-sources")
    cur.execute(sql)
    df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    df.set_index(["source_id", "substance"], inplace=True)
    df.loc[:, "emis"] *= emis_conversion_factor_from_si(unit)
    return df


def aggregate_emissions(
    substances=None,
    sourcetypes=None,
    codeset=None,
    polygon=None,
    tags=None,
    point_ids=None,
    unit="ton/year",
):

    settings = Settings.get_current()
    codeset_index = None if codeset is None else settings.get_codeset_index(codeset)
    sql = create_aggregate_emis_query(
        substances=substances,
        sourcetypes=sourcetypes,
        codeset_index=codeset_index,
        polygon=polygon,
        tags=tags,
        point_ids=point_ids,
    )
    cur = connection.cursor()
    cur.execute(sql)
    df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    if codeset is not None:
        # add code labels to dataframe
        df.insert(1, "activity", "")
        code_labels = dict(codeset.codes.values_list("code", "label"))
        for ind in df.index:
            code = df.loc[ind, "activitycode"]
            df.loc[ind, "activity"] = code_labels[code]
        # add to index (to remain also after pivoting)
        df.set_index(["activitycode", "activity"], inplace=True)
        df = df.pivot(columns="substance")
    else:
        df.insert(1, "activity", "total")
        df.set_index(["activity"], inplace=True)
        df = df.pivot(columns="substance")

    df *= emis_conversion_factor_from_si(unit)
    df.columns = df.columns.set_names(["quantity", "substance"])
    # df.rename(columns={"emission": f"emission [{unit}]"})
    return df
