"""Functions to dynamically create SQL where clauses for emission calculations."""

from collections.abc import Iterable

from django.contrib.gis.geos import Polygon


def create_name_where_clause(name, sql):
    """create SQL to filter sources by source name"""
    return "sources.name ~ {name}"


def create_ids_where_clause(ids):
    """create SQL to filter sources by source id's
    args:
        ids: iterable of source id's
    """
    source_ids = ",".join(map(int, ids))
    return f"sources.id IN ({source_ids})"


def create_polygon_where_clause(sourcetype, polygon):
    """create SQL to filter sources by polygon
    args:
        sourcetype: "grid", "point" or "area"
        polygon: a polygon in Polygon or EWKT-format
    """
    if isinstance(polygon, str):
        polygon_ewkt = polygon
    elif isinstance(polygon, Polygon):
        polygon_ewkt = polygon.ewkt
    if sourcetype == "grid":
        # intersection of geom with polygon
        # translate polygon to same srid as grid-source
        sql = f"""\
        ST_Intersects(
          ST_SetSRID(raster.geom, raster.srid),
          ST_Transform(ST_GeomFromEWKT({polygon_ewkt}), raster.srid)
        )
        """
    else:
        sql = f"""\
        ST_Intersects(
          sources.geom,
          ST_Transform(ST_GeomFromEWKT({polygon_ewkt}), 4326)
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
                f"(sources.tags IS NULL OR NOT sources.tags ? {tag} OR sources.tags->>{tag} != {val})"  # noqa
            )
        else:
            if cond.startswith("="):
                val = cond[1:].strip()
            else:
                val = cond
            conds.append(f"sources.tags->>%{tag} = {val}")
    return " AND ".join(conds)


def create_veh_ef_substance_where_clause(substances):
    if not isinstance(substances, Iterable):
        substance_ids = str(substances.id)
    else:
        substance_ids = ",".join([str(s.id) for s in substances])
    return f"veh_fuel_ef.substance_id IN ({substance_ids})"


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


# def create_activitycode_where_clauses(ac1, ac2, ac3, first_cond=True):
#     """filter to only include specified activitycodes.
#     args:
#         ac1: iterable with activitycode instances
#         ac2: iterable with activitycode instances
#         ac3: iterable with activitycode instances

#     kwargs:
#         first_cond: True adds WHERE, False adds AND

#     returns sql, params

#     returned where clause includes place-holders for codes named:
#     ac1_code_1, ac1_code_2, ac2_code_1, ac2_code_2 etc.
#     """

#     # ac1, ac2, ac3 can be either a single code or an iterable
#     sql = ""
#     params = {}
#     if ac1 is not None:
#         if not isinstance(ac1, Iterable):
#             ac1 = [ac1]
#         else:
#             ac1 = list(ac1)
#         if not first_cond:
#             sql += " AND ("
#         else:
#             sql += " WHERE ("
#             first_cond = False
#         sql += " OR ".join(
#             [f"ac1.code <@ %(ac1_code_{i})s" for i, ac in enumerate(ac1)]
#         )
#         sql += ")"
#         params.update({f"ac1_code_{i}": ac.code for i, ac in enumerate(ac1)})

#     if ac2 is not None:
#         if not isinstance(ac2, Iterable):
#             ac2 = [ac2]
#         else:
#             ac2 = list(ac2)
#         if not first_cond:
#             sql += " AND ("
#         else:
#             sql += " WHERE ("
#             first_cond = False
#         sql += " OR ".join(
#             [f"ac2.code <@ %(ac2_code_{i})s" for i, ac in enumerate(ac2)]
#         )
#         sql += ")"
#         params.update({f"ac2_code_{i}": ac.code for i, ac in enumerate(ac2)})

#     if ac3 is not None:
#         if not isinstance(ac3, Iterable):
#             ac3 = [ac3]
#         else:
#             ac3 = list(ac3)

#         if not first_cond:
#             sql += " AND ("
#         else:
#             sql += " WHERE ("
#             first_cond = False

#         sql += " OR ".join(
#             [f"ac3.code <@ %(ac3_code_{i})s" for i, ac in enumerate(ac3)]
#         )
#         sql += ")"
#         params.update({f"ac3_code_{i}": ac.code for i, ac in enumerate(ac3)})

#     return sql, params


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
