"""Command line interface for managing a Clair emission inventory offline."""

import argparse
import datetime
import logging
import os
import sys

# import traceback
from pathlib import Path

# from django.contrib.gis.geos import Polygon
from django.db import transaction

import etk
from etk.db import run_migrate
from etk.tools.utils import (
    CalledProcessError,
    SubprocessError,
    check_and_get_path,
    create_from_template,
    get_db,
    get_template_db,
)

log = logging.getLogger(__name__)

settings = etk.configure()

from etk.edb import exporters, importers  # noqa
from etk.edb.const import DEFAULT_SRID, SHEET_NAMES  # noqa
from etk.edb.models import Settings, Substance  # noqa
from etk.edb.rasterize.rasterizer import EmissionRasterizer, Output  # noqa
from etk.emissions.calc import aggregate_emissions, get_used_substances  # noqa
from etk.emissions.views import (  # noqa
    create_areasource_emis_table,
    create_pointsource_emis_table,
)

SOURCETYPES = ("point", "area")
DEFAULT_EMISSION_UNIT = "kg/year"


sheet_choices = ["All"]
sheet_choices.extend(SHEET_NAMES)


class DryrunAbort(Exception):
    """Forcing abort of database changes when doing dryrun."""

    pass


class Editor(object):
    def __init__(self):
        self.db_path = settings.DATABASES["default"]["NAME"]

    def migrate(self, template=False, db_path=None):
        if db_path is None:
            if template:
                db_path = get_template_db()
            else:
                db_path = get_db()
        log.debug(f"Running migrations for database {db_path}")
        try:
            std_out, std_err = run_migrate(db_path=db_path)
        except (CalledProcessError, SubprocessError) as err:
            log.error(f"Error while migrating {db_path}: {err}")
        log.debug(f"Successfully migrated database {db_path}")

    def import_pointsources(self, filename, dry_run=False):
        # reverse all created/updated DataModels if doing dry run or error occurs.
        try:
            with transaction.atomic():
                progress = importers.import_sources(
                    filename, validation=dry_run, type="point"
                )
                if dry_run:
                    raise DryrunAbort
        except DryrunAbort:
            pass
        return progress

    def import_areasources(self, filename, dry_run=False):
        # reverse all created/updated DataModels if doing dry run or error occurs.
        try:
            with transaction.atomic():
                progress = importers.import_sources(
                    filename, validation=dry_run, type="area"
                )
                if dry_run:
                    raise DryrunAbort
        except DryrunAbort:
            pass
        return progress

    def import_sourceactivities(self, filename, sheet, dry_run=False):
        # works for point and area, recognizes from tab name which one.
        try:
            with transaction.atomic():
                progress = importers.import_sourceactivities(
                    filename, import_sheets=sheet, validation=dry_run
                )
                if dry_run:
                    raise DryrunAbort
        except DryrunAbort:
            pass
        return progress

    def update_emission_tables(
        self, sourcetypes=None, unit=DEFAULT_EMISSION_UNIT, substances=None
    ):
        sourcetypes = sourcetypes or SOURCETYPES
        substances = substances or get_used_substances()
        if "point" in sourcetypes:
            create_pointsource_emis_table(substances=substances, unit=unit)
        if "area" in sourcetypes:
            create_areasource_emis_table(substances=substances, unit=unit)

    def aggregate_emissions(
        self,
        filename,
        sourcetypes=None,
        unit=DEFAULT_EMISSION_UNIT,
        codeset=None,
        substances=None,
    ):
        substances = substances or get_used_substances()
        df = aggregate_emissions(
            sourcetypes=sourcetypes, unit=unit, codeset=codeset, substances=substances
        )
        try:
            df.to_csv(filename, sep=";")
        except Exception as err:
            log.error(
                f"could not write aggregated emission to file {filename}: {str(err)}"
            )
            sys.exit(1)

    def rasterize_emissions(
        self,
        outputpath,
        nx,
        ny,
        sourcetypes=None,
        unit=DEFAULT_EMISSION_UNIT,
        codeset=None,
        substances=None,
        begin=None,
        end=None,
        extent=None,
        srid=None,
        timezone=None,
    ):
        # TODO souretypes and codeset not actually given as arguments to rasterizer yet!
        substances = substances or get_used_substances()
        timezone = timezone or datetime.timezone.utc
        extent = extent or Settings.get_current().extent.extent
        # Settings.extent is a Polygon, Settings.extent.extent a tuple (x1, y1, x2, y2)
        if extent is None:
            log.error(
                f"could not rasterize emissions to path {outputpath}: extent not set"
                + " for database nor rasterizer"
            )
        srid = srid or DEFAULT_SRID
        try:
            output = Output(
                extent=extent, timezone=timezone, path=outputpath, srid=srid
            )
            rasterizer = EmissionRasterizer(output, nx=nx, ny=ny)
            rasterizer.process(substances, begin=begin, end=end, unit=unit)
        except Exception as err:
            log.error(f"could not rasterize emissions to path {outputpath}: {str(err)}")
            # log.error(traceback.print_exc())
            sys.exit(1)

    def export_data(self, filename):
        exporters.export_sources(filename)
        return True


