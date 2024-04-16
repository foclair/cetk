import numpy as np
import pytest
import rasterio as rio
from django.contrib.gis.geos import Polygon

from etk.edb.models import list_gridsource_rasters, write_gridsource_raster
from etk.emissions.calc import aggregate_emissions  # noqa
from etk.utils import GTiffProfile

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


def test_aggregate_emissions(
    testsettings, pointsources, areasources, gridsources, db_raster
):
    """test aggregation of emissions"""

    assert "raster1" in list_gridsource_rasters()
    df = aggregate_emissions(unit="ton/year")
    assert df.loc["total", ("emission", "NOx")] == 2530.0

    poly = Polygon.from_bbox((0, 0, 500, 500))
    poly.srid = 3006

    # test with polygon only covering half the grid source raster
    df = aggregate_emissions(unit="ton/year", polygon=poly)
    assert df.loc["total", ("emission", "NOx")] < 2530.0
