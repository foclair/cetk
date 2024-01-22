"""Utility functions for emission processing."""

import logging
import os
import shutil
import subprocess
from argparse import ArgumentTypeError
from pathlib import Path
from subprocess import CalledProcessError, SubprocessError  # noqa

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
    return DATABASE_DIR / "eclair.sqlite"


def check_and_get_path(filename):
    p = Path(filename)
    if p.exists():
        return p
    else:
        raise ArgumentTypeError(f"Input file {filename} does not exist")


def run_update_emission_tables(db_path=None, **kwargs):
    """update emission tables."""
    cmd_args = ["--update"]
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    return run("etk", "calc", db_path=db_path, *cmd_args)


def run_aggregate_emissions(filename, db_path=None, **kwargs):
    """write aggregated emissions to file."""
    cmd_args = ["--aggregate", str(filename)]
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    return run("etk", "calc", db_path=db_path, *cmd_args)


def run_rasterize_emissions(outputpath, **kwargs):
    """rasterize emissions and store as NetCDF."""
    cmd_args = ["--rasterize", str(outputpath)]
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    return run("etk", "calc", *cmd_args)


def run_import(filename, sheet, dry_run=False, db_path=None, **kwargs):
    """run import in a sub-process."""
    cmd_args = [str(filename)]
    cmd_args.append("--sheets")
    cmd_args.append(str(sheet))
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    if dry_run:
        cmd_args.append("--dryrun")
    return run("etk", "import", *cmd_args)


def run_import_residential_heating(filename, dry_run=False, **kwargs):
    """run import residential heating in a sub-process."""
    cmd_args = [str(filename)]
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    if dry_run:
        cmd_args.append("--dryrun")
    cmd_args.append("--residential-heating")
    return run("etk", "import", *cmd_args)


def run_import_eea_emfacs(filename):
    return run("etk", "import_eea_emfacs", filename)


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


def run(*args, db_path=None):
    env = (
        os.environ if db_path is None else {**os.environ, "ETK_DATABASE_PATH": db_path}
    )
    print(args)
    # try:
    proc = subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, env=env
    )
    # except subprocess.CalledProcessError as e:
    #     error = e.stderr.decode("utf-8")
    #     log.debug(f"command {'_'.join(args)} failed with error {error}")
    log.debug(f"command {'_'.join(args)} finished with status code {proc.returncode}")
    return proc.stdout, proc.stderr
