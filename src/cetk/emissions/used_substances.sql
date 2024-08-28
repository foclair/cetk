/*
Similar to inventory_substances.sql in gadget.
 */
with point_subst as (
	select distinct psrc_emis.substance_id
	from edb_pointsourcesubstance as psrc_emis
	join edb_pointsource as psrc on psrc.id = psrc_emis.source_id
),
area_subst as (
	select distinct asrc_emis.substance_id
	from edb_areasourcesubstance as asrc_emis
	join edb_areasource as asrc on asrc.id = asrc_emis.source_id
),
grid_subst as (
	select distinct gsrc_emis.substance_id
 	from edb_gridsourcesubstance as gsrc_emis
 	join edb_gridsource as gsrc on gsrc.id = gsrc_emis.source_id
),
road_subst as (
 	select distinct veh_ef.substance_id
 	from edb_vehicleef as veh_ef
),
source_ef_subst as (
	select distinct ef.substance_id
	from edb_emissionfactor as ef
	join (
		select distinct activity_id
		from (
			select psrc_act.activity_id
			from edb_pointsource as psrc
			join edb_pointsourceactivity as psrc_act on psrc.id = psrc_act.source_id
			union all
			select asrc_act.activity_id
			from edb_areasource as asrc
			join edb_areasourceactivity as asrc_act on asrc.id = asrc_act.source_id
			union all
			select gsrc_act.activity_id
			from edb_gridsource as gsrc
			join edb_gridsourceactivity as gsrc_act on gsrc.id = gsrc_act.source_id
		) as all_act_ids
	) as activity_ids on activity_ids.activity_id = ef.activity_id
)
select distinct slug
from (
	select * from point_subst
	union all
	select * from area_subst
	union all
	select * from grid_subst
	union all
	select * from road_subst
	union all
	select * from source_ef_subst
) as all_subst
join substances on substance_id = substances.id
order by slug
