"""Unit and regression tests for edb models."""

# from collections import OrderedDict
import ast

import numpy as np
import pytest

from etk.edb import models

# from django.contrib.gis.gdal import GDALRaster
# from django.contrib.gis.geos import Polygon
# from pytest_django.asserts import assertNumQueries


# from etk.edb.const import DUMMY_SRID
# from etk.edb.models import Substance
# from etk.edb.units import activity_rate_unit_to_si, emission_unit_to_si


class TestActivityCodes:
    def test_activitycode1_manager_create(self, code_sets):
        """Test creating a new activitycode with reference to a code-set."""
        # TODO maybe can find fixtures in edb/fixtures now?
        # if not can change to ifactory.edb.codeset() but then no preset data?
        code_set = code_sets[0]
        ac1 = models.ActivityCode.objects.create(
            code="actcode1", label="label1", code_set=code_set
        )
        ac1_ref = code_set.codes.get(code="actcode1", code_set=code_set)
        assert ac1 == ac1_ref

        ac1, created = code_set.codes.get_or_create(code="actcode1", label="label1")
        assert not created
        assert ac1 == ac1_ref

        ac2, created = code_set.codes.get_or_create(code="actcode2", label="label2")
        assert created

    def test_get_children(self, code_sets):
        code_set = code_sets[0]
        ac1 = code_set.codes.get(code="1")
        ac13 = code_set.codes.get(code="1.3")
        ac131 = code_set.codes.get(code="1.3.1")
        # breakpoint()
        assert ac13 in list(ac1.get_children())
        assert ac131 not in list(ac1.get_children())
        assert ac131 in list(ac13.get_children())

    def test_get_parent(self, code_sets):
        code_set = code_sets[0]
        ac1 = code_set.codes.get(code="1")
        ac13 = code_set.codes.get(code="1.3")
        ac131 = code_set.codes.get(code="1.3.1")
        # breakpoint()
        assert ac1 == ac13.get_parent()
        assert ac13 == ac131.get_parent()
        with pytest.raises(RuntimeError):
            ac1.get_parent()


# TODO start fixing tests above here

# class TestRoadEFSet:
#     @pytest.fixture
#     def roadefset(self, ifactory, base_sets, vehicles):
#         base_set1 = base_sets[0]
#         roadefset = ifactory.edb.roadefset(
#             name="test set",
#             description="a test set",
#             owner=ifactory.auth.user(),
#             year=2019,
#             base_set=base_set1,
#             project=base_set1.project,
#         )
#         fuels = list(base_set1.vehicle_fuels.all())
#         traffic_situations = list(base_set1.traffic_situations.all())
#         for i in range(2):
#             ifactory.edb.vehicleef(
#                 ef_set=roadefset,
#                 vehicle=vehicles[i],
#                 fuel=fuels[i],
#                 traffic_situation=traffic_situations[i],
#                 freeflow=i + 1,
#                 heavy=i + 2,
#                 saturated=i + 3,
#                 stopngo=i + 4,
#                 coldstart=i + 5,
#             )
#         return roadefset

#     def test_road_ef_set_manager_create(self, projects, base_sets):
#         """Test creating a new road ef-set."""

#         proj1 = projects[0]
#         base_set1 = base_sets[0]
#         refset1 = models.RoadEFSet.objects.create(
#             base_set=base_set1, project=proj1, name="test"
#         )
#         assert refset1.project.slug == proj1.slug
#         assert refset1.name == "test"
#         refset2, created = models.RoadEFSet.objects.get_or_create(
#             base_set=base_set1, name="test"
#         )
#         assert not created
#         assert refset1 == refset2

#     def test_copy(self, roadefset):
#         copy = roadefset.copy()
#         assert copy.pk != roadefset.pk
#         assert copy.name == roadefset.name
#         assert copy.slug != roadefset.slug
#         assert copy.base_set == roadefset.base_set
#         assert copy.project == roadefset.project
#         assert copy.description == roadefset.description
#         assert copy.owner == roadefset.owner
#         assert copy.year == roadefset.year
#         assert copy.created > roadefset.created
#         assert copy.updated > roadefset.updated

