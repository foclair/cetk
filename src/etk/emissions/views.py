"""Create emission calculation views."""

from django.db import connection

from etk.edb.models import Settings
from etk.edb.units import emis_conversion_factor_from_si
from etk.emissions.queries import create_source_emis_query


def create_pointsource_emis_view(substances, unit="kg/year"):
    """Create views for pointsource emissions."""
    settings = Settings.get_current()
    cur = connection.cursor()
    fac = emis_conversion_factor_from_si(unit)
    source_subst_cols = ",".join(
        f'sum(rec.emis*{fac}) FILTER (WHERE rec.substance_id={s.id}) AS "{s.slug}"'  # noqa
        for s in substances
    )

    # create point source emission view
    sql = create_source_emis_query(
        sourcetype="point",
        srid=settings.srid,
        substances=substances,
    )
    cur.execute("DROP VIEW IF EXISTS pointsource_emissions")
    view_sql = f"""\
CREATE VIEW pointsource_emissions AS
  SELECT source_id,
    {source_subst_cols}
  FROM (
{sql}
  ) as rec
  GROUP BY source_id"""
    cur.execute(view_sql)


def create_pointsource_emis_table(substances, unit="kg/year"):
    """Create views for pointsource emissions."""
    settings = Settings.get_current()
    cur = connection.cursor()
    fac = emis_conversion_factor_from_si(unit)
    source_subst_cols = ",".join(
        f'sum(rec.emis*{fac}) FILTER (WHERE rec.substance_id={s.id}) AS "{s.slug}"'  # noqa
        for s in substances
    )

    # create point source emission view
    sql = create_source_emis_query(
        sourcetype="point",
        srid=settings.srid,
        substances=substances,
    )
    cur.execute("DROP TABLE IF EXISTS pointsource_emissions")
    table_sql = "CREATE TABLE pointsource_emissions AS SELECT source_id, " + ", ".join(
        [f'cast("{s.slug}" as real) as "{s.slug}"' for s in substances]
    )
    table_sql += f"""
  FROM (
     SELECT source_id,
      {source_subst_cols}
      FROM (
      {sql}
    ) as rec
  GROUP BY source_id
  )
"""
    cur.execute(table_sql)
    cur.execute(
        "CREATE INDEX pointsource_emis_idx ON pointsource_emissions (source_id)"
    )


def create_areasource_emis_view(substances, unit="kg/year"):
    """Create views for areasource emissions."""
    settings = Settings.get_current()
    cur = connection.cursor()
    fac = emis_conversion_factor_from_si(unit)
    source_subst_cols = ",".join(
        f'sum(rec.emis*{fac}) FILTER (WHERE rec.substance_id={s.id}) AS "{s.slug}"'  # noqa
        for s in substances
    )

    # create area source emission view
    sql = create_source_emis_query(
        sourcetype="area",
        srid=settings.srid,
        substances=substances,
    )
    cur.execute("DROP VIEW IF EXISTS areasource_emissions")
    view_sql = f"""\
CREATE VIEW areasource_emissions AS
  SELECT source_id,
    {source_subst_cols}
  FROM (
{sql}
  ) as rec
  GROUP BY source_id"""
    cur.execute(view_sql)


def create_areasource_emis_table(substances, unit="kg/year"):
    """Create views for areasource emissions."""
    settings = Settings.get_current()
    cur = connection.cursor()
    fac = emis_conversion_factor_from_si(unit)
    source_subst_cols = ",".join(
        f'sum(rec.emis*{fac}) FILTER (WHERE rec.substance_id={s.id}) AS "{s.slug}"'  # noqa
        for s in substances
    )

    # create area source emission view
    sql = create_source_emis_query(
        sourcetype="area",
        srid=settings.srid,
        substances=substances,
    )
    cur.execute("DROP TABLE IF EXISTS areasource_emissions")
    table_sql = "CREATE TABLE areasource_emissions AS SELECT source_id, " + ", ".join(
        [f'cast("{s.slug}" as real) as "{s.slug}"' for s in substances]
    )
    table_sql += f"""
  FROM (
     SELECT source_id,
      {source_subst_cols}
      FROM (
      {sql}
    ) as rec
  GROUP BY source_id
  )
"""
    cur.execute(table_sql)
    cur.execute("CREATE INDEX areasource_emis_idx ON areasource_emissions (source_id)")
