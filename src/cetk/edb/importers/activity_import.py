"""import activities and emission-factors."""

from django.db import IntegrityError

from cetk.edb.cache import cache_queryset
from cetk.edb.models import (
    Activity,
    AreaSource,
    AreaSourceActivity,
    EmissionFactor,
    Facility,
    GridSource,
    GridSourceActivity,
    PointSource,
    PointSourceActivity,
    Substance,
)
from cetk.edb.units import activity_ef_unit_to_si

from .utils import import_error, worksheet_to_dataframe


def import_emissionfactorsheet(workbook, validation):
    return_dict = {}
    return_message = []
    activities = cache_queryset(
        Activity.objects.prefetch_related("emissionfactors").all(), "name"
    )
    data = workbook["EmissionFactor"].values
    df_activity = worksheet_to_dataframe(data)

    activity_names = df_activity["activity_name"]
    update_activities = {}
    create_activities = {}
    drop_emfacs = []
    for row_nr, activity_name in enumerate(activity_names):
        try:
            activity = activities[activity_name]
            if activity_name not in update_activities.keys():
                if df_activity["activity_unit"][row_nr] != activity.unit:
                    # check if all sources with this activity are updated.
                    error_message = (
                        "Changing activity rate unit for activity "
                        f"{activity_name} without updating all sources"
                        " in inventory with this activity. Define as new"
                        " activity by giving new name, or update all"
                        " sources with this activity simultaneously."
                    )
                    pointsource_ids = [
                        psa.source_id
                        for psa in PointSourceActivity.objects.filter(
                            activity_id=activity.id
                        )
                    ]
                    if len(pointsource_ids) > 0:
                        pointsources = [
                            PointSource.objects.get(id=i) for i in pointsource_ids
                        ]
                        facility_names = [
                            Facility.objects.get(id=source.facility_id).name
                            for source in pointsources
                        ]
                        source_names = [source.name for source in pointsources]
                        if "PointSource" in workbook.sheetnames:
                            new_pointsources = worksheet_to_dataframe(
                                workbook["PointSource"].values
                            )
                            for facility, source in zip(facility_names, source_names):
                                row_exists = (
                                    (new_pointsources["source_name"] == source)
                                    & (new_pointsources["facility_name"] == facility)
                                ).any()
                                if not row_exists:
                                    return_message.append(
                                        import_error(
                                            error_message, validation=validation
                                        )
                                    )
                        else:
                            return_message.append(
                                import_error(error_message, validation=validation)
                            )
                    areasource_ids = [
                        psa.source_id
                        for psa in AreaSourceActivity.objects.filter(
                            activity_id=activity.id
                        )
                    ]
                    if len(areasource_ids) > 0:
                        areasources = [
                            AreaSource.objects.get(id=i) for i in areasource_ids
                        ]
                        facility_names = [
                            Facility.objects.get(id=source.facility_id).name
                            for source in areasources
                        ]
                        source_names = [source.name for source in areasources]
                        if "AreaSource" in workbook.sheetnames:
                            new_areasources = worksheet_to_dataframe(
                                workbook["AreaSource"].values
                            )
                            for facility, source in zip(facility_names, source_names):
                                row_exists = (
                                    (new_areasources["source_name"] == source)
                                    & (new_areasources["facility_name"] == facility)
                                ).any()
                                if not row_exists:
                                    return_message.append(
                                        import_error(
                                            error_message, validation=validation
                                        )
                                    )
                        else:
                            return_message.append(
                                import_error(error_message, validation=validation)
                            )
                    gridsource_ids = [
                        psa.source_id
                        for psa in GridSourceActivity.objects.filter(
                            activity_id=activity.id
                        )
                    ]
                    if len(gridsource_ids) > 0:
                        gridsources = [
                            GridSource.objects.get(id=i) for i in gridsource_ids
                        ]
                        source_names = [source.name for source in gridsources]
                        if "GridSource" in workbook.sheetnames:
                            update_sources = [
                                name
                                in worksheet_to_dataframe(
                                    workbook["GridSource"].values
                                )["name"]
                                for name in gridsources
                            ]
                            if not all(update_sources):
                                return_message.append(
                                    import_error(
                                        error_message,
                                        validation=validation,
                                    )
                                )
                        else:
                            return_message.append(
                                import_error(error_message, validation=validation)
                            )
                    setattr(activity, "unit", df_activity["activity_unit"][row_nr])
                update_activities[activity_name] = activity
                drop_emfacs += list(activities[activity_name].emissionfactors.all())
            elif (
                df_activity["activity_unit"][row_nr]
                != update_activities[activity_name].unit
            ):
                return_message.append(
                    import_error(
                        f"conflicting units for activity '{activity_name}'",
                        validation=validation,
                    )
                )
        except KeyError:
            if activity_name not in create_activities:
                activity = Activity(
                    name=activity_name, unit=df_activity["activity_unit"][row_nr]
                )
                create_activities[activity_name] = activity
            else:
                if (
                    df_activity["activity_unit"][row_nr]
                    != create_activities[activity_name].unit
                ):
                    return_message.append(
                        import_error(
                            "multiple rows for the same activity " + str(activity_name),
                            validation=validation,
                        )
                    )
    Activity.objects.bulk_create(create_activities.values())
    Activity.objects.bulk_update(
        update_activities.values(),
        [
            "name",
            "unit",
        ],
    )
    # drop existing emfacs of activities that will be updated
    EmissionFactor.objects.filter(pk__in=[inst.id for inst in drop_emfacs]).delete()
    return_dict.update(
        {
            "activity": {
                "updated": len(update_activities),
                "created": len(create_activities),
            }
        }
    )
    data = workbook["EmissionFactor"].values
    df_emfac = worksheet_to_dataframe(data)
    substances = cache_queryset(Substance.objects.all(), "slug")
    activities = cache_queryset(Activity.objects.all(), "name")
    # unique together activity_name and substance
    emissionfactors = cache_queryset(
        EmissionFactor.objects.all(), ["activity", "substance"]
    )
    update_emfacs = []
    create_emfacs = []
    for row_nr in range(len(df_emfac)):
        activity_name = df_emfac.iloc[row_nr]["activity_name"]
        try:
            activity = activities[activity_name]
            subst = df_emfac.iloc[row_nr]["substance"]
            try:
                substance = substances[subst]
                factor = df_emfac.iloc[row_nr]["factor"]
                factor_unit = df_emfac.iloc[row_nr]["emissionfactor_unit"]
                activity_quantity_unit, time_unit = activity.unit.split("/")
                mass_unit, factor_quantity_unit = factor_unit.split("/")
                if activity_quantity_unit != factor_quantity_unit:
                    # emission factor and activity need to have the same unit
                    # for quantity, eg GJ, m3 "pellets", number of produces bottles
                    return_message.append(
                        import_error(
                            "Units for emission factor and activity rate for"
                            f" '{activity_name}'"
                            " are inconsistent, convert units before importing.",
                            validation=validation,
                        )
                    )
                else:
                    factor = activity_ef_unit_to_si(factor, factor_unit)
                try:
                    emfac = emissionfactors[(activity, substance)]
                    setattr(emfac, "activity", activity)
                    setattr(emfac, "substance", substance)
                    setattr(emfac, "factor", factor)
                    update_emfacs.append(emfac)
                except KeyError:
                    emfac = EmissionFactor(
                        activity=activity, substance=substance, factor=factor
                    )
                    create_emfacs.append(emfac)
            except KeyError:
                if subst == "PM2.5":
                    substance = substances["PM25"]
                else:
                    return_message.append(
                        import_error(
                            f"unknown substance '{subst}'"
                            f" for emission factor on row '{row_nr}'",
                            validation=validation,
                        )
                    )
        except KeyError:
            return_message.append(
                import_error(
                    f"unknown activity '{activity_name}'"
                    f" for emission factor on row '{row_nr}'",
                    validation=validation,
                )
            )
    try:
        EmissionFactor.objects.bulk_create(create_emfacs)
    except IntegrityError:
        return_message.append(
            import_error(
                "Two emission factors for same activity and substance are given.",
                validation=validation,
            )
        )
    EmissionFactor.objects.bulk_update(
        update_emfacs, ["activity", "substance", "factor"]
    )
    return_dict.update(
        {
            "emission_factors": {
                "updated": len(update_emfacs),
                "created": len(create_emfacs),
            }
        }
    )
    return return_dict, return_message
