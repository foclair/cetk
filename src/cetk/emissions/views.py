"""Create emission calculation views."""

from django.db import connection

from cetk.edb.const import DEFAULT_EMISSION_UNIT
from cetk.edb.models import Settings, Substance
from cetk.edb.units import emis_conversion_factor_from_si
from cetk.emissions.calc import get_used_substances
from cetk.emissions.queries import create_source_emis_query


def make_emission_sql(sourcetype, substances):
    """Create views for pointsource emissions."""
    settings = Settings.get_current()
    # create point source emission view
    sql = create_source_emis_query(
        sourcetype=sourcetype,
        srid=settings.srid,
        substances=substances,
    )
    return sql


def create_emission_view(sourcetype, substances, unit=DEFAULT_EMISSION_UNIT):
    """create emission view with columns source_id, subst1, subst2...substn."""
    sql = make_emission_sql(sourcetype, substances)

    if sourcetype == "road":
        substances = substances.copy()
        substances.append(Substance.objects.get(slug="traffic_work"))

    fac = emis_conversion_factor_from_si(unit)
    source_subst_cols = ",".join(
        f'sum(rec.emis*{fac if s.slug != "traffic_work" else 1.0}) FILTER (WHERE rec.substance_id={s.id}) AS "{s.slug}"'  # noqa
        for s in substances
    )
    view_sql = f"""\
    CREATE VIEW {sourcetype}source_emissions AS
    SELECT source_id,
    {source_subst_cols}
    FROM (
      {sql}
    ) as rec
    GROUP BY source_id
    """
    cur = connection.cursor()
    cur.execute(f"DROP VIEW IF EXISTS {sourcetype}source_emissions")
    cur.execute(view_sql)


def create_emission_table(sourcetype, substances=None, unit=DEFAULT_EMISSION_UNIT):
    """create emission table with columns source_id, subst1, subst2...substn."""

    sql = make_emission_sql(sourcetype, substances)
    fac = emis_conversion_factor_from_si(unit)
    if sourcetype == "road":
        substances = substances.copy()
        substances.append(Substance.objects.get(slug="traffic_work"))

    if substances is None:
        substances = get_used_substances()
    source_subst_cols = ",".join(
        f'sum(rec.emis*{fac if s.slug != "traffic_work" else 1.0}) FILTER (WHERE rec.substance_id={s.id}) AS "{s.slug}"'  # noqa
        for s in substances
    )
    table_sql = (
        f"CREATE TABLE {sourcetype}source_emissions AS SELECT source_id, "
        + ", ".join([f'cast("{s.slug}" as real) as "{s.slug}"' for s in substances])
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
    cur = connection.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {sourcetype}source_emissions")
    # breakpoint()
    cur.execute(table_sql)
    cur.execute(
        f"""
        CREATE INDEX {sourcetype}source_emis_idx
        ON {sourcetype}source_emissions (source_id)
        """
    )
