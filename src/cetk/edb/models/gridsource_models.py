"""Gridsource models"""

import numpy as np
import rasterio as rio
import shapely
from django import db
from django.contrib.gis.db import models
from rasterio.mask import mask

from cetk.edb.const import CHAR_FIELD_LENGTH, NODATA
from cetk.utils import path_from_connection, slugify_keep_case

from .source_models import PointAreaGridSourceBase, SourceActivity, SourceSubstance

GRIDSOURCE_RASTER_PREFIX = "raster_"


class OutsideExtentError(Exception):
    pass


class GridSource(PointAreaGridSourceBase):

    sourcetype = "grid"

    class Meta(PointAreaGridSourceBase.Meta):
        constraints = [
            models.UniqueConstraint(fields=("name",), name="gridsource_unique_name"),
        ]
        default_related_name = "gridsources"


class GridSourceActivity(SourceActivity):
    """An emitting activity for a grid-source."""

    source = models.ForeignKey("GridSource", on_delete=models.CASCADE)
    raster = models.CharField(
        verbose_name="distribution raster", max_length=CHAR_FIELD_LENGTH
    )


class GridSourceSubstance(SourceSubstance):
    """A substance emission of a grid-source ."""

    source = models.ForeignKey("GridSource", on_delete=models.CASCADE)
    raster = models.CharField(
        verbose_name="distribution raster", max_length=CHAR_FIELD_LENGTH
    )


def raster_table(name: str):
    """get name of table where raster is stored."""
    return f"{GRIDSOURCE_RASTER_PREFIX}{slugify_keep_case(name)}"


def list_gridsource_rasters():
    """return names of gridsource rasters in database."""
    cur = db.connection.cursor()
    names = [
        rec[0]
        for rec in cur.execute(
            """
            select table_name from gpkg_contents where
            data_type = '2d-gridded-coverage'
            """
        ).fetchall()
    ]
    return [
        name[len(GRIDSOURCE_RASTER_PREFIX) :]
        for name in names
        if name.startswith(GRIDSOURCE_RASTER_PREFIX)
    ]


def get_gridsource_raster(name, clip_by=None):
    """Return (data, tranform, metadata) of raster
    option:
        clip_by: clip raster by polygon
    """
    with rio.open(path_from_connection(), table=raster_table(name)) as dset:
        _, srid = dset.profile["crs"].to_authority()
        nodata = dset.profile.get("nodata_value", NODATA)
        metadata = {"srid": srid, "nodata": nodata}
        if clip_by is not None:
            geoms = [shapely.from_wkt(clip_by.transform(srid, clone=True).wkt)]
            try:
                data, transform = mask(
                    dset, geoms, all_touched=True, crop=True, indexes=1
                )
            except ValueError:
                raise OutsideExtentError("polygon is completely outside extent")
            metadata["transform"] = transform
            rows, cols = data.shape
            x_bl, y_bl = transform * (0, rows)
            x_tr, y_tr = transform * (cols, 0)
            metadata["extent"] = (x_bl, y_bl, x_tr, y_tr)
        else:
            metadata["extent"] = (
                (
                    dset.bounds.left,
                    dset.bounds.bottom,
                    dset.bounds.right,
                    dset.bounds.top,
                ),
            )
            metadata["transform"] = dset.transform
            data = dset.read()
    return data, metadata


def write_gridsource_raster(raster, name):
    """write a rasterio taset to db in geopackage format."""
    try:
        _ = int(raster.crs.to_authority()[1])
    except ValueError:
        raise ValueError(
            f"Raster '{name}' has an invalid projection, could not retrieve epsg code"
        )
    if name in list_gridsource_rasters():
        drop_gridsource_raster(name)

    with rio.Env():
        gpkg = rio.open(
            path_from_connection(),
            "w",
            driver="GPKG",
            height=raster.height,
            width=raster.width,
            count=raster.count,
            dtype="float32",
            RASTER_TABLE=raster_table(name),
            transform=raster.transform,
            nodata=NODATA,
            crs=raster.crs,
            APPEND_SUBDATASET="YES",
        )
        data = raster.read()
        total = data[data != raster.nodata].sum()
        if total != 0:
            data = np.where(data != raster.nodata, data / total, -9999.0)
        gpkg.write(np.float32(data))
        gpkg.close()
    # reload_database()


def drop_gridsource_raster(name):
    """drop grid source raster and related entries in gpkg-tables."""
    table_name = f"{GRIDSOURCE_RASTER_PREFIX}{slugify_keep_case(name)}"
    cur = db.connection.cursor()

    sql_operations = [
        f"delete from gpkg_2d_gridded_tile_ancillary where tpudt_name='{table_name}'",
        f"delete from gpkg_2d_gridded_coverage_ancillary where tile_matrix_set_name='{table_name}'",  # noqa
        f"delete from gpkg_extensions where table_name='{table_name}'",
        f"delete from gpkg_tile_matrix_set where table_name='{table_name}'",
        f"delete from gpkg_tile_matrix where table_name='{table_name}'",
        f"delete from gpkg_metadata_reference where table_name='{table_name}'",
        f"delete from gpkg_contents where table_name='{table_name}'",
        f"drop table {table_name}",
    ]
    for sql in sql_operations:
        cur.execute(sql)
    # reload_database()
