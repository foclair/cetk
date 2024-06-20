import ast

from openpyxl import Workbook

from etk.edb.const import DEFAULT_EMISSION_UNIT, WGS84_SRID
from etk.edb.importers.source_import import (
    OPTIONAL_COLUMNS_POINT,
    REQUIRED_COLUMNS_AREA,
    REQUIRED_COLUMNS_POINT,
)
from etk.edb.models import (
    Activity,
    ActivityCode,
    AreaSource,
    AreaSourceSubstance,
    CodeSet,
    EmissionFactor,
    Facility,
    PointSource,
    PointSourceSubstance,
    Substance,
)
from etk.edb.models.timevar_models import Timevar
from etk.edb.units import activity_rate_unit_from_si, emis_conversion_factor_from_si


def export_sources(export_filepath, srid=WGS84_SRID, unit=DEFAULT_EMISSION_UNIT):
    # Create a new Excel workbook and remove standard first Sheet
    workbook = Workbook()
    del workbook["Sheet"]
    point_columns = REQUIRED_COLUMNS_POINT | OPTIONAL_COLUMNS_POINT
    worksheet = workbook.create_sheet(title="PointSource")
    create_source_sheet(
        worksheet, PointSource, point_columns, PointSourceSubstance, unit
    )

    worksheet = workbook.create_sheet(title="AreaSource")
    create_source_sheet(
        worksheet, AreaSource, REQUIRED_COLUMNS_AREA, AreaSourceSubstance, unit
    )

    worksheet = workbook.create_sheet(title="EmissionFactor")
    header = [
        "activity_name",
        "substance",
        "factor",
        "emissionfactor_unit",
        "activity_unit",
    ]
    worksheet.append(header)
    for emfac in EmissionFactor.objects.all():
        # all factors stored in SI, original factor unit at import not stored in db.
        factor_unit = "kg/" + emfac.activity.unit.split("/")[0]
        row_data = [
            emfac.activity.name,
            emfac.substance.slug,
            emfac.factor,
            factor_unit,
            emfac.activity.unit,
        ]
        worksheet.append(row_data)

    worksheet = workbook.create_sheet(title="CodeSet")
    header = ["name", "slug", "description"]
    worksheet.append(header)
    for cs in CodeSet.objects.all():
        worksheet.append([cs.name, cs.slug, cs.description])

    worksheet = workbook.create_sheet(title="ActivityCode")
    header = ["codeset_slug", "activitycode", "label", "vertical_distribution_slug"]
    worksheet.append(header)
    for ac in ActivityCode.objects.all():
        if ac.vertical_dist is not None:
            worksheet.append(
                [ac.code_set.slug, ac.code, ac.label, ac.vertical_dist.slug]
            )
        else:
            worksheet.append([ac.code_set.slug, ac.code, ac.label, ""])

    if len(Timevar.objects.all()) > 0:
        worksheet = workbook.create_sheet(title="Timevar")
        days_header = [
            "ID",
            "typeday",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        months_header = [
            " ",
            "month",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        time_intervals = [
            "00-01",
            "01-02",
            "02-03",
            "03-04",
            "04-05",
            "05-06",
            "06-07",
            "07-08",
            "08-09",
            "09-10",
            "10-11",
            "11-12",
            "12-13",
            "13-14",
            "14-15",
            "15-16",
            "16-17",
            "17-18",
            "18-19",
            "19-20",
            "20-21",
            "21-22",
            "22-23",
            "23-24",
        ]
        for tvar in Timevar.objects.all():
            worksheet.append(days_header)
            typeday_list = ast.literal_eval(tvar.typeday)
            for i in range(len(typeday_list)):
                if i == 0:
                    row_data = [tvar.name] + [time_intervals[i]] + typeday_list[i]
                else:
                    row_data = [""] + [time_intervals[i]] + typeday_list[i]
                worksheet.append(row_data)
            month_list = ast.literal_eval(tvar.month)
            worksheet.append(months_header)
            worksheet.append(["", ""] + month_list)

    # Save the workbook to the specified export path
    workbook.save(export_filepath)


def create_source_sheet(
    worksheet, model_type, REQUIRED_COLUMNS, SourceSubstanceModel, unit
):
    emis_conversion_factor = emis_conversion_factor_from_si(unit)
    # works for pointsource and areasource
    # Define the header row
    header = list(REQUIRED_COLUMNS.keys())
    codeset_slugs = [code.slug for code in CodeSet.objects.all()]
    codeset_ids = [CodeSet.objects.get(slug=slug).id for slug in codeset_slugs]
    codeset_columns = [f"activitycode_{slug}" for slug in codeset_slugs]
    # unique list of substance slugs for sources
    substance_slugs = list(
        set([ss.substance.slug for ss in SourceSubstanceModel.objects.all()])
    )
    substance_columns = [f"subst:{subst}" for subst in substance_slugs]
    header = header + codeset_columns + substance_columns + ["emission_unit"]
    activities = Activity.objects.all()
    if len(activities) > 0:
        activity_names = [activity.name for activity in activities]
        activity_columns = [f"act:{name}" for name in activity_names]
        header = header + activity_columns

    # Write the header to the worksheet
    worksheet.append(header)
    # Iterate through features and add data to the worksheet
    for source in model_type.objects.all():
        if source.timevar_id is not None:
            timevar_name = Timevar.objects.get(id=source.timevar_id).name
        else:
            timevar_name = ""
        #
        activitycodes = {}
        for i in codeset_ids:
            activitycode = getattr(source, f"activitycode{i}")
            activitycodes[i] = activitycode.code if activitycode is not None else ""

        row_data = [
            str(source.facility),
            Facility.objects.get(id=source.facility_id).name,
            source.name,
            source.geom.coords[1] if model_type == PointSource else source.geom.wkt,
        ]
        if model_type == PointSource:
            row_data.append(source.geom.coords[0])
        row_data.append(timevar_name)

        if hasattr(source, "chimney_height"):
            row_data.extend(
                [
                    source.chimney_height,
                    source.chimney_outer_diameter,
                    source.chimney_inner_diameter,
                    source.chimney_gas_speed,
                    source.chimney_gas_temperature,
                    source.house_width,
                    source.house_height,
                ]
            )

        for i in codeset_ids:
            row_data.append(activitycodes[i])

        source_substances = [ss.substance.slug for ss in source.substances.all()]
        emis_row = [
            source.substances.get(substance=Substance.objects.get(slug=slug).id).value
            if slug in source_substances
            else 0
            for slug in substance_slugs
        ]
        emis_row = [emis * emis_conversion_factor for emis in emis_row]
        row_data = row_data + emis_row + [unit]

        if len(activities) > 0:
            source_activities = [
                Activity.objects.get(id=sa.activity_id).name
                for sa in source.activities.all()
            ]
            source_activity_rates = dict()
            for act in source.activities.all():
                activity_unit = Activity.objects.get(id=act.activity_id).unit
                activity_rate = activity_rate_unit_from_si(act.rate, activity_unit)
                source_activity_rates[
                    Activity.objects.get(id=act.activity_id).name
                ] = activity_rate
            act_row = [
                source_activity_rates[name] if name in source_activities else 0
                for name in activity_names
            ]
            row_data = row_data + act_row

        worksheet.append(row_data)
