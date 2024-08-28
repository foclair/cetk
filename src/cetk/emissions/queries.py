"""Functions to create queries for emissions."""

from collections.abc import Sequence
from importlib import resources

from cetk.edb.models import Settings, Substance
from cetk.emissions.filters import (
    create_ef_substance_where_clause,
    create_ids_where_clause,
    create_name_where_clause,
    create_polygon_where_clause,
    create_raster_share_in_polygon_sql,
    create_substance_emis_where_clause,
    create_tag_where_clause,
)


def load_sql(filename):
    return resources.files("cetk.emissions").joinpath(filename).read_text()


def create_source_emis_query(
    sourcetype,
    srid=None,
    name=None,
    ids=None,
    tags=None,
    polygon=None,
    substances=None,
    #    ac1=None,
    #    ac2=None,
    #    ac3=None,
):
    """
        Create sql for emissions grouped by source, timevar & substance

        Emissions are returned in kg/s.

        optional arguments:
            srid: sources will be transformed to this srid, default is inventory srid
            ids: sequence of source id's for which to include sources
            name: filter by source name(accepts regexp)
            tags: filter by tags(specify as dictionary)
            polygon: only include sources within polygon (EWKT or Polygon)
            substances: iterable of substance model instances(default is all)
    #        ac1: iterable of activitycode instances
    #        ac2: iterable of activitycode instances
    #        ac3: iterable of activitycode instances
    """

    sql = load_sql(f"{sourcetype}source_emissions.sql")
    source_filters = []
    if tags is not None:
        source_filters.append(create_tag_where_clause(tags))
    if ids is not None:
        source_filters.append(create_ids_where_clause(ids))
    if name is not None:
        source_filters.append(create_name_where_clause(name))
    if polygon is not None and sourcetype != "grid":
        source_filters.append(create_polygon_where_clause(polygon))
    if len(source_filters) > 0:
        source_filter_sql = "WHERE " + " AND ".join(source_filters)
    else:
        source_filter_sql = ""

    traffic_work = Substance.objects.get(slug="traffic_work")
    if substances is not None:
        emis_subst_filter = " AND " + create_substance_emis_where_clause(substances)
        if sourcetype == "road":
            ef_subst_filter = " AND " + create_ef_substance_where_clause(
                substances + [traffic_work]
            )
        else:
            ef_subst_filter = " AND " + create_ef_substance_where_clause(substances)
    else:
        ef_subst_filter = "AND 1=1"
        emis_subst_filter = ""

    # replace place-holders by generated sql
    sql = sql.format(
        srid=srid,
        source_filters=source_filter_sql,
        ef_substance_filter=ef_subst_filter,
        emis_substance_filter=emis_subst_filter,
        traffic_work_subst_id=traffic_work.id,
    )
    return sql


def create_aggregate_emis_query(
    substances=None,
    sourcetypes=None,
    codeset_index=None,
    polygon=None,
    tags=None,
    name=None,
    point_ids=None,
    area_ids=None,
    grid_ids=None,
    road_ids=None,
    raster_share_in_polygon=None,
):
    sql = load_sql("aggregate_emissions.sql")
    traffic_work_subst_id = Substance.objects.values_list("id", flat=True).get(
        slug="traffic_work"
    )

    if isinstance(substances, Substance):
        substances = [substances]

    sourcetypes = sourcetypes or ("point", "area", "grid", "road")
    if not isinstance(sourcetypes, Sequence):
        sourcetypes = [sourcetypes]

    settings = Settings.get_current()

    # adapt query to group by requested code-set
    if codeset_index is not None:
        if codeset_index not in (1, 2, 3):
            raise ValueError("Invalid code-set index, must be in range 1-3")
        ac_groupby = f"ac{codeset_index},"
        ac_column = f"ac{codeset_index} as activitycode,"
    else:
        ac_groupby = ""
        ac_column = ""

    # general source filters
    source_filters = []
    if tags is not None:
        source_filters.append(create_tag_where_clause(tags))
    if name is not None:
        source_filters.append(create_name_where_clause(name))

    # point source filters
    point_source_filters = source_filters.copy()
    if polygon is not None:
        point_source_filters.append(create_polygon_where_clause(polygon))
    if point_ids is not None:
        point_source_filters.append(create_ids_where_clause(point_ids))
    if "point" not in sourcetypes:
        point_source_filters.append("1=0")

    if len(point_source_filters) > 0:
        point_source_filter_sql = "WHERE " + " AND ".join(point_source_filters)
    else:
        point_source_filter_sql = ""

    # area source filters
    area_source_filters = source_filters.copy()
    if polygon is not None:
        area_source_filters.append(create_polygon_where_clause(polygon))
    if area_ids is not None:
        area_source_filters.append(create_ids_where_clause(area_ids))
    if "area" not in sourcetypes:
        area_source_filters.append("1=0")

    if len(area_source_filters) > 0:
        area_source_filter_sql = "WHERE " + " AND ".join(area_source_filters)
    else:
        area_source_filter_sql = ""

    # road source filters
    road_source_filters = ["sources.aadt > 0"] + source_filters
    if polygon is not None:
        road_source_filters.append(create_polygon_where_clause(polygon))
    if road_ids is not None:
        road_source_filters.append(create_ids_where_clause(road_ids))
    if "road" not in sourcetypes:
        road_source_filters.append("1=0")
    if len(road_source_filters) > 0:
        road_source_filter_sql = "WHERE " + " AND ".join(road_source_filters)
    else:
        road_source_filter_sql = ""

    if substances is not None:
        emis_subst_filter = " AND " + create_substance_emis_where_clause(substances)
        ef_subst_filter = " AND " + create_ef_substance_where_clause(substances)
    else:
        emis_subst_filter = ""
        ef_subst_filter = ""

    # grid source filters
    grid_source_filters = source_filters.copy()

    if grid_ids is not None:
        grid_source_filters.append(create_ids_where_clause(grid_ids))
    if "grid" not in sourcetypes:
        grid_source_filters.append("1=0")
    if len(grid_source_filters) > 0:
        grid_source_filter_sql = "WHERE " + " AND ".join(grid_source_filters)
    else:
        grid_source_filter_sql = ""

    raster_share_sql = create_raster_share_in_polygon_sql(polygon)
    if substances is not None:
        substances_id = [s.id for s in substances]
    else:
        substances_id = [s.id for s in Substance.objects.all()]
    sql = sql.format(
        srid=settings.srid,
        ac_column=ac_column,
        ac_groupby=ac_groupby,
        point_source_filter=point_source_filter_sql,
        area_source_filter=area_source_filter_sql,
        grid_source_filter=grid_source_filter_sql,
        road_source_filter=road_source_filter_sql,
        emis_substance_filter=emis_subst_filter,
        ef_substance_filter=ef_subst_filter,
        raster_share_sql=raster_share_sql,
        traffic_work_subst_id=traffic_work_subst_id,
        substances=substances_id,
    )
    return sql


def create_used_substances_query():
    """
    Create query to retrieve all substances for which there are emissions
    in the inventory
    """
    return load_sql("used_substances.sql")
