"""Tests for emission model importers."""

from subprocess import CalledProcessError

import netCDF4 as nc
import numpy as np
import pandas as pd
from pytest import approx

from etk.tools.utils import run_aggregate_emissions, run_rasterize_emissions


def test_aggregate(inventory, tmpdir):
    result1_csv = tmpdir / "table1.csv"
    try:
        run_aggregate_emissions(
            result1_csv,
            db_path=inventory,
            unit="ton/year",
            sourcetypes=["point", "area"],
            substances=["NOx", "PM25"],
            codeset="GNFR",
        )
    except CalledProcessError as err:
        print(err.stderr)
        assert False, "error running aggregation"
    df = pd.read_csv(result1_csv, index_col=[0, 1], header=[0, 1], delimiter=";")

    assert np.all(df.columns.levels[0] == ["emission"])
    assert np.all(df.columns.levels[1] == ["NOx", "PM25"])
    assert df.index.names == ["activitycode", "activity"]
    assert df.loc["A", ("emission", "NOx")].item() == 2.018
    assert df.loc["B", ("emission", "PM25")].item() == 1.0

    result2_csv = tmpdir / "table2.csv"
    try:
        run_aggregate_emissions(result2_csv, db_path=inventory)
    except CalledProcessError as err:
        print(err.stderr)
        assert False, "error running aggregation"
    df = pd.read_csv(result2_csv, index_col=0, header=[0, 1], delimiter=";")
    assert np.all(df.columns.levels[0] == ["emission"])
    assert np.all(df.columns.levels[1] == ["CO", "NMVOC", "NOx", "PM10", "PM25", "SOx"])
    assert df.index.names == ["activity"]
    assert df.loc["total", ("emission", "NOx")].item() == approx(2.840229e9)
    assert df.loc["total", ("emission", "PM25")].item() == approx(1.583291e9)


def test_rasterize(inventory, tmpdir):
    output_dir = tmpdir / "grid"
    run_rasterize_emissions(
        output_dir, 5000.0, db_path=inventory, srid=3006, substances=["NOx", "SOx"]
    )
    assert (output_dir / "NOx.nc").exists()
    assert (output_dir / "SOx.nc").exists()
    with nc.Dataset(output_dir / "NOx.nc", "r") as dset:
        assert dset["emission_NOx"][:].sum() > 0
