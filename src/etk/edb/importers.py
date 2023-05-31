"""Data importers for the edb application."""

import logging

import numpy as np
import pandas as pd
from django.contrib.gis.geos import Point

# from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError  # , transaction

from etk.edb.const import WGS84_SRID
from etk.edb.models import (
    CodeSet,
    Facility,
    PointSource,
    PointSourceSubstance,
    Substance,
    Timevar,
)
from etk.edb.units import emission_unit_to_si  # , vehicle_ef_unit_to_si
from etk.tools.utils import cache_queryset

# import sys
# from os import path


# from django.db import transaction


# column facility and name are used as index and is therefore not included here
REQUIRED_COLUMNS = {
    "facility_id": np.str_,
    "x": float,
    "y": float,
    "facility_name": np.str_,
    "source_name": np.str_,
    "timevar": np.str_,
    "activitycode1": np.str_,
    "activitycode2": np.str_,
    "activitycode3": np.str_,
    "height": float,
    "outer_diameter": float,
    "inner_diameter": float,
    "gas_speed": float,
    "gas_temperature": float,
    "house_width": float,
    "house_height": float,
}

log = logging.getLogger(__name__)


class ImportError(Exception):
    """Error while importing emission data."""

    pass


def cache_pointsources(queryset):
    """Return dict of model instances with (facility__official_id, name): instance"""
    sources = {}
    for source in queryset:
        if source.facility is not None:
            sources[source.facility.official_id, source.name] = source
        else:
            sources[None, source.name] = source
    return sources


def cache_codeset(code_set):
    if code_set is None:
        return {}
    return cache_queryset(code_set.codes.all(), "code")


