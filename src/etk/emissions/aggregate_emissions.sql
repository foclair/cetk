WITH
point_source as (
    SELECT sources.id as source_id, timevar_id,
      ST_Transform(geom, {srid}) as geom,
      ac1.code as ac1, ac2.code as ac2, ac3.code as ac3
    FROM edb_pointsource as sources
    LEFT JOIN edb_activitycode as ac1 ON ac1.id = sources.activitycode1_id
    LEFT JOIN edb_activitycode as ac2 ON ac2.id = sources.activitycode2_id
    LEFT JOIN edb_activitycode as ac3 ON ac3.id = sources.activitycode3_id
    {point_source_filter}
),
ef_subst as (
  SELECT * FROM edb_emissionfactor as ef
  JOIN edb_activity ON edb_activity.id=ef.activity_id
  WHERE ef.factor > 0
    {ef_substance_filter}
),
area_source as (
    SELECT sources.id as source_id, timevar_id,
      ST_Transform(geom, {srid}) as geom,
      ac1.code as ac1, ac2.code as ac2, ac3.code as ac3
    FROM edb_areasource as sources
    LEFT JOIN edb_activitycode as ac1 ON ac1.id = sources.activitycode1_id
    LEFT JOIN edb_activitycode as ac2 ON ac2.id = sources.activitycode2_id
    LEFT JOIN edb_activitycode as ac3 ON ac3.id = sources.activitycode3_id
    {area_source_filter}
),
point_emis as (
  SELECT aggr_emis.substance_id, ac1, ac2, ac3, aggr_emis.emis
  FROM
    (
      SELECT substance_id, source_id, sum(emis) as emis
      FROM
        (
          SELECT
            point_source.source_id,
            emis.substance_id as substance_id,
            emis.value as emis
          FROM edb_pointsourcesubstance as emis
          JOIN point_source ON point_source.source_id=emis.source_id
          WHERE emis.value > 0
		{emis_substance_filter}
          UNION ALL
          SELECT
            point_source.source_id,
            ef_subst.substance_id as substance_id,
            act.rate * ef_subst.factor as emis
            FROM edb_pointsourceactivity as act
		 JOIN point_source ON act.source_id=point_source.source_id
		 JOIN ef_subst ON act.activity_id=ef_subst.activity_id
           WHERE act.rate > 0
        ) all_emis
      GROUP BY substance_id, source_id
    ) aggr_emis
  JOIN point_source ON aggr_emis.source_id = point_source.source_id
),
area_emis as (
  SELECT aggr_emis.substance_id, ac1, ac2, ac3, aggr_emis.emis
  FROM
    (
      SELECT substance_id, source_id, sum(emis) as emis
      FROM
        (
          SELECT
            area_source.source_id,
            emis.substance_id as substance_id,
            emis.value as emis
          FROM edb_areasourcesubstance as emis
          JOIN area_source ON area_source.source_id=emis.source_id
          WHERE emis.value > 0
		{emis_substance_filter}
          UNION ALL
          SELECT
            area_source.source_id,
            ef_subst.substance_id as substance_id,
            act.rate * ef_subst.factor as emis
            FROM edb_areasourceactivity as act
		 JOIN area_source ON act.source_id=area_source.source_id
		 JOIN ef_subst ON act.activity_id=ef_subst.activity_id
           WHERE act.rate > 0
        ) all_emis
      GROUP BY substance_id, source_id
    ) aggr_emis
  JOIN point_source ON aggr_emis.source_id = point_source.source_id
)
SELECT {ac_column} substances.slug as substance, sum(emis) as emission
FROM
  (
    SELECT * FROM area_emis
    UNION ALL
    SELECT * FROM point_emis
  ) as all_emis
JOIN substances ON substance_id = substances.id
GROUP BY {ac_groupby} substances.slug