#         emissionfactors = roadefset.emissionfactors.order_by("freeflow")
#         copied_emissionfactors = copy.emissionfactors.order_by("freeflow")
#         assert len(emissionfactors) > 1
#         assert len(copied_emissionfactors) == len(emissionfactors)
#         for copy, ef in zip(copied_emissionfactors, emissionfactors):
#             assert copy.pk != ef.pk
#             assert copy.traffic_situation == ef.traffic_situation
#             assert copy.substance == ef.substance
#             assert copy.vehicle == ef.vehicle
#             assert copy.fuel == ef.fuel
#             assert copy.freeflow == ef.freeflow
#             assert copy.heavy == ef.heavy
#             assert copy.saturated == ef.saturated
#             assert copy.stopngo == ef.stopngo
#             assert copy.coldstart == ef.coldstart

#     def test_copy_with_slug(self, roadefset):
#         copy = roadefset.copy(slug="my-explicit-slug")
#         assert copy.slug == "my-explicit-slug"
#         assert copy.project == roadefset.project

#     def test_copy_with_project(self, roadefset, ifactory):
#         new_project = ifactory.core.project(domain=roadefset.project.domain)
#         copy = roadefset.copy(project=new_project)
#         assert copy.slug == roadefset.slug
#         assert copy.project == new_project

#     def test_copy_with_project_in_another_domain(self, roadefset, ifactory):
#         domain = ifactory.core.domain(name="new domain")
#         new_project = ifactory.core.project(domain=domain)
#         copy = roadefset.copy(project=new_project)
#         assert copy.slug == roadefset.slug
#         assert copy.project == new_project
#         assert copy.base_set != roadefset.base_set
#         ef = copy.emissionfactors.first()
#         assert ef.vehicle.base_set != roadefset.base_set
#         assert ef.fuel.base_set != roadefset.base_set
#         assert ef.traffic_situation.base_set != roadefset.base_set

#     def test_copy_num_queries(self, roadefset, django_assert_num_queries):
#         with django_assert_num_queries(5):
#             # 1 copy roadefset, 1 savepoint, 1 get vehicleefs,
#             # 1 copy vehicleefs, 1 savepoint
#             roadefset.copy()

#     def test_str(self, roadefset):
#         assert str(roadefset) == roadefset.name


# class TestSourceEFSet:
#     def test_source_ef_set_manager_create(self, projects, base_sets):
#         """Test creating a new source ef-set."""

#         proj1 = projects[0]
#         base_set1 = base_sets[0]
#         refset1 = models.SourceEFSet.objects.create(
#             base_set=base_set1, project=proj1, name="test"
#         )
#         assert refset1.project.slug == proj1.slug
#         assert refset1.name == "test"
#         refset2, created = models.SourceEFSet.objects.get_or_create(
#             base_set=base_set1, project__slug=proj1.slug, name="test"
#         )
#         assert not created
#         assert refset1 == refset2

#     def test_str(self, source_ef_sets):
#         assert str(source_ef_sets[0]) == source_ef_sets[0].name


# class TestInventory:
#     def test_inventory_manager_create(self, projects, base_sets):
#         """Test creating a new inventory."""

#         base_set = base_sets[0]

#         proj1 = projects[0]
#         inventory = models.Inventory.objects.create(
#             project=proj1, base_set=base_set, name="test"
#         )
#         assert inventory.project.slug == proj1.slug
#         assert inventory.name == "test"
#         inventory2, created = models.Inventory.objects.get_or_create(
#             project__slug=proj1.slug, base_set=base_set, name="test"
#         )
#         assert not created
#         assert inventory == inventory2

#     def test_delete(self, ifactory):
#         inventory = ifactory.edb.inventory()
#         facility = ifactory.edb.facility(inventory=inventory)
#         timevar = ifactory.edb.timevar(inventory=inventory)
#         pointsource = ifactory.edb.pointsource(
#             inventory=inventory, facility=facility, timevar=timevar
#         )
#         ifactory.edb.pointsourceactivity(source=pointsource)
#         ifactory.edb.pointsourcesubstance(source=pointsource)
#         areasource = ifactory.edb.areasource(
#             inventory=inventory, facility=facility, timevar=timevar
#         )
#         ifactory.edb.areasourceactivity(source=areasource)
#         ifactory.edb.areasourcesubstance(source=areasource)
#         gridsource = ifactory.edb.gridsource(inventory=inventory, timevar=timevar)
#         ifactory.edb.gridsourceactivity(source=gridsource)
#         ifactory.edb.gridsourcesubstance(source=gridsource)
#         flow_timevar = ifactory.edb.flowtimevar(inventory=inventory)
#         coldstart_timevar = ifactory.edb.coldstarttimevar(inventory=inventory)
#         congestion_profile = ifactory.edb.congestionprofile(inventory=inventory)
#         fleet = ifactory.edb.fleet(inventory=inventory)
#         fleet_member = ifactory.edb.fleetmember(
#             fleet=fleet, timevar=flow_timevar, coldstart_timevar=coldstart_timevar
#         )
#         ifactory.edb.fleetmemberfuel(fleet_member=fleet_member)
#         ifactory.edb.roadsource(
#             inventory=inventory, congestion_profile=congestion_profile, fleet=fleet
#         )
#         inventory.delete()
#         assert not models.Inventory.objects.filter(pk=inventory.pk).exists()

