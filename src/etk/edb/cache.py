"""Module to manage caching of emission data."""

import pickle
from collections import namedtuple
from pathlib import Path
from tempfile import TemporaryDirectory

# nr of records per page
PAGE_SIZE = 10000


# source specific parameters to be added to dataset
# parameters must be included in emission query
STATIC_DATA_PARAMETERS = {
    "road": [
        "length",
        "aadt",
        "nolanes",
        "speed",
        "width",
        "slope",
        "heavy_vehicle_share",
    ],
    "point": [
        "chimney_height",
        "chimney_outer_diameter",
        "chimney_inner_diameter",
        "chimney_gas_speed",
        "chimney_gas_temperature",
        "house_height",
        "house_width",
    ],
}


class NotInCacheError(Exception):
    """Page not found in cache"""


class EmissionCache:

    """An emission out-of-memory cache."""

    def __init__(self, querysets):
        """create an EmissionCache

        args
            querysets: dict with a sourcetype as key and a cursor queryset as value

        """

        self.cache_dir = None

        # page count per sourcetype
        self._pages = {}

        # temporary in-memory storage
        # write to "page" on disk when recs_in_memory > PAGE_SIZE
        self._features = {}
        self._weights = {}
        self._emissions = {}
        # counter for features
        self._feature_index = {"point": 0, "road": 0}
        self._rasterized_sources = set()

        # nr of emission records not yet written to disk
        self._recs_in_memory = {"road": 0, "point": 0, "area": 0, "grid": 0}

        # map feature id to index in narc variable
        self.feature_ids = {"road": {}, "point": {}}

        # keep track of all sources that have already been gridded
        self.gridded_sources = {
            "road": set(),
            "point": set(),
            "area": set(),
            "grid": set(),
        }

        # create mapping between column name and index using a named tuple
        self.col_maps = {}
        for sourcetype, qs in querysets.items():
            if qs is not None:
                desc = qs.cursor.description
                column_index_tuple = namedtuple("ColumnIndex", [col[0] for col in desc])
                self.col_maps[sourcetype] = column_index_tuple(*range(len(desc)))

    def __enter__(self):
        # create temporary directory for cache
        self.cache_dir = TemporaryDirectory(prefix="cache_")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cache_dir is not None:
            self.cache_dir.cleanup()
        self.cache_dir = None

    def has_sourcetype(self, sourcetype):
        return sourcetype in self._pages

    def has_substance(self, sourcetype, substance_id):
        return self.emis_page_count(sourcetype, substance_id) > 0

    def emis_page_count(self, sourcetype, substance_id):
        return self._pages.get(sourcetype, {}).get(f"emission_{substance_id}", 0)

    def weight_page_count(self, sourcetype):
        return self._pages.get(sourcetype, {}).get("weights", 0)

    def feature_page_count(self, sourcetype):
        return self._pages.get(sourcetype, {}).get("features", 0)

    def add_rec(
        self, rec, sourcetype, *, write_feature=False, write_weights=False, weights=None
    ):
        """add feature to cache."""

        col_map = self.col_maps[sourcetype]
        # extract data from record
        source_id = rec[col_map.source_id]
        substance_id = rec[col_map.substance_id]

        # only write to disk if source not already in self.feature_ids
        # or in self.gridded_sources
        # (to keep all data related to a specific source on the same cache page)
        if (
            self._recs_in_memory[sourcetype] > PAGE_SIZE
            and source_id not in self.feature_ids[sourcetype]
            and source_id not in self.gridded_sources[sourcetype]
        ):
            if write_weights:
                self.write_weights(sourcetype)
            if write_feature:
                self.write_features(sourcetype)
            self.write_emissions(sourcetype)

            # reset nr of records in memory
            self._recs_in_memory[sourcetype] = 1

        # emissions currently in memory
        emissions = self._emissions.setdefault(sourcetype, {})

        # add record
        # avoid writing emission rec if source is gridded but there are no resulting
        # weights. This may happen if emission filter polygon is bigger than dataset
        # extent. The source is then included, but no weights are generated.
        # It could potentially also happen due to uncertainties in coordinate
        # transformation in PostGIS
        if not (write_weights and weights is None):
            emissions.setdefault(substance_id, []).append(rec)

        self._recs_in_memory[sourcetype] += 1

        if write_feature and source_id not in self.feature_ids[sourcetype]:
            geom_wkt = rec[col_map.wkt]
            params = STATIC_DATA_PARAMETERS[sourcetype]
            data = {key: rec[getattr(col_map, key)] for key in params}
            self.feature_ids[sourcetype][source_id] = self._feature_index[sourcetype]
            # features currently in memory
            features = self._features.setdefault(
                sourcetype, {"ids": [], "geoms": [], "data": []}
            )
            features["ids"].append(source_id)
            features["geoms"].append(geom_wkt)
            features["data"].append(data)
            self._feature_index[sourcetype] += 1

        if sourcetype != "grid":
            source_key = source_id
        else:
            raster = rec[col_map.raster]
            source_key = (source_id, raster)

        if weights is not None and source_key not in self.gridded_sources[sourcetype]:
            self._weights.setdefault(sourcetype, {})[source_key] = weights
            self.gridded_sources[sourcetype].add(source_key)

    def write_features(self, sourcetype):
        if sourcetype in self._features:
            self._write_page_to_cache(
                sourcetype, "features", self._features[sourcetype]
            )
            self._features[sourcetype] = {"ids": [], "geoms": [], "data": []}

    def read_features(self, sourcetype, page_nr):
        return self._read_page_from_cache(sourcetype, "features", page_nr)

    def write_weights(self, sourcetype):
        if sourcetype in self._weights:
            self._write_page_to_cache(sourcetype, "weights", self._weights[sourcetype])
            self._weights[sourcetype] = {}

    def read_weights(self, sourcetype, page_nr):
        return self._read_page_from_cache(sourcetype, "weights", page_nr)

    def write_emissions(self, sourcetype):
        if sourcetype in self._emissions:
            for substance_id, data in self._emissions[sourcetype].items():
                self._write_page_to_cache(sourcetype, f"emission_{substance_id}", data)
            self._emissions[sourcetype] = {}

    def read_emissions(self, sourcetype, substance_id, page_nr):
        return self._read_page_from_cache(
            sourcetype, f"emission_{substance_id}", page_nr
        )

    def _write_page_to_cache(self, sourcetype, namespace, data):
        """Write temporary data to disk"""

        # if data is empty, do not write any page
        if len(data) == 0:
            return

        # set page count for sourcetype in namespace
        pages = self._pages.setdefault(sourcetype, {})
        if namespace not in pages:
            pages[namespace] = 1
        else:
            pages[namespace] += 1

        page_nr = pages[namespace]
        cache_subdir = Path(self.cache_dir.name) / sourcetype / namespace
        cache_subdir.mkdir(parents=True, exist_ok=True)
        with cache_subdir.joinpath(f"page_{page_nr}.tmp").open("wb") as page_file:
            pickle.dump(data, page_file, protocol=-1)

    def _read_page_from_cache(self, sourcetype, namespace, page_nr):
        """Read page of data from disk."""

        cache_subdir = Path(self.cache_dir.name) / sourcetype / namespace
        page_file_name = cache_subdir / f"page_{page_nr}.tmp"
        if not page_file_name.exists():
            raise NotInCacheError(f"file {page_file_name} not found in cache")
        with page_file_name.open("rb") as page_file:
            return pickle.load(page_file)


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