def import_pointsources(csvfile, encoding=None, srid=None, unit=None):
    """Import point-sources from csv-file.

    args
        csvfile: path to csvfile

    options
        encoding: encoding of csvfile (default is utf-8)
        srid: srid of csvfile, default is same srid as domain
        unit: unit of emissions, default is SI-units (kg/s)
    """
    # or change to user defined SRID?
    project_srid = WGS84_SRID
    # cache related models
    substances = cache_queryset(Substance.objects.all(), "slug")
    timevars = cache_queryset(Timevar.objects.all(), "name")
    facilities = cache_queryset(Facility.objects.all(), "official_id")
    pointsources = cache_pointsources(
        PointSource.objects.select_related("facility")
        .prefetch_related("substances")
        .all()
    )

    code_sets = [
        cache_codeset(CodeSet.objects.filter(slug=f"code_set{i}").first())
        for i in range(1, 4)
    ]
    # read csv-file
    with open(csvfile, encoding=encoding or "utf-8") as csvfile:
        log.debug("reading point-sources from csv-file")
        df = pd.read_csv(
            csvfile, sep=";", skip_blank_lines=True, comment="#", dtype=REQUIRED_COLUMNS
        )
    for col in REQUIRED_COLUMNS.keys():
        if col not in df.columns:
            raise ImportError(f"Missing required column '{col}'")

    # set dataframe index
    try:
        df.set_index(
            ["facility_id", "source_name"], verify_integrity=True, inplace=True
        )
    except ValueError as err:
        raise ImportError(
            f"Non-unique combination of facility_id and source_name: {err}"
        )
    update_facilities = []
    create_facilities = {}
    drop_substances = []
    create_substances = []
    update_sources = []
    create_sources = {}
    row_nr = 2
    for row_key, row in df.iterrows():
        row_dict = row.to_dict()

        # initialize activitycodes
        source_data = {
            "activitycode1": None,
            "activitycode2": None,
            "activitycode3": None,
        }

        # get pointsource coordinates
        try:
            if pd.isnull(row_dict["x"]) or pd.isnull(row_dict["y"]):
                raise ImportError(f"missing coordinates for source '{row_key}'")
            x = float(row_dict["x"])
            y = float(row_dict["y"])
        except ValueError:
            raise ImportError(f"Invalid coordinates on row {row_nr}")

        # create geometry
        source_data["geom"] = Point(x, y, srid=srid or project_srid).transform(
            4326, clone=True
        )

        # get chimney properties
        for attr, key in {
            "chimney_height": "height",
            "chimney_inner_diameter": "inner_diameter",
            "chimney_outer_diameter": "outer_diameter",
            "chimney_gas_speed": "gas_speed",
            "chimney_gas_temperature": "gas_temperature",
        }.items():
            if pd.isna(row_dict[key]):
                raise ImportError(f"Missing value for {key} on row {row_nr}")
            else:
                source_data[attr] = row_dict[key]

        # get downdraft parameters
        if not pd.isnull(row_dict["house_width"]):
            source_data["house_width"] = row_dict["house_width"]
        if not pd.isnull(row_dict["house_height"]):
            source_data["house_height"] = row_dict["house_height"]

        # get activitycodes
        for code_ind, code_set in enumerate(code_sets, 1):
            code_attribute = f"activitycode{code_ind}"
            if len(code_set) == 0:
                break
            code = row_dict[code_attribute]

            try:
                source_data[code_attribute] = code_set[code]
            except KeyError:
                raise ImportError(
                    f"Unknown activitycode{code_ind} '{code}' on row {row_nr}"
                )

        # get columns with tag values for the current row
        tag_keys = [key for key in row_dict.keys() if key.startswith("tag:")]
        # set tags dict for source
        source_data["tags"] = {
            key[4:]: row_dict[key] for key in tag_keys if pd.notna(row_dict[key])
        }

        # get timevar name and corresponding timevar
        timevar_name = row_dict["timevar"]
        if pd.notna(timevar_name):
            try:
                source_data["timevar"] = timevars[timevar_name]
            except KeyError:
                ImportError(
                    f"Timevar '{timevar_name}' " f"on row {row_nr} does not exist"
                )

        # get all column-names starting with "subst" whith value for the current row
        subst_keys = [
            key
            for key in row_dict.keys()
            if key.startswith("subst:") and pd.notna(row_dict[key])
        ]

        # create list of data dict for each substance emission
        emissions = {}
        for subst_key in subst_keys:
            subst = subst_key[6:]
            # dict with substance emission properties (value and substance)
            emis = {}
            emissions[subst] = emis

            # get substance
            try:
                emis["substance"] = substances[subst]
            except KeyError:
                raise ImportError(f"Undefined substance {subst}")

            try:
                emis["value"] = emission_unit_to_si(float(row_dict[subst_key]), unit)
            except ValueError:
                raise ImportError(
                    f"Invalid emission value {row_dict[subst_key]} on row {row_nr}"
                )
            except KeyError as err:
                raise ImportError(f"{err}")

        official_facility_id, source_name = row_key
        if pd.isna(official_facility_id):
            official_facility_id = None

        if pd.isna(source_name):
            raise ImportError(f"No name specified for point-source on row {row_nr}")

        if pd.isna(row_dict["facility_name"]):
            facility_name = None
        else:
            facility_name = row_dict["facility_name"]

        try:
            facility = facilities[official_facility_id]
            update_facilities.append(facility)
        except KeyError:
            if official_facility_id is not None:
                if official_facility_id in create_facilities:
                    facility = create_facilities[official_facility_id]
                else:
                    facility = Facility(
                        name=facility_name,
                        official_id=official_facility_id,
                    )
                    create_facilities[official_facility_id] = facility
            else:
                facility = None

        source_data["facility"] = facility
        source_key = (official_facility_id, source_name)
        try:
            source = pointsources[source_key]
            for key, val in source_data.items():
                setattr(source, key, val)
            update_sources.append(source)
            drop_substances += list(source.substances.all())
            create_substances += [
                PointSourceSubstance(source=source, **emis)
                for emis in emissions.values()
            ]
        except KeyError:
            source = PointSource(name=source_name, **source_data)
            if source_key not in create_sources:
                create_sources[source_key] = source
                create_substances += [
                    PointSourceSubstance(source=source, **emis)
                    for emis in emissions.values()
                ]
            else:
                raise ImportError(
                    f"multiple rows for the same point-source '{source_name}'"
                )
        row_nr += 1
    existing_facility_names = set([f.name for f in facilities.values()])
    duplicate_facility_names = []
    for official_id, f in create_facilities.items():
        if f.name in existing_facility_names:
            duplicate_facility_names.append(f.name)
    if len(duplicate_facility_names) > 0:
        raise ImportError(
            "The following facility names are already used in inventory but "
            f"for facilities with different official_id: {duplicate_facility_names}"
        )
    duplicate_facility_names = {}
    for f in create_facilities.values():
        if f.name in duplicate_facility_names:
            duplicate_facility_names[f.name] += 1
        else:
            duplicate_facility_names[f.name] = 1
    duplicate_facility_names = [
        name for name, nr in duplicate_facility_names.items() if nr > 1
    ]
    if len(duplicate_facility_names) > 0:
        raise ImportError(
            "The same facility name is used on multiple rows but "
            f"with different facility_id: {duplicate_facility_names}"
        )

    # adjusted by Eef because no inentory
    Facility.objects.bulk_create(create_facilities.values())
    Facility.objects.bulk_update(update_facilities, ["name"])

    # ensure PointSource.facility_id is not None
    for source in create_sources.values():
        if source.facility is not None:
            # changed by Eef, because IDs were None
            source.facility_id = (
                Facility.objects.filter(official_id=source.facility).first().id
            )

    PointSource.objects.bulk_create(create_sources.values())
    PointSource.objects.bulk_update(
        update_sources,
        [
            "name",
            "geom",
            "tags",
            "chimney_gas_speed",
            "chimney_gas_temperature",
            "chimney_height",
            "chimney_inner_diameter",
            "chimney_outer_diameter",
            "house_height",
            "house_width",
            "activitycode1",
            "activitycode2",
            "activitycode3",
        ],
    )

    # drop existing substance emissions of point-sources that will be updated
    PointSourceSubstance.objects.filter(
        pk__in=[inst.id for inst in drop_substances]
    ).delete()

    # ensure PointSourceSubstance.source_id is not None
    for emis in create_substances:
        emis.source_id = PointSource.objects.filter(name=emis.source).first().id
    PointSourceSubstance.objects.bulk_create(create_substances)

    return {
        "facility": {
            "updated": len(update_facilities),
            "created": len(create_facilities),
        },
        "source": {"updated": len(update_sources), "created": len(create_sources)},
    }


