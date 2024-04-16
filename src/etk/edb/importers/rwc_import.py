import numpy as np
from django.core.exceptions import MultipleObjectsReturned
from django.db import IntegrityError
from openpyxl import load_workbook

from etk.edb.cache import cache_queryset
from etk.edb.models import (
    Activity,
    AreaSource,
    AreaSourceActivity,
    EmissionFactor,
    PointSource,
    PointSourceActivity,
    Substance,
)
from etk.edb.units import heating_demand_unit_to_si, heating_ef_unit_to_si

from .codeset_import import import_activitycodesheet, import_codesetsheet
from .eea_emfac_import import (
    EEA_Tables,
    EEAEmissionFactor,
    eea_appliances,
    eea_fuels,
    excluded_combinations,
)
from .source_import import cache_sources, import_sources
from .timevar_import import import_timevarsheet
from .utils import import_error, worksheet_to_dataframe


def import_residentialheating(
    filepath,
    srid=None,
    import_substances=None,
    return_message="",
    validation=False,
):
    """Import point-sources from xlsx or csv-file.

    args
        filepath: path to file

    options
        srid: srid of file, default is same srid as domain
        substances: list of substances for which emfacs should be imported,
                    if None, all substances for which emfacs exist in EEA are imported.
    """
    try:
        workbook = load_workbook(filename=filepath, data_only=True)
    except Exception as exc:
        return_message = import_error(str(exc), return_message, validation)

    return_dict = {}
    sheet_names = [sheet.title for sheet in workbook.worksheets]

    if "Timevar" in sheet_names:
        import_timevarsheet(workbook, return_message, return_dict, validation)

    if "CodeSet" in sheet_names:
        import_codesetsheet(workbook, return_message, return_dict, validation)

    if "ActivityCode" in sheet_names:
        import_activitycodesheet(workbook, return_message, return_dict, validation)

    if "PointSource" in sheet_names:
        ps, return_message = import_sources(
            filepath,
            srid=srid,
            return_message=return_message,
            validation=validation,
            type="point",
        )
        return_dict.update(ps)
        data = workbook["PointSource"].values
        df = worksheet_to_dataframe(data)
        column_names = df.keys()
        fuel_types_pointsources = [
            name[7:] for name in column_names if name.startswith("energy_")
        ]
    else:
        fuel_types_pointsources = []

    if "AreaSource" in sheet_names:
        ps, return_message = import_sources(
            filepath,
            srid=srid,
            return_message=return_message,
            validation=validation,
            type="area",
        )
        return_dict.update(ps)
        data = workbook["AreaSource"].values
        df = worksheet_to_dataframe(data)
        column_names = df.keys()
        fuel_types_areasources = [
            name[7:] for name in column_names if name.startswith("energy_")
        ]
    else:
        fuel_types_areasources = []

    # unique fuel types
    fuel_types = set(fuel_types_pointsources + fuel_types_areasources)
    fuel_appliance_distribution = worksheet_to_dataframe(
        workbook["FuelApplianceDistribution"].values
    )

    ef_overwrite = worksheet_to_dataframe(workbook["EF_Overwrite"].values)

    for fuel, appliance in excluded_combinations:
        fuel_appliance_weight = fuel_appliance_distribution.loc[
            fuel_appliance_distribution["fuel"] == fuel, appliance
        ].values[0]
        if isinstance(fuel_appliance_weight, (int, float)):
            if fuel_appliance_weight > 0:
                if not any(
                    (ef_overwrite["fuel"] == fuel)
                    & (ef_overwrite["appliance"] == appliance)
                ):
                    return_message = import_error(
                        "There are no emfacs for the fuel+appliance combination "
                        + fuel
                        + "+"
                        + appliance
                        + " in EEA, add manually to EF_Overwrite sheet.",
                        return_message,
                        validation,
                    )

    # TODO what if all energy_fuel values are 0 for some column,
    # should still require appliance weights are set? Currently doing so.
    fuel_appliance_weights = {}
    for fuel in fuel_types:
        if fuel not in eea_fuels and fuel not in ef_overwrite["fuel"]:
            return_message = import_error(
                f"The fuel {fuel} is not in EEA Guidebook, add emission factors "
                + "manually to EF_Overwrite sheet.",
                return_message,
                validation,
            )
        fuel_appliance_weights[fuel] = {}
        for appliance in eea_appliances:
            weight = fuel_appliance_distribution.loc[
                fuel_appliance_distribution["fuel"] == fuel, appliance
            ].values[0]
            if isinstance(weight, (int, float)):
                if weight > 0:
                    fuel_appliance_weights[fuel][appliance] = weight
        if fuel_appliance_weights[fuel] == {}:
            return_message = import_error(
                f"Weights for energy consumption per fuel type are missing for {fuel}. "
                + "Fill positive numerical values in sheet FuelApplianceDistribution.",
                return_message,
                validation,
            )
        weight_sum = sum(fuel_appliance_weights[fuel].values())
        for appliance in fuel_appliance_weights[fuel].keys():
            fuel_appliance_weights[fuel][appliance] = (
                fuel_appliance_weights[fuel][appliance] / weight_sum
            )

    activities = cache_queryset(
        Activity.objects.prefetch_related("emissionfactors").all(), "name"
    )
    update_activities = []
    create_activities = {}
    drop_emfacs = []
    for fuel in fuel_types:
        for appliance in fuel_appliance_weights[fuel].keys():
            activity_name = fuel + "_" + appliance  # + facility?! + NFR
            try:
                activity = activities[activity_name]
                setattr(activity, "name", activity_name)
                setattr(activity, "unit", "GJ/yr")
                update_activities.append(activity)
                drop_emfacs += list(activities[activity_name].emissionfactors.all())
            except KeyError:
                activity = Activity(name=activity_name, unit="GJ/yr")
                if activity_name not in create_activities:
                    create_activities[activity_name] = activity
    Activity.objects.bulk_create(create_activities.values())
    Activity.objects.bulk_update(
        update_activities,
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

    # TODO or do we prefer to import eea_emfacs as migration to template database?
    if EEAEmissionFactor.objects.count() == 0:
        return_message = import_error(
            "First need to import emission factor table from EEA. "
            + "Download csv at https://efdb.apps.eea.europa.eu/ ",
            return_message,
            validation,
        )
    create_emfacs = []
    for fuel in fuel_types:
        for appliance in fuel_appliance_weights[fuel].keys():
            activity_name = fuel + "_" + appliance  # + facility?!
            activity = Activity.objects.get(name=activity_name)
            if fuel not in ["wood_residue", "lpg"]:
                EEA_ref = EEA_Tables[activity_name]
            elif fuel == "wood_residue":
                EEA_ref = EEA_Tables["wood" + "_" + appliance]
            elif fuel == "lpg":
                EEA_ref = EEA_Tables["natural_gas" + "_" + appliance]
            eea_emfacs = EEAEmissionFactor.objects.filter(
                nfr_code=EEA_ref["NFR"], table="Table_" + EEA_ref["table"]
            )
            for eea_emfac in eea_emfacs:
                substance = eea_emfac.substance
                if isinstance(substance, type(None)):
                    # skip unknown substance, substance in EEA not contained in edb.
                    continue
                if import_substances is not None:
                    if substance.name not in import_substances:
                        # only import substances in import_substances
                        continue
                if any(
                    [
                        (ef.substance == substance)
                        and (ef.activity.name == activity_name)
                        for ef in create_emfacs
                    ]
                ):
                    # duplicates in EEA
                    continue
                if any(
                    (ef_overwrite["fuel"] == fuel)
                    & (ef_overwrite["appliance"] == appliance)
                    & (ef_overwrite["substance"] == substance.name)
                ):
                    index = (
                        (ef_overwrite["fuel"] == fuel)
                        & (ef_overwrite["appliance"] == appliance)
                        & (ef_overwrite["substance"] == substance.name)
                    )
                    if len(index) > 1:
                        return_message = import_error(
                            "Several emfacs are given for fuel, appliance, substance: "
                            + f" {fuel, appliance, substance} in EF_Overwrite. "
                            + "Emission factors should be defined uniquely. ",
                            return_message,
                            validation,
                        )
                    factor = ef_overwrite.loc[index]["emission factor"].values[0]
                    factor_unit = ef_overwrite.loc[index]["unit"].values[0]
                else:
                    factor = eea_emfac.value
                    factor_unit = eea_emfac.unit
                    # convert emfac to kg/GJ
                if factor_unit == "% of PM2.5":
                    # Too complicated to look for EF_Overwrite of pm2.5, would not be
                    # intuitive to combine EEA emfac with overwritten emfac
                    substPM25 = Substance.objects.get(name="PM2.5")
                    try:
                        EF_PM25 = EEAEmissionFactor.objects.get(
                            nfr_code=EEA_ref["NFR"],
                            table="Table_" + EEA_ref["table"],
                            substance=substPM25,
                        )
                    except MultipleObjectsReturned:
                        # Duplicates exist in EEA database, check value
                        EFs_PM25 = EEAEmissionFactor.objects.filter(
                            nfr_code=EEA_ref["NFR"],
                            table="Table_" + EEA_ref["table"],
                            substance=substPM25,
                        )
                        values = [EF_PM25.value for EF_PM25 in EFs_PM25]
                        EF_PM25 = EFs_PM25.first()
                        if EF_PM25.value != np.mean(values):
                            return_message = import_error(
                                "Several emfacs given for PM2.5 in Table "
                                + f"{EEA_ref['table']} for NFR {EEA_ref['NFR']}. "
                                + "These emfacs should have only 1 value.",
                                return_message,
                                validation,
                            )
                    factor = EF_PM25.value * factor * 0.01
                    factor_unit = EF_PM25.unit
                factor = heating_ef_unit_to_si(factor, factor_unit)
                emfac = EmissionFactor(
                    activity=activity, substance=substance, factor=factor
                )
                create_emfacs.append(emfac)
    try:
        EmissionFactor.objects.bulk_create(create_emfacs)
    except IntegrityError:
        return_message = import_error(
            "Two emission factors for same activity and substance are given.",
            return_message,
            validation,
        )
    return_dict.update(
        {
            "emission_factors": {
                "updated": len(drop_emfacs),
                "created": len(create_emfacs) - len(drop_emfacs),
            }
        }
    )

    if "PointSource" in sheet_names:
        # now that activities, pointsources and emission factors are created,
        # pointsourceactivities can be created.
        # should not matter whether activities and emission factors were imported from
        # same file or existed already in database.
        pointsourceactivities = cache_queryset(
            PointSourceActivity.objects.all(), ["activity", "source"]
        )
        data = workbook["PointSource"].values
        df_pointsource = worksheet_to_dataframe(data)
        activities = cache_queryset(Activity.objects.all(), "name")
        pointsources = cache_sources(
            PointSource.objects.select_related("facility")
            .prefetch_related("substances")
            .all()
        )
        create_pointsourceactivities = []
        update_pointsourceactivities = []
        for row_key, row in df_pointsource.iterrows():
            pointsource = pointsources[str(row["facility_id"]), str(row["source_name"])]
            for fuel in fuel_types_pointsources:
                if row["energy_" + fuel] > 0:
                    energy = row["energy_" + fuel]
                    for appliance in fuel_appliance_weights[fuel].keys():
                        if fuel_appliance_weights[fuel][appliance] > 0:
                            activity_name = fuel + "_" + appliance  # + facility?!
                            try:
                                activity = activities[activity_name]
                            except KeyError:
                                return_message = import_error(
                                    f"unknown activity '{activity_name}'"
                                    + f" for pointsource '{row['source_name']}'",
                                    return_message,
                                    validation,
                                )
                            rate = energy * fuel_appliance_weights[fuel][appliance]
                            rate = heating_demand_unit_to_si(rate, row["unit"])
                            # original unit stored in activity.unit, but
                            # pointsourceactivity.rate stored as GJ / s.
                        try:
                            psa = pointsourceactivities[activity, pointsource]
                            setattr(psa, "rate", rate)
                            update_pointsourceactivities.append(psa)
                        except KeyError:
                            psa = PointSourceActivity(
                                activity=activity, source=pointsource, rate=rate
                            )
                            create_pointsourceactivities.append(psa)

        PointSourceActivity.objects.bulk_create(create_pointsourceactivities)
        PointSourceActivity.objects.bulk_update(
            update_pointsourceactivities, ["activity", "source", "rate"]
        )
        return_dict.update(
            {
                "pointsourceactivity": {
                    "updated": len(update_pointsourceactivities),
                    "created": len(create_pointsourceactivities),
                }
            }
        )

    if "AreaSource" in sheet_names:
        areasourceactivities = cache_queryset(
            AreaSourceActivity.objects.all(), ["activity", "source"]
        )
        data = workbook["AreaSource"].values
        df_areasource = worksheet_to_dataframe(data)
        activities = cache_queryset(Activity.objects.all(), "name")
        areasources = cache_sources(
            AreaSource.objects.select_related("facility")
            .prefetch_related("substances")
            .all()
        )
        create_areasourceactivities = []
        update_areasourceactivities = []
        for row_key, row in df_areasource.iterrows():
            areasource = areasources[str(row["facility_id"]), str(row["source_name"])]
            for fuel in fuel_types_areasources:
                if row["energy_" + fuel] > 0:
                    energy = row["energy_" + fuel]
                    for appliance in fuel_appliance_weights[fuel].keys():
                        if fuel_appliance_weights[fuel][appliance] > 0:
                            activity_name = fuel + "_" + appliance  # + facility?!
                            try:
                                activity = activities[activity_name]
                            except KeyError:
                                return_message = import_error(
                                    f"unknown activity '{activity_name}'"
                                    + f" for areasource '{row['source_name']}'",
                                    return_message,
                                    validation,
                                )
                            rate = energy * fuel_appliance_weights[fuel][appliance]
                            rate = heating_demand_unit_to_si(rate, row["unit"])
                            # original unit stored in activity.unit, but
                            # areasourceactivity.rate stored as GJ / s.
                        try:
                            asa = areasourceactivities[activity, areasource]
                            setattr(asa, "rate", rate)
                            update_areasourceactivities.append(asa)
                        except KeyError:
                            asa = AreaSourceActivity(
                                activity=activity, source=areasource, rate=rate
                            )
                            create_areasourceactivities.append(asa)
        AreaSourceActivity.objects.bulk_create(create_areasourceactivities)
        AreaSourceActivity.objects.bulk_update(
            update_areasourceactivities, ["activity", "source", "rate"]
        )
        return_dict.update(
            {
                "areasourceactivity": {
                    "updated": len(update_areasourceactivities),
                    "created": len(create_areasourceactivities),
                }
            }
        )

    return return_dict, return_message
