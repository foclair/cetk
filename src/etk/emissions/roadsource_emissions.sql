/*Retrieve roads using optional filters */
WITH sources as (
  SELECT
    id as source_id,
    name as source_name,
    tags,
    aadt,
    heavy_vehicle_share,
    congestion_profile_id,
    nolanes,
    speed,
    width,
    slope,
    roadclass_id,
    fleet_id,
    ST_Transform(geometry(geom), %(srid)s) as geom
  FROM edb_roadsource as sources
  WHERE sources.aadt > %(min_aadt)s
  {id_filter}
  {name_filter}
  {tag_filter}
  {polygon_filter}
),
/*
Get vehicles for each road with fraction and timevar.
If heavy vehicle share is specified on the road, the vehicle
fractions in the fleet are re-scaled accordingly.
Emission factors for different fuels are aggregated
*/
fleet_veh as (
  SELECT
    fm.fleet_id,
    rc.id as roadclass_id,
    fm.vehicle_id as vehicle_id,
    veh.isheavy,
    veh.max_speed,
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
    coldstart_ef
  FROM
  (
    SELECT
      fleet_id,
      fm.id as fleetmember_id,
      veh_ef.traffic_situation_id as traffic_situation,
      fm.vehicle_id,
      veh_ef.substance_id,
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
    JOIN edb_vehiclefuelcomb as vfc on fm.vehicle_id = vfc.vehicle_id
      AND fmf.fuel_id = vfc.fuel_id
    LEFT JOIN edb_activitycode as ac1 ON vfc.activitycode1_id=ac1.id
    LEFT JOIN edb_activitycode as ac2 ON vfc.activitycode2_id=ac2.id
    LEFT JOIN edb_activitycode as ac3 ON vfc.activitycode3_id=ac3.id
    WHERE veh_ef.substance_id != {traffic_work_subst_id}
      {ac_filter}
    GROUP BY fm.fleet_id, fm.id, veh_ef.traffic_situation_id,
      fm.vehicle_id, veh_ef.substance_id
    UNION
    SELECT
      fleet_id,
      fm.id as fleetmember_id,
      ts.id as traffic_situation,
      fm.vehicle_id,
      {traffic_work_subst_id} as substance_id,
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
  ) as veh_fuel_ef
  JOIN edb_fleetmember fm ON veh_fuel_ef.fleetmember_id = fm.id
  JOIN edb_vehicle veh ON veh_fuel_ef.vehicle_id=veh.id
  LEFT JOIN edb_roadclass rc
    ON veh_fuel_ef.traffic_situation=rc.traffic_situation_id
  JOIN edb_fleet as fleet ON fm.fleet_id = fleet.id
  WHERE {ef_substance_filter}
),
/*
Retrieve all valid combinations of congestion profile and flow timevar
*/
ct_combos as (
    SELECT DISTINCT congestion_profile_id, timevar_id
    FROM edb_roadsource AS src
    JOIN edb_fleetmember AS fm ON src.fleet_id = fm.fleet_id
),
/*
Calculate weight of each LOS (Level Of Service) for all valid combinations
of congestion profile and timevar
*/
congestion as (
    SELECT ct_combos.congestion_profile_id as congestion_id,
	ct_combos.timevar_id as timevar_id,
	COALESCE(weighted.freeflow, 1.0) as freeflow,
	COALESCE(weighted.heavy, 0.0) as heavy,
	COALESCE(weighted.saturated, 0.0) as saturated,
	COALESCE(weighted.stopngo, 0.0) as stopngo
    FROM ct_combos
    LEFT JOIN
    (
	SELECT timevar_id, congestion_id,
	    sum(case when cond='1' then flow else 0 end) / typeday_sum
	    as freeflow,
	    sum(case when cond='2' then flow else 0 end) / typeday_sum
	    as heavy,
	    sum(case when cond='3' then flow else 0 end) / typeday_sum
	    as saturated,
	    sum(case when cond='4' then flow else 0 end) / typeday_sum
	    as stopngo,
	    max(cond) as dummy
	FROM
	(
	    SELECT t.id as timevar_id, c.id as congestion_id,
		t.typeday_sum as typeday_sum,
		unnest(c.traffic_condition) as cond,
		unnest(t.typeday) AS flow
	    FROM ct_combos
	    JOIN edb_flowtimevar AS t ON ct_combos.timevar_id = t.id
	    JOIN edb_congestionprofile AS c
	    ON ct_combos.congestion_profile_id = c.id
	) AS profiles
	GROUP BY timevar_id, congestion_id, typeday_sum
    ) AS weighted ON ct_combos.congestion_profile_id = weighted.congestion_id
    AND ct_combos.timevar_id = weighted.timevar_id
)
/*
Calculate emissions for each combination of road, vehicle and substance
*/
SELECT source_id, source_name, geom,
       fleet_id, roadclass_id,
       substance_id, vehicle_id, isheavy,
       ST_AsText(road_veh_ef.simple_geom) as wkt,
       ST_Length(road_veh_ef.geom) as length,
       ST_Length(simple_geom) as simple_length,
       timevar_id,
       coldstart_timevar_id,
       congestion_profile_id,
       aadt,
       nolanes,
       speed,
       width,
       slope,
       heavy_vehicle_share,
       fraction,
       veh_m_per_sec,
       (
	  road_veh_ef.veh_m_per_sec * (
	    freeflow_ef * COALESCE(freeflow_share, 1.0) +
	    heavy_ef * COALESCE(heavy_share, 0.0) +
	    saturated_ef * COALESCE(saturated_share, 0.0) +
	    stopngo_ef * COALESCE(stopngo_share, 0.0) +
	    coldstart_ef * coldstart_fraction
	  )
       ) as emis,
       freeflow_ef, heavy_ef, saturated_ef, stopngo_ef, coldstart_ef,
       freeflow_share, heavy_share, saturated_share, stopngo_share,
       coldstart_fraction, max_speed