def import_timevars(timevar_data, overwrite=False):
    """import time-variation profiles."""

    # Timevar instances must not be created by bulk_create as the save function
    # is overloaded to calculate the normation constant.
    def make_timevar(data, timevarclass, subname=None):
        retdict = {}
        for name, timevar_data in data.items():
            try:
                typeday = timevar_data["typeday"]
                month = timevar_data["month"]

                if overwrite:
                    newobj, _ = timevarclass.objects.update_or_create(
                        name=name,
                        defaults={"typeday": typeday, "month": month},
                    )
                else:
                    try:
                        newobj = timevarclass.objects.create(
                            name=name, typeday=typeday, month=month
                        )
                    except IntegrityError:
                        raise IntegrityError(
                            f"{timevarclass.__name__} {name} "
                            f"already exist in inventory."
                        )
                retdict[name] = newobj
            except KeyError:
                raise ImportError(
                    f"Invalid specification of timevar {name}"
                    f", are 'typeday' and 'month' given?"
                )
        return retdict

    timevars = {}
    for vartype, subdict in timevar_data.items():
        if vartype == "emission":
            timevars["emission"] = make_timevar(timevar_data[vartype], Timevar)
        else:
            raise ImportError(f"invalid time-variation type '{vartype}' specified")
    return timevars


# class Command(InspectorCommand):
#     help = f"""Import point sources from csv-file

#     The csv-file should be ";"-separated.

#     Required column headers are:
#     {REQUIRED_COLUMNS}

#     For each substance to be imported, a column named 'subst:<slug>' should be added.
#     Where 'slug' refers to the substance slug.

#     For each tag to be added, a column named 'tag:<key>' should be added, where 'key'
#     refers to the tag key.

#     For each point-source to be imported, one row is added to the table. The emissions
#     for each source are specified in the "subst:<slug>" columns. All emissions should
#     be in the same unit (can be any units supported by Clair, the emissions and will
#     be converted to SI-units at import).

#     If a point-source with the same facility and name already exist in the inventory,
#     it will be updated and any emissions will be replaced by emissions specified in
#     the csv-table.
#     """

#     def add_arguments(self, parser):
#         parser.add_argument(
#             "csvfile",
#             metavar="FILENAME",
#             help="path to csv file with grid source specifications",
#         )
#         parser.add_argument(
#             "-u",
#             "--unit",
#             dest="unit",
#             metavar="UNIT",
#             required=True,
#             help="Unit for emissions to import",
#         )
#         parser.add_argument(
#             "--srid",
#             dest="srid",
#             metavar="SRID",
#             type=int,
#             help="srid of input rasters (default is domain srid)",
#         )
#         parser.add_argument(
#             "-m",
#             "--manager",
#             dest="manager",
#             metavar="USERNAME",
#             help="project manager",
#             required=True,
#         )
#         parser.add_argument(
#             "-p",
#             "--project",
#             dest="project",
#             metavar="SLUG",
#             help="project of target dataset",
#             required=True,
#         )
#         parser.add_argument(
#             "-i", "--inventory", metavar="SLUG", help="inventory slug", required=True
#         )
#         parser.add_argument(
#             "--encoding",
#             metavar="ENCODING",
#             help="encoding used in csv-file (default=utf-8)",
#             default="utf-8",
#         )

#     @transaction.atomic
#     def handle(self, *args, **options):
#         self.options = options

#         inventory = Inventory.objects.get(
#             slug=options["inventory"],
#             project__slug=options["project"],
#             project__manager__username=options["manager"],
#         )

#         csvfile = self.options["csvfile"]
#         srid = self.options["srid"]
#         unit = self.options["unit"]
#         encoding = self.options["encoding"]

#         if not path.exists(csvfile):
#             self.stderr.write(f"Import file {csvfile} does not exist")
#             sys.exit(1)
#         try:
#             done = import_pointsources(inventory, csvfile, encoding, srid, unit)
#         except ImportError as err:
#             self.stderr.write(f"Error during import: {err}")
#             sys.exit(1)

#         self.stdout.write(
#             f"created {done['facility']['created']} facilities,"
#             f" updated {done['facility']['updated']}"
#         )
#         self.stdout.write(
#             f"created {done['source']['created']} sources, "
#             f"   updated {done['source']['updated']}"
#         )


# code for spreadsheet

# try:
#     workbook = load_workbook(filename=self.sourcefile)
# except Exception as exc:
#     raise CommandError(str(exc))
# worksheet = workbook.worksheets[0]
# if len(workbook.worksheets) > 1:
#     log.debug("debug: multiple sheets in spreadsheet, only importing 1st.")
# data = worksheet.values
# cols = next(data)[1:]
# data = list(data)
# idx = [r[0] for r in data]
# data = (islice(r, 1, None) for r in data)
# df = pd.DataFrame(data, index=idx, columns=cols)
# print(df)
# # TODO same here with df as in parse_csv ? add to test_importers as well
