"""Utility functions for emission processing."""
import argparse
import os
import shutil
import subprocess
from argparse import ArgumentTypeError
from collections.abc import Iterable
from pathlib import Path
from subprocess import CalledProcessError, SubprocessError  # noqa

from django.core import serializers

from etk import __version__, logging
from etk.edb.const import SHEET_NAMES

log = logging.getLogger(__name__)


def get_db():
    db_path = os.environ.get("ETK_DATABASE_PATH")
    return Path(db_path) if db_path is not None else None


def get_template_db():
    DATABASE_DIR = Path(
        os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "eclair"
        )
    )
    return DATABASE_DIR / "eclair.gpkg"


def check_and_get_path(filename):
    p = Path(filename)
    if p.exists():
        return p
    else:
        raise ArgumentTypeError(f"Input file {filename} does not exist")


def run_get_settings(db_path=None, **kwargs):
    """get settings from db."""
    cmd_args = []
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    stdout, stderr = run("etk", "info", db_path=db_path, *cmd_args)
    settings = next(serializers.deserialize("json", stdout)).object
    return settings


def run_update_emission_tables(db_path=None, **kwargs):
    """update emission tables."""
    cmd_args = ["--update"]
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    return run("etk", "calc", db_path=db_path, *cmd_args)


def run_aggregate_emissions(
    filename, db_path=None, codeset=None, substances=None, sourcetypes=None, unit=None
):
    """write aggregated emissions to file."""
    cmd_args = ["--aggregate", str(filename)]
    if codeset is not None:
        cmd_args += ["--codeset", codeset]
    if unit is not None:
        cmd_args += ["--unit", unit]
    if sourcetypes is not None:
        if isinstance(sourcetypes, str):
            sourcetypes = [sourcetypes]
        cmd_args += ["--sourcetypes"] + sourcetypes
    if substances is not None:
        if isinstance(substances, str):
            substances = [substances]
        cmd_args += ["--substances"] + substances
    return run("etk", "calc", db_path=db_path, *cmd_args)


def run_rasterize_emissions(
    outputpath,
    cellsize,
    extent=None,
    srid=None,
    begin=None,
    end=None,
    db_path=None,
    unit=None,
    sourcetypes=None,
    substances=None,
):
    """rasterize emissions and store as NetCDF."""
    cmd_args = ["--rasterize", str(outputpath), "--cellsize", str(cellsize)]
    if extent is not None:
        cmd_args += ["--extent"] + list(map(str, extent))
    if srid is not None:
        cmd_args += ["--srid", str(srid)]
    if begin is not None and end is not None:
        cmd_args += [
            "--begin",
            begin.strftime("%y%m%d%H"),
            "--end",
            end.strftime("%y%m%d%H"),
        ]
    if unit is not None:
        cmd_args += ["--unit", unit]
    if sourcetypes is not None:
        if isinstance(sourcetypes, str):
            sourcetypes = [sourcetypes]
        cmd_args += ["--sourcetypes"] + sourcetypes
    if substances is not None:
        if isinstance(substances, str):
            substances = [substances]
        cmd_args += ["--substances"] + substances

    return run("etk", "calc", db_path=db_path, *cmd_args)


def run_import(filename, sheets=SHEET_NAMES, dry_run=False, db_path=None, **kwargs):
    """run import in a sub-process."""
    cmd_args = [str(filename)]
    cmd_args.append("--sheets")

    if not isinstance(sheets, Iterable):
        cmd_args += [sheets]
    else:
        cmd_args += list(sheets)
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    if dry_run:
        cmd_args.append("--dryrun")
    return run("etk", "import", *cmd_args)


def run_export(filename, db_path=None, **kwargs):
    """run export in a sub-process, arguments to be added are unit and srid."""
    cmd_args = [str(filename)]
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    return run("etk", "export", db_path=db_path, *cmd_args)


def create_from_template(filename):
    """create from template."""
    shutil.copyfile(get_template_db(), filename)


def set_settings_srid(srid, db_path=None):
    return run("etk", "settings", "--srid", str(srid), db_path=db_path)


def run(*args, db_path=None):
    env = (
        os.environ if db_path is None else {**os.environ, "ETK_DATABASE_PATH": db_path}
    )
    proc = subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, env=env
    )
    log.debug(f"command {'_'.join(args)} finished with status code {proc.returncode}")
    return proc.stdout, proc.stderr


class VerboseAction(argparse.Action):

    """Argparse action to handle terminal verbosity level."""

    def __init__(self, option_strings, dest, default=logging.INFO, help=None):
        baselogger = logging.getLogger("etk")
        baselogger.setLevel(logging.DEBUG)
        if len(baselogger.handlers) == 0:
            self._loghandler = logging.create_terminal_handler(default)
            baselogger.addHandler(self._loghandler)
        super(VerboseAction, self).__init__(
            option_strings,
            dest,
            nargs=0,
            default=default,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        currentlevel = getattr(namespace, self.dest, logging.WARNING)
        self._loghandler.setLevel(currentlevel - 10)
        setattr(namespace, self.dest, self._loghandler.level)


class LogFileAction(argparse.Action):

    """Argparse action to setup logging to file."""

    def __call__(self, parser, namespace, values, option_string=None):
        baselogger = logging.getLogger("prepper")
        baselogger.addHandler(logging.create_file_handler(values))
        setattr(namespace, self.dest, values)


def add_standard_command_options(parser):
    """Add standard prepper command line options to *parser*."""
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s from etk " + __version__,
    )
    parser.add_argument(
        "-v",
        action=VerboseAction,
        dest="loglevel",
        default=logging.INFO,
        help="increase verbosity in terminal",
    )
    parser.add_argument(
        "-l",
        metavar="logfile",
        action=LogFileAction,
        dest="logfile",
        help="write verbose output to logfile",
    )