#     def test_delete_sources(self, ifactory):
#         inventory = ifactory.edb.inventory()
#         facility = ifactory.edb.facility(inventory=inventory)
#         timevar = ifactory.edb.timevar(inventory=inventory)
#         pointsource = ifactory.edb.pointsource(
#             inventory=inventory, facility=facility, timevar=timevar
#         )
#         ifactory.edb.pointsourceactivity(source=pointsource)
#         ifactory.edb.pointsourcesubstance(source=pointsource)
#         areasource = ifactory.edb.areasource(
#             inventory=inventory, facility=facility, timevar=timevar
#         )
#         ifactory.edb.areasourceactivity(source=areasource)
#         ifactory.edb.areasourcesubstance(source=areasource)
#         gridsource = ifactory.edb.gridsource(inventory=inventory, timevar=timevar)
#         ifactory.edb.gridsourceactivity(source=gridsource)
#         ifactory.edb.gridsourcesubstance(source=gridsource)
#         flow_timevar = ifactory.edb.flowtimevar(inventory=inventory)
#         coldstart_timevar = ifactory.edb.coldstarttimevar(inventory=inventory)
#         congestion_profile = ifactory.edb.congestionprofile(inventory=inventory)
#         fleet = ifactory.edb.fleet(inventory=inventory)
#         fleet_member = ifactory.edb.fleetmember(
#             fleet=fleet, timevar=flow_timevar, coldstart_timevar=coldstart_timevar
#         )
#         ifactory.edb.fleetmemberfuel(fleet_member=fleet_member)
#         ifactory.edb.roadsource(
#             inventory=inventory, congestion_profile=congestion_profile, fleet=fleet
#         )
#         inventory.delete_sources()
#         assert inventory.pointsources.all().count() == 0
#         assert inventory.areasources.all().count() == 0
#         assert inventory.roadsources.all().count() == 0
#         assert inventory.gridsources.all().count() == 0

#     def test_copy(self, ifactory, django_assert_num_queries):
#         original = ifactory.edb.inventory(slug="original")
#         flow_timevar = ifactory.edb.flowtimevar(
#             inventory=original, name="flow timevar1"
#         )
#         congestion_profile = ifactory.edb.congestionprofile(
#             inventory=original, name="profile1"
#         )
#         coldstart_timevar = ifactory.edb.coldstarttimevar(
#             inventory=original, name="coldstart timevar1"
#         )
#         for i in range(2):
#             fleet = ifactory.edb.fleet(inventory=original, name=f"fleet{i}")
#             for j in range(2):
#                 fleetmember = ifactory.edb.fleetmember(
#                     fleet=fleet,
#                     timevar=flow_timevar,
#                     coldstart_timevar=coldstart_timevar,
#                 )
#                 for k in range(2):
#                     ifactory.edb.fleetmemberfuel(fleet_member=fleetmember)
#         timevar = ifactory.edb.timevar(inventory=original, name="timevar1")
#         wear_profile = ifactory.edb.wearprofile(
#             inventory=original, name="wear profile 1"
#         )
#         for i in range(2):
#             ifactory.edb.roadsource(
#                 inventory=original,
#                 fleet=fleet,
#                 congestion_profile=congestion_profile,
#                 wear_profile=wear_profile,
#                 name="road %i" % i,
#             )

#             for model in ("pointsource", "areasource"):
#                 source = getattr(ifactory.edb, model)(
#                     inventory=original, name="source %i" % i, timevar=timevar
#                 )
#                 for j in range(2):
#                     getattr(ifactory.edb, model + "activity")(source=source)
#                     getattr(ifactory.edb, model + "substance")(source=source)

