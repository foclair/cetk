"""Utility functions for emission processing."""

import logging
import os
import shutil
import subprocess
from argparse import ArgumentTypeError
from pathlib import Path
from subprocess import CalledProcessError, SubprocessError  # noqa

from django.contrib.gis.geos import GEOSGeometry

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


def run_import(filename, sheet, dry_run=False, db_path=None, **kwargs):
    """run import in a sub-process."""
    cmd_args = [str(filename), str(sheet)]
    for k, v in kwargs.items():
        cmd_args.append(f"--{k}")
        cmd_args.append(str(v))
    if dry_run:
        cmd_args.append("--dryrun")
    return run("etk", "import", db_path=db_path, *cmd_args)


def create_from_template(filename):
    """create from template."""
    shutil.copyfile(get_template_db(), filename)


def run(*args, db_path=None):
    env = (
        os.environ if db_path is None else {**os.environ, "ETK_DATABASE_PATH": db_path}
    )
    print(args)
    try:
        proc = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, env=env
        )
    except subprocess.CalledProcessError as e:
        error = e.stderr.decode("utf-8")
        log.debug(f"command {'_'.join(args)} failed with error {error}")
    if error is not None:
        # breakpoint()
        pass
    log.debug(f"command {'_'.join(args)} finished with status code {proc.returncode}")
    return proc.stdout, proc.stderr


def cache_queryset(queryset, fields):
    """Return dict of model instances with fields as key
    If several fields are specified, a tuple of the fields is used as key
    """

    def fields2key(inst, fields):
        if hasattr(fields, "__iter__") and not isinstance(fields, str):
            return tuple([getattr(inst, field) for field in fields])
        else:
            return getattr(inst, fields)

    return dict(((fields2key(instance, fields), instance) for instance in queryset))


def cache_codeset(code_set):
    if code_set is None:
        return {}
    return cache_queryset(code_set.codes.all(), "code")


def get_nodes_from_wkt(wkt):
    """Extract list of nodes (x, y) from WKT.

    geom_type: 'POINT', 'LINESTRING' or 'POLYGON'

    """
    geom = GEOSGeometry(wkt)
    if geom.geom_type == "Point":
        return (geom.coords,)
    if geom.geom_type == "LineString":
        return geom.coords
    if geom.geom_type == "Polygon":
        return geom.coords[0]

    raise NotImplementedError(
        f'Geometry type specified in WKT not implemented: "{wkt}"'
    )
