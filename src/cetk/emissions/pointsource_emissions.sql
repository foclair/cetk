/*
Calculate emissions, optionally filtered by a polygon.
Substance emissions and activity emissions are calculated separately and
are then aggregated by source, raster and substance.
 */
WITH sources as (
  SELECT sources.id as source_id, name as source_name, tags, timevar_id,
       ac1.code as ac1, ac2.code as ac2, ac3.code as ac3,
       ST_Transform(geom, {srid}) as geom
  FROM edb_pointsource as sources
       LEFT JOIN edb_activitycode as ac1 ON ac1.id = sources.activitycode1_id
       LEFT JOIN edb_activitycode as ac2 ON ac2.id = sources.activitycode2_id
       LEFT JOIN edb_activitycode as ac3 ON ac3.id = sources.activitycode3_id
       {source_filters}
)
SELECT sources.source_id, aggr_emis.substance_id, source_name, ac1, ac2, ac3,
  sources.geom as geom,
  ST_AsText(sources.geom) as wkt,
  sources.timevar_id, substances.slug as substance, aggr_emis.emis
FROM
(
  SELECT substance_id, source_id, SUM(emis) as emis
  FROM
  (
    SELECT
      sources.source_id,
      emis.substance_id as substance_id,
      emis.value as emis
    FROM edb_pointsourcesubstance as emis
	 JOIN sources ON sources.source_id = emis.source_id
     WHERE emis.value > 0
	 {emis_substance_filter}
    UNION ALL
    SELECT
      sources.source_id,
      ef_subst.substance_id as substance_id,
      act.rate * ef_subst.factor as emis
      FROM edb_pointsourceactivity as act
	   JOIN sources ON act.source_id=sources.source_id
	   JOIN (
	     SELECT *
	       FROM edb_emissionfactor as ef
		    JOIN edb_activity ON edb_activity.id=ef.activity_id
	      WHERE ef.factor > 0
		    {ef_substance_filter}
	   ) as ef_subst ON act.activity_id=ef_subst.activity_id
     WHERE act.rate > 0
  ) all_emis
   GROUP BY substance_id, source_id
) aggr_emis
  JOIN sources ON aggr_emis.source_id = sources.source_id
  JOIN substances ON aggr_emis.substance_id = substances.id
 ORDER BY sources.source_id