#             gridsource = ifactory.edb.gridsource(
#                 inventory=original, name="source %i" % i, timevar=timevar
#             )
#             raster = ifactory.edb.gridsourceraster(inventory=original)
#             for j in range(2):
#                 ifactory.edb.gridsourceactivity(source=gridsource, raster=raster)
#                 ifactory.edb.gridsourcesubstance(source=gridsource, raster=raster)

#         with django_assert_num_queries(49):
#             copy = original.copy()
#         assert copy.pk is not None
#         assert copy.pk != original.pk

#         def get_fields(obj, exclude=("id",)):
#             return [
#                 f
#                 for f in obj._meta.get_fields()
#                 if not f.one_to_many and f.name not in exclude
#             ]

#         # compare inventories
#         for f in get_fields(original, exclude={"id", "slug", "created", "updated"}):
#             assert getattr(copy, f.name) == getattr(original, f.name)
#         # compare point & area sources
#         for relation in ("pointsources", "areasources"):
#             original_sources = getattr(original, relation).order_by("name")
#             copied_sources = getattr(copy, relation).order_by("name")
#             for src, org_src in zip(copied_sources, original_sources):
#                 assert src.pk != org_src.pk
#                 for f in get_fields(
#                     org_src, exclude={"id", "inventory", "created", "updated"}
#                 ):
#                     if f.name == "timevar":
#                         assert org_src.timevar.inventory == original
#                         assert src.timevar.inventory == copy
#                     else:
#                         assert getattr(src, f.name) == getattr(org_src, f.name)
#                 org_substances = org_src.substances.order_by("substance__name")
#                 substances = src.substances.order_by("substance__name")
#                 for org_subst, subst in zip(org_substances, substances):
#                     for f in get_fields(
# org_subst, exclude={"id", "source", "updated"}):
#                         assert getattr(subst, f.name) == getattr(org_subst, f.name)

#                 org_activities = org_src.activities.order_by("activity__name")
#                 activities = src.activities.order_by("activity__name")
#                 for org_act, act in zip(org_activities, activities):
#                     for f in get_fields(org_act, exclude={"id", "source"}):
#                         assert getattr(act, f.name) == getattr(org_act, f.name)

#         # compare grid sources
#         original_sources = original.gridsources.order_by("name")
#         copied_sources = copy.gridsources.order_by("name")
#         for src, org_src in zip(copied_sources, original_sources):
#             assert src.pk != org_src.pk
#             for f in get_fields(
#                 org_src, exclude={"id", "inventory", "geom", "created", "updated"}
#             ):
#                 if f.name == "timevar":
#                     assert org_src.timevar.inventory == original
#                     assert src.timevar.inventory == copy
#                 else:
#                     assert getattr(src, f.name) == getattr(org_src, f.name)

#             org_substances = org_src.substances.order_by("substance__name")
#             substances = src.substances.order_by("substance__name")
#             for org_subst, subst in zip(org_substances, substances):
#                 for f in get_fields(
#                     org_subst, exclude={"id", "source", "updated", "raster"}
#                 ):
#                     assert getattr(subst, f.name) == getattr(org_subst, f.name)
#                 assert numpy.allclose(
#                     org_subst.raster.geom.bands[0].data(),
#                     subst.raster.geom.bands[0].data(),
#                 )

#             org_activities = org_src.activities.order_by("activity__name")
#             activities = src.activities.order_by("activity__name")
#             for org_act, act in zip(org_activities, activities):
#                 for f in get_fields(org_act, exclude={"id", "source", "raster"}):
#                     assert getattr(act, f.name) == getattr(org_act, f.name)
#                 assert numpy.allclose(
#                     org_act.raster.geom.bands[0].data(),
#                     act.raster.geom.bands[0].data()
#                 )

#         # compare road sources
#         original_sources = original.roadsources.order_by("name")
#         copied_sources = copy.roadsources.order_by("name")
#         for src, org_src in zip(copied_sources, original_sources):
#             assert src.pk != org_src.pk
#             for f in get_fields(
#                 org_src, exclude={"id", "inventory", "created", "updated"}
#             ):
#                 # check that related instances belong to the same inventory
#                 if f.name in ("fleet", "congestion_profile", "wear_profile"):
#                     related_instance_copy = getattr(src, f.name)
#                     related_instance = getattr(org_src, f.name)
#                     assert related_instance.inventory == original
#                     assert related_instance_copy.inventory == copy
#                 # check that all other fields are equal
#                 else:
#                     assert getattr(src, f.name) == getattr(org_src, f.name)

