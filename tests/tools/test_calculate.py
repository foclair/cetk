"""Tests for emission model importers."""

import datetime

import netCDF4 as nc
import numpy as np
import pandas as pd
import pytest

from cetk.tools.utils import (
    run_aggregate_emissions,
    run_rasterize_emissions,
    run_update_settings,
)


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_aggregate(inventory, tmpdir):
    run_update_settings(db_path=inventory, codeset1="GNFR")

    result1_csv = tmpdir / "table1.xlsx"
    proc = run_aggregate_emissions(
        result1_csv,
        db_path=inventory,
        unit="ton/year",
        sourcetypes=["point", "area"],
        substances=["NOx", "PM25"],
        codeset="GNFR",
    )
    assert proc.wait() == 0, proc.stderr

    df = pd.read_excel(result1_csv, index_col=[0, 1], header=[0, 1])

    assert np.all(df.columns.levels[0] == ["emission"])
    assert np.all(df.columns.levels[1] == ["NOx", "PM25"])
    assert df.index.names == ["activitycode", "activity"]
    assert df.loc["A", ("emission", "NOx")].item() == pytest.approx(2.018)
    assert df.loc["B", ("emission", "PM25")].item() == pytest.approx(1.0)

    result2_csv = tmpdir / "table2.xlsx"
    proc = run_aggregate_emissions(result2_csv, db_path=inventory)
    assert proc.wait() == 0, proc.stderr

    df = pd.read_excel(result2_csv, index_col=0, header=[0, 1])
    assert np.all(df.columns.levels[0] == ["emission"])
    assert np.all(df.columns.levels[1] == ["CO", "NMVOC", "NOx", "PM10", "PM25", "SOx"])
    assert df.index.names == ["activity"]
    assert df.loc["total", ("emission", "NOx")].item() == pytest.approx(
        45108 / (365.25 * 24 * 3600)
    )
    assert df.loc["total", ("emission", "PM25")].item() == pytest.approx(
        5.411264e6 / (365.25 * 24 * 3600)
    )


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_rasterize(inventory, tmpdir):
    output_dir = tmpdir / "grid"
    proc = run_rasterize_emissions(
        output_dir, 5000.0, db_path=inventory, srid=3006, substances=["NOx", "SOx"]
    )
    assert proc.wait() == 0, proc.stderr

    assert (output_dir / "NOx.nc").exists()
    assert (output_dir / "SOx.nc").exists()
    with nc.Dataset(output_dir / "NOx.nc", "r") as dset:
        assert dset["emission_NOx"][:].sum() > 0


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_rasterize_timeseries(inventory, tmpdir):
    output_dir = tmpdir / "grid"
    begin = datetime.datetime(2012, 1, 1, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2012, 1, 1, 2, tzinfo=datetime.timezone.utc)
    proc = run_rasterize_emissions(
        output_dir,
        5000.0,
        db_path=inventory,
        srid=3006,
        substances=["NOx", "SOx"],
        begin=begin,
        end=end,
    )
    assert proc.wait() == 0, proc.stderr

    assert (output_dir / "NOx.nc").exists()
    assert (output_dir / "SOx.nc").exists()
    with nc.Dataset(output_dir / "NOx.nc", "r") as dset:
        assert dset["emission_NOx"][:].sum() > 0
