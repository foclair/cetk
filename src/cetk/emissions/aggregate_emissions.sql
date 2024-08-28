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
grid_source as (
    SELECT sources.id as source_id, timevar_id,
      ac1.code as ac1, ac2.code as ac2, ac3.code as ac3
    FROM edb_gridsource as sources
    LEFT JOIN edb_activitycode as ac1 ON ac1.id = sources.activitycode1_id
    LEFT JOIN edb_activitycode as ac2 ON ac2.id = sources.activitycode2_id
    LEFT JOIN edb_activitycode as ac3 ON ac3.id = sources.activitycode3_id
    {grid_source_filter}
),
road_source as (
    SELECT sources.id as source_id, name as source_name, tags,
      ST_Transform(geom, {srid}) as geom, aadt, heavy_vehicle_share,
      congestion_profile_id,nolanes,speed,width,slope,roadclass_id,fleet_id
    FROM edb_roadsource as sources
    {road_source_filter}
),
fleet_veh as (
  SELECT
    fm.fleet_id,
    rc.id as roadclass_id,
    fm.vehicle_id as vehicle_id,
    veh.isheavy,
    timevar_id,
    coldstart_timevar_id,
    fm.fraction as fraction,
    fm.coldstart_fraction,
    fleet.default_heavy_vehicle_share,
    substance_id,
    freeflow_ef,
    heavy_ef,
    saturated_ef,
    stopngo_ef,
    coldstart_ef,
    ef.ac1,
    ef.ac2,
    ef.ac3
  FROM
    (
      SELECT
        fleet_id,
	fm.id as fleetmember_id,
        veh_ef.traffic_situation_id as traffic_situation,
        fm.vehicle_id,
        veh_ef.substance_id,
        ac1.code as ac1,
        ac2.code as ac2,
        ac3.code as ac3,
        sum(fmf.fraction * veh_ef.freeflow) as freeflow_ef,
        sum(fmf.fraction * veh_ef.heavy) as heavy_ef,
        sum(fmf.fraction * veh_ef.saturated) as saturated_ef,
        sum(fmf.fraction * veh_ef.stopngo) as stopngo_ef,
        sum(fmf.fraction * veh_ef.coldstart) as coldstart_ef
      FROM edb_fleetmember fm
      JOIN edb_fleetmemberfuel as fmf ON fm.id=fmf.fleet_member_id
      JOIN edb_vehicleef as veh_ef
        ON fm.vehicle_id = veh_ef.vehicle_id
        AND fmf.fuel_id = veh_ef.fuel_id
      JOIN edb_fleet as fleet ON fm.fleet_id = fleet.id
      JOIN edb_vehiclefuelcomb as vfc
        ON fm.vehicle_id = vfc.vehicle_id
        AND fmf.fuel_id = vfc.fuel_id
      LEFT JOIN edb_activitycode as ac1 ON vfc.activitycode1_id=ac1.id
      LEFT JOIN edb_activitycode as ac2 ON vfc.activitycode2_id=ac2.id
      LEFT JOIN edb_activitycode as ac3 ON vfc.activitycode3_id=ac3.id
      WHERE veh_ef.substance_id != {traffic_work_subst_id}
      GROUP BY fm.fleet_id, fm.id, veh_ef.traffic_situation_id,
        fm.vehicle_id, veh_ef.substance_id, ac1.code, ac2.code, ac3.code
      UNION
      SELECT
	fleet_id,
	fm.id as fleetmember_id,
	ts.id as traffic_situation,
	fm.vehicle_id,
	{traffic_work_subst_id} as substance_id,
	ac1.code as ac1,
	ac2.code as ac2,
	ac3.code as ac3,
	1.0 as freeflow_ef,
	1.0 as saturated_ef,
	1.0 as congested_ef,
	1.0 as stopngo_ef,
	0.0 as coldstart_ef
      FROM edb_fleetmember fm
      JOIN edb_fleetmemberfuel as fmf ON fm.id=fmf.fleet_member_id
      CROSS JOIN edb_trafficsituation as ts
      JOIN edb_fleet as fleet ON fm.fleet_id = fleet.id
      JOIN edb_vehiclefuelcomb as vfc on fm.vehicle_id = vfc.vehicle_id
      AND fmf.fuel_id = vfc.fuel_id
      LEFT JOIN edb_activitycode as ac1 ON vfc.activitycode1_id=ac1.id
      LEFT JOIN edb_activitycode as ac2 ON vfc.activitycode2_id=ac2.id
      LEFT JOIN edb_activitycode as ac3 ON vfc.activitycode3_id=ac3.id
    ) as ef
    JOIN edb_fleetmember fm ON ef.fleetmember_id = fm.id
    JOIN edb_vehicle veh ON ef.vehicle_id=veh.id
    LEFT JOIN edb_roadclass rc
      ON ef.traffic_situation=rc.traffic_situation_id
    JOIN edb_fleet as fleet ON fm.fleet_id = fleet.id
   WHERE  (
     ef.freeflow_ef != 0 OR ef.coldstart_ef != 0 OR
     ef.stopngo_ef != 0 OR ef.heavy_ef != 0 OR ef.saturated_ef != 0
   ) {ef_substance_filter}
),
/*
Calculate weight of each LOS (Level Of Service) for all valid combinations
of congestion profile and timevar. A custom sqlite function in python called
condition_weight is used (see cetk.edb.signals).
*/
congestion as (
    SELECT c.id as congestion_profile_id, t.id as timevar_id,
      condition_weight(c.traffic_condition, t.typeday, t.typeday_sum, 1) as freeflow_share,
      condition_weight(c.traffic_condition, t.typeday, t.typeday_sum, 2) as heavy_share,
      condition_weight(c.traffic_condition, t.typeday, t.typeday_sum, 3) as saturated_share,
      condition_weight(c.traffic_condition, t.typeday, t.typeday_sum, 4) as stopngo_share
    FROM (
      SELECT DISTINCT congestion_profile_id, timevar_id
      FROM road_source as src
      JOIN edb_fleetmember AS fm ON src.fleet_id = fm.fleet_id
    ) as ct
    JOIN edb_flowtimevar as t ON ct.congestion_profile_id = c.id
    JOIN edb_congestionprofile as c ON ct.timevar_id = t.id
),
road_emis as (
SELECT substance_id, ac1, ac2, ac3,
  road_veh_ef.veh_m_per_sec * (
    freeflow_ef * COALESCE(freeflow_share, 1.0) +
    heavy_ef * COALESCE(heavy_share, 0.0) +
    saturated_ef * COALESCE(saturated_share, 0.0) +
    stopngo_ef * COALESCE(stopngo_share, 0.0) +
    coldstart_ef * coldstart_fraction
  ) as emis
FROM
  (
    SELECT
      fleet_veh.coldstart_fraction,
      congestion.freeflow_share,
      congestion.heavy_share,
      congestion.saturated_share,
      congestion.stopngo_share,
      fleet_veh.substance_id,
      fleet_veh.freeflow_ef,
      fleet_veh.heavy_ef,
      fleet_veh.saturated_ef,
      fleet_veh.stopngo_ef,
      fleet_veh.coldstart_ef,
      fleet_veh.ac1,
      fleet_veh.ac2,
      fleet_veh.ac3,
      (
        CASE
        WHEN fleet_veh.isheavy=TRUE THEN
          COALESCE(
            road_source.heavy_vehicle_share,
            fleet_veh.default_heavy_vehicle_share
          )
        ELSE
          1 - COALESCE(
	    road_source.heavy_vehicle_share,
            fleet_veh.default_heavy_vehicle_share
          )
        END
	* fleet_veh.fraction * road_source.aadt / (3600.0 * 24) * ST_Length(road_source.geom)
      ) as veh_m_per_sec
    FROM road_source
    JOIN fleet_veh
      ON road_source.roadclass_id=fleet_veh.roadclass_id
      AND road_source.fleet_id=fleet_veh.fleet_id
    LEFT JOIN congestion
      ON congestion.congestion_profile_id=road_source.congestion_profile_id
      AND congestion.timevar_id=fleet_veh.timevar_id
  ) as road_veh_ef
),
ef_subst as (
  SELECT * FROM edb_emissionfactor as ef
  JOIN edb_activity ON edb_activity.id=ef.activity_id
  WHERE ef.factor > 0
    {ef_substance_filter}
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
  JOIN area_source ON aggr_emis.source_id = area_source.source_id
),
grid_emis as (
  SELECT aggr_emis.substance_id, ac1, ac2, ac3, aggr_emis.emis
  FROM
    (
      SELECT substance_id, source_id, raster_name, sum(emis * raster.total) as emis
      FROM
        (
          SELECT
            grid_source.source_id,
            emis.substance_id as substance_id,
            emis.value as emis,
            emis.raster as raster_name
          FROM edb_gridsourcesubstance as emis
          JOIN grid_source ON grid_source.source_id=emis.source_id
          WHERE emis.value > 0
          {emis_substance_filter}
          UNION ALL
          SELECT
            grid_source.source_id,
            ef_subst.substance_id as substance_id,
            emis.rate * ef_subst.factor as emis,
            emis.raster as raster_name
          FROM edb_gridsourceactivity as emis
          JOIN grid_source ON emis.source_id=grid_source.source_id
          JOIN ef_subst ON emis.activity_id=ef_subst.activity_id
          WHERE emis.rate > 0
        ) all_emis
      JOIN (
         {raster_share_sql}
      ) as raster ON all_emis.raster_name = raster.name
      GROUP BY substance_id, source_id, raster_name
    ) aggr_emis
  JOIN grid_source ON aggr_emis.source_id = grid_source.source_id
)
SELECT {ac_column} substances.slug as substance, sum(emis) as emission
FROM
  (
    SELECT * FROM area_emis
    UNION ALL
    SELECT * FROM point_emis
    UNION ALL
    SELECT * FROM grid_emis
    UNION ALL
    SELECT * FROM road_emis
  ) as all_emis
JOIN substances ON substance_id = substances.id
GROUP BY {ac_groupby} substances.slug