#         # compare fleets
#         org_fleet = original.fleets.get(name="fleet1")
#         fleet = copy.fleets.get(name="fleet1")
#         assert fleet.pk != org_fleet.pk
#         for f in get_fields(org_fleet, exclude={"id", "inventory", "vehicles"}):
#             assert getattr(fleet, f.name) == getattr(org_fleet, f.name)

#         # compare fleet members & fleet member fuels
#         org_members = org_fleet.vehicles.order_by("vehicle_id")
#         members = fleet.vehicles.order_by("vehicle_id")
#         for org_member, member in zip(org_members, members):
#             for f in get_fields(org_member, exclude={"id", "fleet"}):
#                 elif f.name == "fuels":
#                     org_fuels = org_member.fuels.order_by("fuel_id")
#                     fuels = member.fuels.order_by("fuel_id")
#                     for org_fuel, fuel in zip(org_fuels, fuels):
#                         for f in get_fields(org_fuel, exclude={"id", "fleet_member"}):
#                             assert getattr(fuel, f.name) == getattr(org_fuel, f.name)
#                 else:
#                     assert getattr(member, f.name) == getattr(org_member, f.name)
#         # compare timevars
#         org_timevar = original.timevars.get(name="timevar1")
#         timevar = copy.timevars.get(name="timevar1")
#         for f in get_fields(org_timevar, exclude={"id"}):
#             if f.name == "inventory":
#                 assert getattr(timevar, f.name) != getattr(org_timevar, f.name)
#             else:
#                 assert getattr(timevar, f.name) == getattr(org_timevar, f.name)

#         #  compare flow timevars
#         org_flow_timevar = original.flow_timevars.get(name="flow timevar1")
#         flow_timevar = copy.flow_timevars.get(name="flow timevar1")
#         for f in get_fields(org_flow_timevar, exclude={"id"}):
#             if f.name == "inventory":
#                 assert getattr(flow_timevar, f.name) != getattr(
#                     org_flow_timevar, f.name
#                 )
#             else:
#                 assert getattr(flow_timevar, f.name) == getattr(
#                     org_flow_timevar, f.name
#                 )

#         # compare coldstart timevars
#         org_cs_timevar = original.coldstart_timevars.get(name="coldstart timevar1")
#         cs_timevar = copy.coldstart_timevars.get(name="coldstart timevar1")
#         for f in get_fields(org_cs_timevar, exclude={"id"}):
#             if f.name == "inventory":
#                 assert getattr(cs_timevar, f.name) != getattr(org_cs_timevar, f.name)
#             else:
#                 assert getattr(cs_timevar, f.name) == getattr(org_cs_timevar, f.name)

#         # compare congestion profiles
#         org_prof = original.congestion_profiles.get(name="profile1")
#         prof = copy.congestion_profiles.get(name="profile1")
#         for f in get_fields(org_prof, exclude={"id"}):
#             if f.name == "inventory":
#                 assert getattr(prof, f.name) != getattr(org_prof, f.name)
#             else:
#                 assert getattr(prof, f.name) == getattr(org_prof, f.name)

#         # compare wear profiles
#         org_wear = original.wear_profiles.get(name="wear profile 1")
#         wear = copy.wear_profiles.get(name="wear profile 1")
#         for f in get_fields(org_wear, exclude={"id"}):
#             if f.name == "inventory":
#                 assert getattr(wear, f.name) != getattr(org_wear, f.name)
#             else:
#                 assert getattr(wear, f.name) == getattr(org_wear, f.name)

#         # test copy without fleet
#         for src in original_sources:
#             src.fleet = None
#             src.save()
#         original.fleets.all().delete()

#         # test copy without any fleets defined
#         assert original.fleets.count() == 0
#         with django_assert_num_queries(44):
#             copy2 = original.copy()
#         assert copy2.pk is not None
#         assert copy2.pk != original.pk
#         assert copy2.fleets.count() == 0

#     def test_copy_with_slug(self, ifactory):
#         original = ifactory.edb.inventory(slug="original")
#         copy = original.copy(slug="copy")
#         assert copy.slug == "copy"