FROM
  (
  SELECT sources.source_id,
      source_name,
      geom,
      ST_SimplifyPreserveTopology(geom, {tolerance}) as simple_geom,
      sources.fleet_id,
      sources.roadclass_id,
      aadt,
      heavy_vehicle_share,
      nolanes,
      speed,
      width,
      slope,
      fleet_veh.vehicle_id,
      fleet_veh.timevar_id,
      fleet_veh.coldstart_fraction,
      fleet_veh.coldstart_timevar_id,
      fleet_veh.fraction,
      fleet_veh.isheavy,
      fleet_veh.max_speed,
      congestion.congestion_id as congestion_profile_id,
      congestion.freeflow as freeflow_share,
      congestion.heavy as heavy_share,
      congestion.saturated as saturated_share,
      congestion.stopngo as stopngo_share,
      fleet_veh.substance_id,
      fleet_veh.freeflow_ef,
      fleet_veh.heavy_ef,
      fleet_veh.saturated_ef,
      fleet_veh.stopngo_ef,
      fleet_veh.coldstart_ef,
      (
	CASE
	WHEN fleet_veh.isheavy=TRUE THEN
	  COALESCE(
	    sources.heavy_vehicle_share,
	    fleet_veh.default_heavy_vehicle_share
	  )
	ELSE
	  1 - COALESCE(
	    sources.heavy_vehicle_share,
	    fleet_veh.default_heavy_vehicle_share
	  )
	END
	* fleet_veh.fraction * sources.aadt / (3600.0 * 24) * ST_Length(sources.geom)
      ) as veh_m_per_sec
    FROM sources
    JOIN fleet_veh
      ON sources.roadclass_id=fleet_veh.roadclass_id
      AND sources.fleet_id=fleet_veh.fleet_id
    LEFT JOIN congestion
      ON congestion.congestion_id=sources.congestion_profile_id
      AND congestion.timevar_id=fleet_veh.timevar_id
  ) as road_veh_ef
ORDER BY source_id
