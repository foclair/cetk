"""Utility functions."""

import itertools
import re
import unicodedata

import rasterio as rio
from django import db
from django.core.cache import cache

from cetk.edb.const import NODATA

DEFAULT_DB_ALIAS = "TEST"


def reload_database() -> None:
    """
    Reload the database
    """
    db.connection.close()
    db.connection.connect()
    cache.clear()


def path_from_connection():
    """get path to db file from database cursor."""
    return db.connection.settings_dict["NAME"]


def slugify_keep_case(value):
    """slugify without changing case."""
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value).strip()
    return re.sub(r"[-\s]+", "-", value)


class GTiffProfile(rio.profiles.Profile):
    """Tiled, band-interleaved, LZW-compressed, 8-bit GTiff."""

    defaults = {
        "count": 1,
        "driver": "GTiff",
        "interleave": "band",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "lzw",
        "nodata": NODATA,
        "dtype": "float32",
    }


def inbatch(iterable, size):
    """Return suitable sized batches (as lists) of an iterable."""
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, size))
        if not batch:
            return
        yield batch