#     def test_copy_to_another_project(self, ifactory):
#         original = ifactory.edb.inventory(slug="original")
#         congestion_profile = ifactory.edb.congestionprofile(
#             inventory=original, name="profile1"
#         )

#         ifactory.edb.pointsource(inventory=original, geom="POINT (-1 -1)")
#         timevar = ifactory.edb.timevar(inventory=original)
#         ifactory.edb.pointsource(
#             inventory=original,
#             geom="POINT (1 1)",
#             tags={"included": True},
#             timevar=timevar,
#         )
#         ifactory.edb.areasource(
#             inventory=original,
#             geom="POLYGON ((-2 -1, -1 -2, -1 -1, -2 -1))",
#             timevar=timevar,
#         )
#         ifactory.edb.areasource(
#             inventory=original,
#             geom="POLYGON ((1 1, 2 1, 1 2, 1 1))",
#             tags={"included": True},
#             timevar=timevar,
#         )
#         ifactory.edb.roadsource(
#             inventory=original,
#             congestion_profile=congestion_profile,
#             geom="LINESTRING (-1 -1, -2 -2)",
#         )
#         ifactory.edb.roadsource(
#             inventory=original,
#             congestion_profile=congestion_profile,
#             geom="LINESTRING (1 1, 2 2)",
#             tags={"included": True},
#         )
#         new_project = ifactory.core.project(
#             name="new",
#             extent="MULTIPOLYGON (((0 0, 3 0, 3 3, 0 3, 0 0)))",
#             domain=original.project.domain,
#         )
#         copy = original.copy(project=new_project)
#         assert copy.pk is not None
#         assert copy.pk != original.pk
#         assert copy.slug == original.slug
#         assert copy.project == new_project

#         assert copy.pointsources.count() == 1
#         assert "included" in copy.pointsources.get().tags
#         assert copy.areasources.count() == 1
#         assert "included" in copy.areasources.get().tags
#         assert copy.roadsources.count() == 1
#         assert "included" in copy.roadsources.get().tags

#     def test_copy_to_another_domain(
#         self,
#         ifactory,
#         base_sets,
#         fleets,
#         vehicles,
#         roadclasses,
#         activities,
#         pointsources,
#         roadsources,
#         areasources,
#         gridsources,
#     ):
#         inv = fleets[0].inventory
#         domain = inv.project.domain
#         new_domain = ifactory.core.domain(name="new domain", extent=domain.extent)
#         new_project = ifactory.core.project(domain=new_domain,
# extent=new_domain.extent)
#         new_baseset = inv.base_set.copy(project=new_project)
#         new_inv = inv.copy(
#             name="new inventory", project=new_project, base_set=new_baseset
#         )

#         assert inv.project.domain != new_inv.project.domain
#         assert inv.base_set.project.domain != new_inv.base_set.project.domain
#         assert inv.base_set.code_set1 != new_inv.base_set.code_set1
#         assert inv.base_set.code_set2 != new_inv.base_set.code_set2

#         assert inv.pointsources.all().count() == new_inv.pointsources.all().count()
#         assert inv.areasources.all().count() == new_inv.areasources.all().count()
#         assert inv.gridsources.all().count() == new_inv.gridsources.all().count()
#         assert inv.roadsources.all().count() == new_inv.roadsources.all().count()

#         new_domain2 = ifactory.core.domain(name="new domain2", extent=domain.extent)
#         new_project2 = ifactory.core.project(
#             domain=new_domain2, extent=new_domain2.extent
#         )
#         new_inv2 = inv.copy(name="new inventory2", project=new_project2)

#         assert inv.project.domain != new_inv2.project.domain
#         assert inv.base_set != new_inv2.base_set
#         assert inv.base_set.project.domain != new_inv2.base_set.project.domain
#         assert inv.base_set.code_set1 != new_inv2.base_set.code_set1
#         assert inv.base_set.code_set2 != new_inv2.base_set.code_set2

#         assert inv.pointsources.all().count() == new_inv2.pointsources.all().count()
#         assert inv.areasources.all().count() == new_inv2.areasources.all().count()
#         assert inv.gridsources.all().count() == new_inv2.gridsources.all().count()
#         assert inv.roadsources.all().count() == new_inv2.roadsources.all().count()