def main():
    db_path = get_db() or "unspecified"
    parser = argparse.ArgumentParser(
        description="Manage Clair offline emission inventories",
        usage=f"""etk <command> [<args>]

        Main commands are:
        migrate  migrate an sqlite inventory
        import   import data
        export   export data
        calc     calculate emissions

        Current database is {db_path} (set by $ETK_DATABASE_PATH)
        """,
    )
    parser.add_argument(
        "command",
        help="Subcommand to run",
        choices=("migrate", "create", "import", "export", "calc"),
    )
    main_args = parser.parse_args(args=sys.argv[1:2])

    editor = Editor()
    if main_args.command == "create":
        sub_parser = argparse.ArgumentParser(
            description="Create database from template.",
            usage="etk create <filename>",
        )
        sub_parser.add_argument(
            "filename",
            help="Path of new database",
        )
        args = sub_parser.parse_args(sys.argv[2:])
        create_from_template(args.filename)
        log.debug(
            "Created new database '{args.filename}' from template '{get_template_db()}'"
        )
        sys.exit(0)

    if (
        len(sys.argv) < 2
        and sys.argv[2] not in ("-h", "--help")
        and db_path == "unspecified"
    ):
        sys.stderr.write("No database specified, set by $ETK_DATABASE_PATH\n")
        sys.exit(1)

    if main_args.command == "migrate":
        sub_parser = argparse.ArgumentParser(
            description=f"Migrate database {db_path}.",
            usage="usage: etk migrate",
        )
        sub_parser.add_argument(
            "--template",
            action="store_true",
            help="Migrate the template database",
        )
        sub_parser.add_argument(
            "--dbpath",
            help="Specify database path manually",
        )
        args = sub_parser.parse_args(sys.argv[2:])
        editor.migrate(template=args.template, db_path=args.dbpath)
    elif main_args.command == "import":
        sub_parser = argparse.ArgumentParser(
            description="Import data from an xlsx-file",
            usage="etk import <filename> <sheet> [options]",
        )
        sub_parser.add_argument(
            "filename", help="Path to xslx-file", type=check_and_get_path
        )
        sub_parser.add_argument(
            "sheets", help="List of sheets to import, valid names {SHEET_NAMES}"
        )
        sub_parser.add_argument(
            "--dryrun",
            action="store_true",
            help="Do dry run to validate import file without actually importing data",
        )
        # pointsource_grp = sub_parser.add_argument_group(
        #     "pointsources", description="Options for pointsource import"
        # )
        args = sub_parser.parse_args(sys.argv[2:])
        if not Path(db_path).exists():
            sys.stderr.write(
                "Database " + db_path + " does not exist, first run "
                "'etk create' or 'etk migrate'\n"
            )
            sys.exit(1)
        if args.sheets == "PointSource":
            status = editor.import_sources(
                args.filename, dry_run=args.dryrun, type="point"
            )
        if args.sheets == "AreaSource":
            status = editor.import_sources(
                args.filename, dry_run=args.dryrun, type="area"
            )
        else:
            status = editor.import_sourceactivities(
                args.filename, sheet=args.sheets, dry_run=args.dryrun
            )
        log.debug("Imported data from '{args.filename}' to '{db_path}")
        sys.stdout.write(str(status))
        sys.exit(0)

    elif main_args.command == "calc":
        sub_parser = argparse.ArgumentParser(
            description="Calculate emissions",
            usage="etk calc [options]",
        )
        sub_parser.add_argument(
            "--unit",
            default=DEFAULT_EMISSION_UNIT,
            help="Unit of emissions, default=%(default)s",
        )
        sub_parser.add_argument(
            "--sourcetypes", nargs="*", help="Only sourcetypes", choices=SOURCETYPES
        )
        sub_parser.add_argument(
            "--substances",
            nargs="*",
            help="Only substances (default is all with emissions)",
            choices=Substance.objects.values_list("slug", flat=True),
            metavar=("NOx", "PM10"),
        )
        calc_grp = sub_parser.add_mutually_exclusive_group()
        calc_grp.add_argument(
            "--update", help="Create/update emission tables", action="store_true"
        )
        calc_grp.add_argument(
            "--aggregate", help="Aggregate emissions", metavar="FILENAME"
        )
        aggregate_grp = sub_parser.add_argument_group(
            "aggregate emissions", description="Options to aggregate emissions"
        )
        aggregate_grp.add_argument(
            "--codeset", help="Aggregate emissions by codeset", metavar="SLUG"
        )
        calc_grp.add_argument(
            "--rasterize", help="Rasterize emissions", metavar="OUTPUTPATH"
        )
        rasterize_grp = sub_parser.add_argument_group(
            "rasterize emissions", description="Settings to rasterize emissions"
        )
        rasterize_grp.add_argument(
            "--nx",
            help="Number of cells in x-direction in output raster",
            metavar="int",
        )
        rasterize_grp.add_argument(
            "--ny",
            help="Number of cells in y-direction in output raster",
            metavar="int",
        )
        rasterize_grp.add_argument(
            "--extent",
            help="Extent of output raster. Settings.extent is taken otherwise",
            metavar="x1,y1,x2,y2",
        )
        rasterize_grp.add_argument(
            "--srid",
            help="EPSG of output raster. 4-5 digits integer",
            metavar="EPSG",
        )
        rasterize_grp.add_argument(
            "--begin",
            help="when hourly rasters are desired, specify begin date."
            + " Time 00:00 assumed",
            metavar="2022-01-01",
        )
        rasterize_grp.add_argument(
            "--end",
            help="when hourly rasters are desired, specify end date"
            + " Time 00:00 assumed",
            metavar="2023-01-01",
        )
        # TODO add argument begin/end for rasterize
        # TODO add argument to aggregate emissions within polygon

        args = sub_parser.parse_args(sys.argv[2:])
        if not Path(db_path).exists():
            sys.stderr.write("Database does not exist.\n")
            sys.exit(1)
        if args.update:
            editor.update_emission_tables(sourcetypes=args.sourcetypes, unit=args.unit)
            sys.stdout.write("Successfully updated tables\n")
            sys.exit(0)
        if args.aggregate is not None:
            editor.aggregate_emissions(
                args.aggregate,
                sourcetypes=args.sourcetypes,
                unit=args.unit,
                codeset=args.codeset,
            )
            sys.stdout.write("Successfully aggregated emissions\n")
            sys.exit(0)
        if args.rasterize is not None:
            if args.extent is not None:
                x1, y1, x2, y2 = map(float, args.extent.split(","))
                # Create the extent tuple
                args.extent = (x1, y1, x2, y2)
            if args.begin is not None:
                args.begin = datetime.datetime.strptime(args.begin, "%Y-%m-%d").replace(
                    tzinfo=datetime.timezone.utc
                )
                if args.end is not None:
                    args.end = datetime.datetime.strptime(args.end, "%Y-%m-%d").replace(
                        tzinfo=datetime.timezone.utc
                    )
                else:
                    sys.stderr.write(
                        "If begin is specified," + " end has to be specified too.\n"
                    )
                    sys.exit(1)
            editor.rasterize_emissions(
                args.rasterize,
                int(args.nx),
                int(args.ny),
                sourcetypes=args.sourcetypes,
                unit=args.unit,
                extent=args.extent,
                srid=args.srid,
                begin=args.begin,
                end=args.end,
            )  # TODO add arguments for codeset, substances, begin/end, timezone!
            # could also add for polygon, but this filtering is not implemented yet!!
            sys.stdout.write("Successfully rasterized emissions\n")
            sys.exit(0)

    elif main_args.command == "export":
        sub_parser = argparse.ArgumentParser(
            description="Export data to xlsx-file",
            usage="etk export <filename> [options]",
        )
        sub_parser.add_argument("filename", help="Path to xslx-file")
        if not Path(db_path).exists():
            sys.stderr.write(
                "Database " + db_path + " does not exist, first run "
                "'etk create' or 'etk migrate'\n"
            )
            sys.exit(1)

        args = sub_parser.parse_args(sys.argv[2:])
        try:
            # Check if the file can be created at the given path
            os.access(args.filename, os.W_OK | os.X_OK)
        except Exception as e:
            sys.stderr.write(f"File {args.filename} cannot be created: \n {e} ")
            sys.exit(1)
        status = editor.export_data(args.filename)
        if status:
            sys.stdout.write(f"Exported data from {db_path} to {args.filename}.\n")
            sys.exit(0)
        else:
            sys.stderr.write("Did not export data, something went wrong.")
            sys.exit(1)
