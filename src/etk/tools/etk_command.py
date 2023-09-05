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

# sheets in order of import
SHEETNAMES = ("codesets", "pointsources")


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

        Current database is {db_path} (set by $ETK_DATABASE_PATH)
        """,
    )
    parser.add_argument(
        "command",
        help="Subcommand to run",
        choices=("migrate", "create", "import", "export"),
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
        sub_parser.add_argument("sheet", help="Sheet to import", choices=SHEETNAMES)
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
                "Database does not exist, first run " "'etk create' or 'etk migrate'\n"
            )
            sys.exit(1)
        if args.sheet == "pointsources":
            editor.import_pointsources(args.filename, unit=args.unit)

    elif main_args.command == "export":
        sub_parser = argparse.ArgumentParser(description="Export data to file")
        args = sub_parser.parse_args(sys.argv[2:])
        editor.export_data(*args)
