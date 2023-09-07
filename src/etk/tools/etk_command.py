"""Command line interface for managing a Clair emission inventory offline."""

import argparse
import logging
import sys
from pathlib import Path

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

from etk.edb import importers  # noqa
from etk.edb.models import Substance  # noqa
from etk.edb.importers import SHEET_NAMES  # noqa
from etk.emissions.calc import aggregate_emissions, get_used_substances  # noqa
from etk.emissions.views import create_pointsource_emis_table  # noqa


SOURCETYPES = ("point",)
DEFAULT_EMISSION_UNIT = "kg/year"

sheet_choices = SHEET_NAMES.append("All")


class Editor(object):
    def __init__(self):
        self.db_path = settings.DATABASES["default"]["NAME"]

    def migrate(self, template=False):
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

    def import_pointsources(self, filename, unit):
        importers.import_pointsources(filename, unit=unit)

    def import_pointsourceactivities(self, filename, unit, sheet):
        importers.import_pointsourceactivities(filename, unit=unit, import_sheets=sheet)

    def update_emission_tables(
        self, sourcetypes=None, unit=DEFAULT_EMISSION_UNIT, substances=None
    ):
        sourcetypes = sourcetypes or SOURCETYPES
        substances = substances or get_used_substances()
        if "point" in sourcetypes:
            create_pointsource_emis_table(substances=substances, unit=unit)

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



    def export_data(self):
        print("Not implemented")


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
            description="Migrate database {db_path}.",
            usage="usage: etk migrate",
        )
        sub_parser.add_argument(
            "--template",
            action="store_true",
            help="Migrate the template database",
        )
        args = sub_parser.parse_args(sys.argv[2:])
        editor.migrate(template=args.template)
    elif main_args.command == "import":
        sub_parser = argparse.ArgumentParser(
            description="Import data from an xlsx-file",
            usage="etk import <filename> <sheet> [options]",
        )
        sub_parser.add_argument(
            "filename", help="Path to xslx-file", type=check_and_get_path
        )
        sub_parser.add_argument(
            "sheet", help="Sheet to import. ", choices=sheet_choices
        )
        pointsource_grp = sub_parser.add_argument_group(
            "pointsources", description="Options for pointsource import"
        )
        pointsource_grp.add_argument(
            "--unit",
            default="ton/year",
            help="Unit of emissions to be imported, default=%(default)s",
        )
        args = sub_parser.parse_args(sys.argv[2:])
        if not Path(db_path).exists():
            sys.stderr.write(
                "Database " + db_path + " does not exist, first run "
                "'etk create' or 'etk migrate'\n"
            )
            sys.exit(1)
        if args.sheet == "PointSource":
            editor.import_pointsources(args.filename, unit=args.unit)
        elif args.sheet == "All":
            editor.import_pointsourceactivities(
                args.filename, unit=args.unit, sheet=SHEET_NAMES
            )
        else:
            editor.import_pointsourceactivities(
                args.filename, unit=args.unit, sheet=[args.sheet]
            )
        log.debug("Imported data from '{args.filename}' to '{db_path}")
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
        # TODO add argument to aggregate emissions within polygon

        args = sub_parser.parse_args(sys.argv[2:])
        if not Path(db_path).exists():
            sys.stderr.write("Database does not exist.\n")
            sys.exit(1)
        if args.update:
            editor.update_emission_tables(sourcetypes=args.sourcetypes, unit=args.unit)
        if args.aggregate is not None:
            editor.aggregate_emissions(
                args.aggregate,
                sourcetypes=args.sourcetypes,
                unit=args.unit,
                codeset=args.codeset,
            )

    elif main_args.command == "export":
        sub_parser = argparse.ArgumentParser(description="Export data to file")
        args = sub_parser.parse_args(sys.argv[2:])
        editor.export_data(*args)
