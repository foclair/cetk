import os

import numpy as np
import pytest
import rasterio as rio
from django.contrib.gis.geos import Polygon

from cetk.edb.models import (
    ActivityCode,
    GridSource,
    Substance,
    get_gridsource_raster,
    list_gridsource_rasters,
    write_gridsource_raster,
)
from cetk.edb.units import activity_rate_unit_to_si, emission_unit_to_si
from cetk.emissions.calc import aggregate_emissions  # noqa
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
    outfile = str(os.path.join(tmpdir, "gridsource_raster.tiff"))
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
    testsettings, pointsources, areasources, gridsources, roadsources, db_raster
):
    """test aggregation of emissions"""

    assert "raster1" in list_gridsource_rasters()
    df = aggregate_emissions(sourcetypes=["point", "area", "grid"], unit="ton/year")
    assert df.loc["total", ("emission", "NOx")] == pytest.approx(2530.0)

    poly = Polygon.from_bbox((0, 0, 500, 500))
    poly.srid = 3006

    # test with polygon only covering half the grid source raster
    df = aggregate_emissions(
        sourcetypes=["point", "area", "grid"], unit="ton/year", polygon=poly
    )
    assert df.loc["total", ("emission", "NOx")] < 2530.0

    df = aggregate_emissions(sourcetypes=["road"], unit="ton/year")
    assert df.loc["total", ("emission", "NOx")] > 0


def test_aggregate_emissions_all_sourcetypes(
    roadsources, pointsources, areasources, activities, code_sets, db_raster
):
    NOx = Substance.objects.get(slug="NOx")
    SOx = Substance.objects.get(slug="SOx")

    src1 = GridSource.objects.create(
        name="gridsource1",
        activitycode1=ActivityCode.objects.get(code="3"),
    )
    src1.substances.create(
        substance=NOx, value=emission_unit_to_si(1000, "ton/year"), raster=db_raster
    )
    src1.substances.create(
        substance=SOx, value=emission_unit_to_si(1.0, "kg/s"), raster=db_raster
    )
    src2 = GridSource.objects.create(
        name="gridsource2",
        activitycode1=ActivityCode.objects.get(code="3"),
    )
    src2.activities.create(
        activity=activities[0],
        rate=activity_rate_unit_to_si(1000, "m3/year"),
        raster=db_raster,
    )

    df = aggregate_emissions()
    # TODO should do better test than just > 0. Same value as gadget?
    # in gadget; df.max().max() = 31557610.0, men kan vara annan raster?
    #     quantity                           emission [ton/year]
    # substance                                          NOx           SOx
    # activitycode activity
    # 1            Energy                       3.155761e+07   2001.000000
    # 1.1          Stationary combustion                 NaN   1000.000000
    # 1.2          Fugitive emissions           1.000000e+03   3000.000000
    # 1.3.1        Light vehicles               1.220184e+00      1.220184
    # 1.3.2        Heavy vehicles               1.785290e+00      1.785290
    # 2.2          Other                        1.000000e+01      1.000000
    # 3            Diffuse sources              1.010000e+03  31558.600705
    assert df.max().max() > 0
    # gdal_raster.extent (367000.0, 6368000.0, 369000.0, 6370000.0)

    raster_data, metadata = get_gridsource_raster(db_raster)
    x1, y1, x2, y2 = metadata["extent"][0]
    left_half_extent = Polygon(
        (
            (x1, y1),
            (x1 + 0.5 * (x2 - x1), y1),
            (x1 + 0.5 * (x2 - x1), y2),
            (x1, y2),
            (x1, y1),
        ),
        srid=3006,
    )
    clipped_raster_data, metadata = get_gridsource_raster(db_raster, left_half_extent)

    # fraction of raster sum inside polygon
    raster_share = clipped_raster_data.sum() / raster_data.sum()

    codeset = code_sets[0]
    df = aggregate_emissions(
        name="gridsource1",
        substances=[SOx],
        codeset=codeset,
        polygon=left_half_extent,
        sourcetypes=["grid"],
    )
    assert len(df) == 1
    assert df.index[0] == ("3", "Diffuse sources")
    assert df.columns[0] == ("emission", "SOx")
    # reference emission: "seconds of year" * "grid fraction in polygon"
    ref_emis = 1.0 * 365.25 * 24 * 3600 * raster_share
    assert ref_emis == pytest.approx(df.iloc[0, 0], 1e-5)
