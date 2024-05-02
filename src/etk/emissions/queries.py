"""Functions to create queries for emissions."""

from collections.abc import Sequence
from importlib import resources

from etk.edb.models import Settings, Substance
from etk.emissions.filters import (
    create_ef_substance_where_clause,
    create_ids_where_clause,
    create_name_where_clause,
    create_polygon_where_clause,
    create_raster_share_in_polygon_sql,
    create_substance_emis_where_clause,
    create_tag_where_clause,
    create_veh_ef_substance_where_clause,
)


def load_sql(filename):
    return resources.files("etk.emissions").joinpath(filename).read_text()


def create_source_emis_query(
    sourcetype="point",
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

    if substances is not None:
        ef_subst_filter = " AND " + create_ef_substance_where_clause(substances)
        emis_subst_filter = " AND " + create_substance_emis_where_clause(substances)
    else:
        ef_subst_filter = ""
        emis_subst_filter = ""

    # replace place-holders by generated sql
    sql = sql.format(
        srid=srid,
        source_filters=source_filter_sql,
        ef_substance_filter=ef_subst_filter,
        emis_substance_filter=emis_subst_filter,
    )
    return sql


def create_aggregate_emis_query(
    substances=None,
    sourcetypes=None,
    codeset_index=None,
    polygon=None,
    tags=None,
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

    # point source filters
    point_source_filters = list(*source_filters)
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
    area_source_filters = list(*source_filters)
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
    road_source_filters = list(*source_filters)
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
    grid_source_filters = list(*source_filters)

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
    # breakpoint()
    return sql


def create_used_substances_query():
    """
    Create query to retrieve all substances for which there are emissions
    in the inventory
    """
    return load_sql("used_substances.sql")


def create_road_emis_query(
    srid,
    ids=None,
    name=None,
    tags=None,
    polygon=None,
    substances=None,
    ac1=None,
    ac2=None,
    ac3=None,
    min_aadt=0,
    tolerance=1.0,
):
    """Create sql for road emissions.

    returns(query, params)

    query gives emissions in kg/s.

    args:
        srid: sources will be transformed to this srid
    optional:
        ids: sequence of source id's for which to include sources
        name: filter by source name(accepts regexp)
        tags: filter by tags(specify as dictionary)
        polygon: polygon in Polygon or EWKT format
        substances: iterable of substance model instances(default is all)
        ac1: iterable of activitycode instances
        ac2: iterable of activitycode instances
        ac3: iterable of activitycode instances
        min_aadt: only include roads with aadt above this value
        tolerance: geometry tolerance (default is 1.0m)
    """

    sql = load_sql("road_emissions.sql")
    traffic_work_subst_id = Substance.objects.values_list("id", flat=True).get(
        slug="traffic_work"
    )
    params = {
        "srid": srid,
        "min_aadt": min_aadt,
    }

    # ac_filter, ac_params = create_activitycode_where_clauses(
    #     ac1, ac2, ac3, first_cond=False
    # )
    tags_filter, tags_params = create_tag_where_clause(tags)
    ids_filter, ids_params = create_ids_where_clause(ids)
    name_filter, name_params = create_name_where_clause(name)
    ef_subst_filter, ef_subst_params = create_veh_ef_substance_where_clause(substances)
    if len(ef_subst_filter) > 4:
        # filter should not start with "AND"
        ef_subst_filter = ef_subst_filter[4:]
    emis_subst_filter, emis_subst_params = create_substance_emis_where_clause(
        substances
    )
    polygon_filter, polygon_params = create_polygon_where_clause("road", polygon)

    # params.update(ac_params)
    params.update(tags_params)
    params.update(name_params)
    params.update(ids_params)
    params.update(ef_subst_params)
    params.update(emis_subst_params)
    params.update(polygon_params)

    # replace place-holders by generated sql
    sql = sql.format(
        ac_filter="",  # ac_filter,
        id_filter=ids_filter,
        name_filter=name_filter,
        tag_filter=tags_filter,
        ef_substance_filter=ef_subst_filter,
        polygon_filter=polygon_filter,
        tolerance=tolerance,
        traffic_work_subst_id=traffic_work_subst_id,
    )
    return sql, params