#         assert (
#             inv.fleets.first().vehicles.first().vehicle.base_set
#             != new_inv2.fleets.first().vehicles.first().vehicle.base_set
#         )
#         assert (
#             inv.fleets.first().vehicles.first().fuels.first().fuel.base_set
#             != new_inv2.fleets.first().vehicles.first().fuels.first().fuel.base_set
#         )
#         assert (
#             inv.roadsources.first().roadclass.traffic_situation.base_set
#             != new_inv2.roadsources.first().roadclass.traffic_situation.base_set
#         )

#     def test_copy_with_drop_sources(self, ifactory):
#         original = ifactory.edb.inventory(slug="original")
#         fleet = ifactory.edb.fleet(inventory=original, name="fleet1")
#         flow_timevar = ifactory.edb.flowtimevar(
#             inventory=original, name="flow timevar1"
#         )
#         congestion_profile = ifactory.edb.congestionprofile(
#             inventory=original, name="profile1"
#         )
#         coldstart_timevar = ifactory.edb.coldstarttimevar(
#             inventory=original, name="coldstart timevar1"
#         )
#         fleet_member = ifactory.edb.fleetmember(
#             fleet=fleet, timevar=flow_timevar, coldstart_timevar=coldstart_timevar
#         )
#         ifactory.edb.fleetmemberfuel(fleet_member=fleet_member)
#         timevar = ifactory.edb.timevar(inventory=original, name="timevar1")
#         wear_profile = ifactory.edb.wearprofile(
#             inventory=original, name="wear profile 1"
#         )
#         ifactory.edb.roadsource(
#             inventory=original,
#             fleet=fleet,
#             congestion_profile=congestion_profile,
#             wear_profile=wear_profile,
#             name="road 1",
#         )
#         for model in ("pointsource", "areasource", "gridsource"):
#             getattr(ifactory.edb, model)(
#                 inventory=original, name=f"{model} 1", timevar=timevar
#             )
#         ifactory.edb.gridsourceraster(inventory=original)

#         copy = original.copy(drop_sources=True)

#         assert copy.fleets.count() == 1
#         assert copy.flow_timevars.count() == 1
#         assert copy.congestion_profiles.count() == 1
#         assert copy.coldstart_timevars.count() == 1
#         assert copy.timevars.count() == 1
#         assert copy.wear_profiles.count() == 1
#         assert not copy.roadsources.exists()
#         assert not copy.pointsources.exists()
#         assert not copy.areasources.exists()
#         assert not copy.gridsources.exists()
#         assert not copy.gridsourcerasters.exists()

# def test_aggregate_emissions(
#     self,
#     inventories,
#     road_ef_sets,
#     source_ef_sets,
#     roadsources,
#     pointsources,
#     areasources,
#     activities,
# ):
#     NOx = Substance.objects.get(slug="NOx")
#     SOx = Substance.objects.get(slug="SOx")
#     road_ef_set = road_ef_sets[0]
#     source_ef_set = source_ef_sets[0]
#     inventory = inventories[0]
#     gdal_raster = GDALRaster(
#         {
#             "srid": DUMMY_SRID,
#             "width": 2,
#             "height": 2,
#             "datatype": 6,
#             "scale": (1000, -1000),
#             "origin": (367000, 6370000),
#             "bands": [{"data": [0.1, 0.2, 0.3, 0.4]}],
#         }
#     )
#     raster = inventory.gridsourcerasters.create(
#         name="gridsourceraster 1",
#         srid=inventory.project.domain.srid,
#         geom=gdal_raster,
#     )
#     src1 = inventory.gridsources.create(
#         name="gridsource1",
#         activitycode1=inventory.base_set.code_set1.codes.get(code="3"),
#     )
#     src1.substances.create(
#         substance=NOx, raster=raster, value=emission_unit_to_si(1000, "ton/year")
#     )
#     src1.substances.create(
#         substance=SOx, raster=raster, value=emission_unit_to_si(1.0, "kg/s")
#     )
#     src2 = inventory.gridsources.create(
#         name="gridsource2",
#         activitycode1=inventory.base_set.code_set1.codes.get(code="3"),
#     )
#     src2.activities.create(
#         activity=activities[0],
#         raster=raster,
#         rate=activity_rate_unit_to_si(1000, "m3/year"),
#     )

#     df = inventory.aggregate_emissions(
#         source_ef_set, road_ef_set, substances=[NOx, SOx], code_set_index=1
#     )
#     assert df.max().max() > 0
#     x1, y1, x2, y2 = gdal_raster.extent

