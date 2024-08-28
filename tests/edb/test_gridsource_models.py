"""Unit and regression tests for gridsource models."""


import numpy as np
import pytest
import rasterio as rio
from django.contrib.gis.geos import Polygon

from cetk.edb.models import (
    GridSource,
    Substance,
    drop_gridsource_raster,
    get_gridsource_raster,
    list_gridsource_rasters,
    write_gridsource_raster,
)
from cetk.edb.units import emission_unit_to_si
from cetk.utils import GTiffProfile

RASTER_EXTENT = (0, 0, 1200, 1000)


@pytest.fixture
def rasterfile(tmpdir):
    nrows = 10
    ncols = 12
    x1, y1, x2, y2 = RASTER_EXTENT
    transform = rio.transform.from_bounds(x1, y1, x2, y2, width=ncols, height=nrows)
    data = np.linspace(0, 100, num=nrows * ncols, dtype=np.float32).reshape(
        (nrows, ncols)
    )
    outfile = str(tmpdir / "gridsource_raster.tiff")
    with rio.open(
        outfile,
        "w",
        **GTiffProfile(),
        width=data.shape[1],
        height=data.shape[0],
        transform=transform,
        crs=3006
    ) as dset:
        dset.write(data, 1)
    return outfile


@pytest.fixture
def db_raster(rasterfile, transactional_db):
    name = "raster1"
    with rio.open(rasterfile, "r") as raster:
        write_gridsource_raster(raster, "raster1")
    return name


@pytest.mark.django_db(transaction=False)
def test_write_and_delete_gridsource_raster(transactional_db, rasterfile):
    """test to write gridsource raster to database."""
    assert Substance.objects.filter(
        slug="NOx"
    ).exists(), "problem with transactions duering testing"
    with rio.open(rasterfile, "r") as raster:
        write_gridsource_raster(raster, "test")
    assert "test" in list_gridsource_rasters(), "no gridsource raster created in db"
    drop_gridsource_raster("test")
    assert (
        "test" not in list_gridsource_rasters()
    ), "gridsource raster not removed from db"
    # test to write same raster again (checking that everything has been removed)
    with rio.open(rasterfile, "r") as raster:
        write_gridsource_raster(raster, "test")
    assert (
        "test" in list_gridsource_rasters()
    ), "could not re-write gridsource raster to db"
    # clean-up
    drop_gridsource_raster("test")
    assert Substance.objects.filter(
        slug="NOx"
    ).exists(), "problem with transactions duering testing"


def test_list_rasters(db_raster):
    rasters = list_gridsource_rasters()
    assert db_raster in rasters, "raster not found in db"


def test_create_gridsource(rasterfile, code_sets, transactional_db):
    raster_name = "raster1"
    with rio.open(rasterfile, "r") as raster:
        write_gridsource_raster(raster, raster_name)

    NOx = Substance.objects.get(slug="NOx")
    code_set1, code_set2 = code_sets
    ac1 = dict([(ac.code, ac) for ac in code_set1.codes.all()])
    ac2 = dict([(ac.code, ac) for ac in code_set2.codes.all()])

    src = GridSource.objects.create(
        name="gridsource1", activitycode1=ac1["1"], activitycode2=ac2["A"]
    )
    src.substances.create(
        raster=raster_name, substance=NOx, value=emission_unit_to_si(2000, "ton/year")
    )


def test_get_raster(rasterfile, transactional_db):
    raster_name = "raster1"

    with rio.open(rasterfile, "r") as raster:
        write_gridsource_raster(raster, raster_name)
    data, metadata = get_gridsource_raster(raster_name)
    with rio.open(rasterfile, "r") as dset:
        ref_data = dset.read()
        total = ref_data[ref_data != dset.nodata].sum()
        if total != 0:
            ref_data = np.where(ref_data != dset.nodata, ref_data / total, -9999.0)
        ref_transform = dset.transform
    assert np.all(ref_data == data), "db raster differs from the original"
    assert (
        ref_transform == metadata["transform"]
    ), "raster transform differs from the original"


def test_clip_raster(transactional_db, db_raster):

    poly = Polygon.from_bbox(RASTER_EXTENT)
    poly.srid = 3006
    full_data, full_metadata = get_gridsource_raster(db_raster)
    full_clipped_data, full_clipped_metadata = get_gridsource_raster(
        db_raster, clip_by=poly
    )

    assert np.all(full_data == full_clipped_data), "clip alters data without reason"
    assert (
        full_metadata["transform"] == full_clipped_metadata["transform"]
    ), "clip alters raster transform without reason"

    x1, y1, x2, y2 = RASTER_EXTENT
    poly = Polygon.from_bbox((x1, y1, x2 / 2, y2 / 2))
    poly.srid = 3006
    half_data, _ = get_gridsource_raster(db_raster, clip_by=poly)

    assert half_data.shape[1] < full_data.shape[1], "clipping raster did not work"
    assert (
        half_data.sum() < full_data.sum()
    ), "sum of data should be reduced when clipping"
