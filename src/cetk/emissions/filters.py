"""Functions to dynamically create SQL where clauses for emission calculations."""

from collections.abc import Iterable

from django.contrib.gis.geos import Polygon

from cetk.edb.models import Settings, get_gridsource_raster, list_gridsource_rasters


def create_name_where_clause(name):
    """create SQL to filter sources by source name"""
    return f"sources.name = '{name}'"


def create_ids_where_clause(ids):
    """create SQL to filter sources by source id's
    args:
        ids: iterable of source id's
    """
    source_ids = ",".join(ids)
    return f"sources.id IN ({source_ids})"


def create_polygon_where_clause(polygon):
    """create SQL to filter sources by polygon
    args:
        sourcetype: "grid", "point" or "area"
        polygon: a polygon in Polygon or EWKT-format
    """
    polygon_ewkt = polygon.ewkt if isinstance(polygon, Polygon) else polygon
    settings = Settings.get_current()
    sql = f"""\
       ST_Intersects(
         ST_transform(sources.geom, {settings.srid}),
         ST_Transform(GeomFromEWKT('{polygon_ewkt}'), {settings.srid})
       )
    """
    return sql


def create_tag_where_clause(tags):
    """create SQL to filter sources on tags
    args:
        tags: a dictionary with key value pairs

    To exclude all sources with a specific tag, specify operator as part of value:
    "tag": "!=value"
    """
    conds = []
    for tag, cond in tags.items():
        if cond.startswith("!="):
            val = cond[2:].strip()
            conds.append(
                f"(sources.tags IS NULL OR NOT sources.tags ? {tag} OR sources.tags->>{tag} != {val})"
            )
        else:
            if cond.startswith("="):
                val = cond[1:].strip()
            else:
                val = cond
            conds.append(f"sources.tags->>%{tag} = {val}")
    return " AND ".join(conds)


def create_ef_substance_where_clause(substances):
    """filter to only include specified substances.
    args:
        substances: list of Substance model instances
    """

    if not isinstance(substances, Iterable):
        substance_ids = str(substances.id)
    else:
        substance_ids = ",".join([str(s.id) for s in substances])
    return f"ef.substance_id IN ({substance_ids})"


def create_activitycode_where_clauses(ac1, ac2, ac3):
    """filter to only include specified activitycodes.
    args:
        ac1: iterable with activitycode instances
        ac2: iterable with activitycode instances
        ac3: iterable with activitycode instances

    returns sql, params

    returned where clause includes place-holders for codes named:
    ac1_code_1, ac1_code_2, ac2_code_1, ac2_code_2 etc.
    """

    sql_list = []  # return list of sql strings

    # ac1, ac2, ac3 can be either a single code or an iterable
    if ac1 is not None:
        if not isinstance(ac1, Iterable):
            ac1 = [ac1]
        else:
            ac1 = list(ac1)

        sql = " OR ".join([f"(ac1.code LIKE '{ac.code}')" for ac in ac1])
        sql_list.append(sql)

    if ac2 is not None:
        if not isinstance(ac2, Iterable):
            ac2 = [ac2]
        else:
            ac2 = list(ac2)

        sql = " OR ".join([f"(ac2.code LIKE '{ac.code}')" for ac in ac2])
        sql_list.append(sql)

    if ac3 is not None:
        if not isinstance(ac3, Iterable):
            ac3 = [ac3]
        else:
            ac3 = list(ac3)

        sql = " OR ".join([f"(ac3.code LIKE '{ac.code}')" for ac in ac3])
        sql_list.append(sql)

    return sql_list


def create_substance_emis_where_clause(substances):
    """filter to only include emissions of specified substances.
    args:
        substances: list of Substance model instances
    """
    substance_ids = (
        str(substances.id)
        if not isinstance(substances, Iterable)
        else ",".join([str(s.id) for s in substances])
    )
    return f"emis.substance_id IN ({substance_ids})"


def create_raster_share_in_polygon_sql(polygon):
    """create inline sql table for fractions of rasters inside polygon."""
    rasters = {}
    for raster_name in list_gridsource_rasters():
        if polygon is not None:
            raster_data, metadata = get_gridsource_raster(raster_name, clip_by=polygon)
            rasters[raster_name] = raster_data.sum()
        else:
            rasters[raster_name] = 1.0
    if len(rasters) > 0:
        sql = "\nUNION ALL\n".join(
            f"SELECT '{name}' as name, {total} as total"
            for name, total in rasters.items()
        )
    else:
        sql = """SELECT "dummy" as name, 1.0 as total"""
    return sql