#     left_half_extent = Polygon(
#         (
#             (x1, y1),
#             (x1 + 0.5 * (x2 - x1), y1),
#             (x1 + 0.5 * (x2 - x1), y2),
#             (x1, y2),
#             (x1, y1),
#         ),
#         srid=raster.srid,
#     )

#     df = inventory.aggregate_emissions(
#         source_ef_set,
#         road_ef_set,
#         name="gridsource1",
#         substances=[SOx],
#         code_set_index=1,
#         polygon=left_half_extent,
#         sourcetypes=["grid"],
#     )
#     assert len(df) == 1
#     assert df.index[0] == ("3", "Diffuse sources")
#     assert df.columns[0] == ("emission [ton/year]", "SOx")
#     # reference emission: "seconds of year" * "grid fraction in polygon" / "kg/ton"
#     ref_emis = 1.0 * 365.25 * 24 * 3600 * 0.4 / 1000
#     assert ref_emis == pytest.approx(df.values[0, 0], 1e-5)

# def test_aggregate_emissions_with_filters(
#     self,
#     inventories,
#     road_ef_sets,
#     source_ef_sets,
#     roadsources,
# ):
#     NOx = Substance.objects.get(slug="NOx")
#     SOx = Substance.objects.get(slug="SOx")
#     road_ef_set = road_ef_sets[0]
#     other_road_ef_set = road_ef_sets[2]
#     inventory = inventories[0]
#     empty_inventory = inventories[3]

#     df_road1 = inventory.aggregate_emissions(
#         road_ef_set=road_ef_set,
#         substances=[NOx, SOx],
#         code_set_index=1,
#         road_ids=[roadsources[0].id],
#     )

#     df_road2 = inventory.aggregate_emissions(
#         road_ef_set=road_ef_set,
#         substances=[NOx, SOx],
#         code_set_index=1,
#         road_ids=[roadsources[1].id],
#     )
#     assert len(df_road1) == 2
#     assert df_road1.index[0] == ("1.3.1", "Light vehicles")
#     assert df_road1.index[1] == ("1.3.2", "Heavy vehicles")
#     assert df_road1.columns[0] == ("emission [ton/year]", "NOx")
#     assert df_road1.columns[1] == ("emission [ton/year]", "SOx")
#     assert numpy.any(df_road1 != df_road2)

#     with pytest.raises(ValueError):
#         inventory.aggregate_emissions()

#     with pytest.raises(ValueError):
#         inventory.aggregate_emissions(road_ef_set=other_road_ef_set)

#     with pytest.raises(ValueError):
#         empty_inventory.aggregate_emissions(road_ef_set=other_road_ef_set)

#     empty_df = empty_inventory.aggregate_emissions(
#         road_ef_set=other_road_ef_set, substances=NOx
#     )
#     assert len(empty_df) == 0

# def test_list_substances(
#     self,
#     inventories,
#     road_ef_sets,
#     source_ef_sets,
#     roadsources,
#     pointsources,
#     areasources,
#     activities,
# ):
#     NOx = Substance.objects.get(slug="NOx")
#     SOx = Substance.objects.get(slug="SOx")
#     road_ef_set = road_ef_sets[0]
#     source_ef_set = source_ef_sets[0]
#     inventory = inventories[0]
#     substances = inventory.list_substances(source_ef_set, road_ef_set)

#     assert substances == [NOx, SOx]

# def test_emissions(self, inventories, road_ef_sets, source_ef_sets, roadsources):
#     inv = inventories[0]
#     road_ef_set = road_ef_sets[0]
#     with pytest.raises(ValueError):
#         inv.emissions("bla bla", road_ef_set)
#     cur = inv.emissions("road", road_ef_sets[0])
#     recs = cur.fetchall()
#     assert len(recs) > 0


class TestVerticalDist:
    def test_create_vertical_dist(self, ifactory):
        # breakpoint()
        domain = ifactory.edb.domain()
        vdist = domain.vertical_dists.create(
            name="residential heating", weights="[[5, 0], [10, 0.3], [15, 0.7]]"
        )
        assert len(np.array(ast.literal_eval(vdist.weights))) == 3

    def test_str(self, vertical_dist):
        assert str(vertical_dist) == vertical_dist.name
