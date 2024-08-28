"""Rasterization of emission sources."""

import datetime
import logging
import os
from copy import copy
from functools import cache
from itertools import product
from math import ceil
from pathlib import Path
from typing import Optional

import netCDF4 as nc
import numpy as np
import pandas as pd
import rasterio as rio
from django.contrib.gis.geos import GEOSGeometry, Polygon
from rastafari import ddaf_line_subpixel, even_odd_polygon_fill, resample_band

from cetk import __version__
from cetk.edb.cache import EmissionCache, NotInCacheError
from cetk.edb.models import (
    VELOCITY_CHOICES,
    AreaSource,
    ColdstartTimevar,
    CongestionProfile,
    FlowTimevar,
    GridSource,
    Parameter,
    PointSource,
    RoadSource,
    Settings,
    Timevar,
    get_gridsource_raster,
    timevar_to_series,
)
from cetk.edb.models.gridsource_models import OutsideExtentError
from cetk.edb.traffic import los_to_velocity
from cetk.edb.units import emis_conversion_factor_from_si
from cetk.emissions.calc import calculate_source_emissions

# short  source type identifiers for conveniency
POINT = PointSource.sourcetype
AREA = AreaSource.sourcetype
GRID = GridSource.sourcetype
ROAD = RoadSource.sourcetype

# supported source types
SOURCETYPES = (POINT, AREA, GRID, ROAD)

# slug for traffic work parameter and traffic condition parameter
TRAFFIC_WORK_PARAMETER_SLUG = "traffic_work"
TRAFFIC_CONDITION_PARAMETER_SLUG = "traffic_condition"
TRAFFIC_WORK_SUBSTANCE_SLUG = "traffic_work"
VEHICLE_SPEED_PARAMETER_SLUG = "vehicle_speed"


class Output:
    def __init__(
        self, extent: tuple, path: Path, srid: int, timezone: datetime.timezone
    ):
        self.extent = extent
        self.path = path
        self.srid = srid
        self.timezone = timezone


@cache
def time_step_as_delta(time_step):
    """Return timedelta corresponding to a time_step.
    For Y and M, returns an approximate time-delta.
    """

    if time_step.endswith("Y"):
        nyears = int(time_step[:-1])
        return pd.Timedelta(days=nyears * 365)

    if time_step.endswith("M"):
        nmonths = int(time_step[:-1])
        return pd.Timedelta(days=nmonths * 30)

    ts = time_step.lower() if time_step.endswith("h") else time_step
    try:
        return pd.Timedelta(ts)
    except ValueError:
        raise ValueError(f"invalid time step abbreviation {ts}")


class EmissionRasterizer:
    """An emission time-series rasterizer.

    writes emissions to outputfile in units kg/s

    """

    def __init__(self, output, nx, ny):
        """
        args
            output: output.path: path to store NetCDF files
                    output.extent: extent of the raster (x1, y1, x2, y2)
                    output.srid: SRID of output, as int of 4 numbers (ex. 3006)
                    output.timezone: timezone of output
            nx: raster dimension in x-direction
            ny: raster dimension in y-direction
        """
        self.timevars = {}
        self.flow_timevars = {}
        self.coldstart_timevars = {}
        self.congestion_profiles = {}
        self.level_weights = {}
        self.output = output
        self.extent = output.extent
        self.crs = rio.crs.CRS.from_epsg(output.srid)
        self._cache = None
        self.nx = nx
        self.ny = ny
        self.sourcetypes = []

        # querysets for emission
        self.querysets = {}

        self.log = logging.getLogger(__name__)

    def reset(self):
        """Reset attributes.
        To allow reuse of rasterizer (e.g. for a new substance)
        """

        self.querysets = {}
        self.sourcetypes = []

    @property
    def x1(self):
        return self.extent[0]

    @property
    def x2(self):
        return self.extent[2]

    @property
    def y1(self):
        return self.extent[1]

    @property
    def y2(self):
        return self.extent[3]

    @property
    def dx(self):
        return (self.x2 - self.x1) / self.nx

    @property
    def dy(self):
        return (self.y2 - self.y1) / self.ny

    @property
    def srid(self):
        return self.output.srid

    def _get_timevars(self, sourcetypes):
        """Get all time-variations."""
        self.timevars = {}
        self.flow_timevars = {}
        self.coldstart_timevars = {}
        self.congestion_profiles = {}

        if POINT in sourcetypes or AREA in sourcetypes:
            for tvar in Timevar.objects.all():
                self.timevars[tvar.id] = tvar
            default = Timevar()
            self.timevars["default"] = default

        if ROAD in sourcetypes:
            for tvar in FlowTimevar.objects.all():
                self.flow_timevars[tvar.id] = tvar
            default = FlowTimevar()
            self.flow_timevars["default"] = default

            for tvar in ColdstartTimevar.objects.all():
                self.coldstart_timevars[tvar.id] = tvar
            default = ColdstartTimevar()
            self.coldstart_timevars["default"] = default

            for prof in CongestionProfile.objects.all():
                self.congestion_profiles[prof.id] = prof
            default = CongestionProfile()
            self.congestion_profiles["default"] = default

    def _get_level_weights(self):
        """redistribute vertical distr. into levels of result dataset."""
        # TODO don't use levels yet
        if Settings.get_current().codeset1 is None:
            self.log.warning(
                "inventory has no primary code-set - "
                "cannot apply vertical distributions "
            )
            return

        bounds = self.levels[:]

        weights = np.zeros(self.levels.shape, dtype=float)
        # cache vertical distributions to used for different activitycodes
        # heights are determined using the 1st (primary) codeset
        for ac in (
            Settings.get_current()
            .codeset1.codes.prefetch_related("vertical_dist")
            .exclude(vertical_dist__isnull=True)
        ):
            # eval is needed in cetk because arrays stored as CharField in sqlite
            vdist = np.array(eval(ac.vertical_dist.weights))
            vdist_weights = vdist[:, 1]
            vdist_heights = vdist[:, 0]

            if vdist_heights[0] > 0:
                vdist_weights = np.insert(vdist_weights, 0, 0)
                vdist_heights = np.insert(vdist_heights, 0, 0)

            # interp weights at level bounds
            interp_weights = np.interp(bounds, vdist_heights, vdist_weights, right=0)
            # insert interpolated values into vdist
            start_ind = 0
            level = 0
            for bound, val in zip(bounds, interp_weights):
                # index where bound will be inserted
                ind = np.searchsorted(vdist_heights, bound)
                if bound not in vdist_heights:
                    vdist_weights = np.insert(vdist_weights, ind, val)
                    vdist_heights = np.insert(vdist_heights, ind, bound)
                # integrate weight between level bounds
                weight = np.trapz(
                    vdist_weights[start_ind : ind + 1],
                    vdist_heights[start_ind : ind + 1],
                )
                start_ind = ind
                weights[level] = weight
                level += 1
            weights_sum = weights.sum()
            if weights_sum != 0:
                weights /= weights_sum
            vertical_index = weights.nonzero()
            non_zero_weights = weights[vertical_index]
            self.level_weights[ac.code] = (vertical_index[0], non_zero_weights[:])

    def _timevariations_to_dataframe(self, begin, end):
        """Prepare hourly dataframes in UTC for all time-variation profiles.

        args
            begin: start time in UTC
            end: end time in UTC

        """
        time_index = pd.date_range(begin, end, freq="h")
        one_hour = datetime.timedelta(hours=1)
        shifted_index = pd.date_range(begin - one_hour, end - one_hour, freq="h")

        self.flow_timevar_scalings = pd.DataFrame(
            {
                fvar.id
                or "default": timevar_to_series(
                    shifted_index, fvar, timezone=self.timezone
                ).to_numpy()  # discard the shifted index by converting to ndarray
                for fvar in self.flow_timevars.values()
            },
            index=time_index,
        )
        self.traffic_conditions = pd.DataFrame(
            {
                prof.id
                or "default": prof.to_series(
                    shifted_index, timezone=self.timezone
                ).to_numpy()
                for prof in self.congestion_profiles.values()
            },
            index=time_index,
        )

        # calculate vehicle velocity from level-of-service and posted speed
        self.velocity_light = {}
        self.velocity_heavy = {}
        for key, vel in product(self.traffic_conditions, VELOCITY_CHOICES):
            lvehspd, hvehspd = los_to_velocity(self.traffic_conditions[key], vel)
            # convert to SI units, km/h to m/s
            self.velocity_light[(key, vel)] = lvehspd / 3.6
            self.velocity_heavy[(key, vel)] = hvehspd / 3.6

        self.source_timevar_scalings = pd.DataFrame(
            {
                tvar.id
                or "default": timevar_to_series(
                    shifted_index, tvar, timezone=self.output.timezone
                ).to_numpy()
                for tvar in self.timevars.values()
            },
            index=time_index,
        )

    def _get_querysets(  # noqa: C901, PLR0912
        self,
        sourcetypes=None,
        name=None,
        tags=None,
        point_ids=None,
        area_ids=None,
        grid_ids=None,
        road_ids=None,
        polygon=None,
        substances=None,
        ac1=None,
        ac2=None,
        ac3=None,
        *,
        cur=None,
    ):
        """Get querysets for emissions."""

        sourcetypes = sourcetypes or SOURCETYPES
        # not used; srid = Settings.get_current().srid

        if ac1 is not None or ac2 is not None or ac3 is not None:
            raise ValueError(
                "filtering for ac not implemented in source_emissions_query yet!"
            )
        # if activity codes are given as strings, get the corresponding
        # activity code instances
        if ac1 is not None and len(ac1) > 0 and isinstance(ac1[0], str):
            # TODO why code__in= not code= ?
            ac1_instances = list(
                Settings.get_current().codeset1.codes.filter(code__in=ac1)
            )
            if len(ac1_instances) == 0:
                raise ValueError(
                    f"the filter for activitycode1: {ac1} does not match any code"
                    f" in code-set '{Settings.get_current().codeset1.name}'"
                )
        else:
            ac1_instances = ac1

        if ac2 is not None and len(ac2) > 0 and isinstance(ac2[0], str):
            ac2_instances = list(
                Settings.get_current().codeset2.codes.filter(code__in=ac2)
            )
            if len(ac2_instances) == 0:
                raise ValueError(
                    f"the filter for activitycode2: {ac2} does not match any code"
                    f" in code-set '{Settings.get_current().codeset2.name}'"
                )
        else:
            ac2_instances = ac2

        if ac3 is not None and len(ac3) > 0 and isinstance(ac3[0], str):
            ac3_instances = list(
                Settings.get_current().codeset3.codes.filter(code__in=ac3)
            )
            if len(ac3_instances) == 0:
                raise ValueError(
                    f"the filter for activitycode3: {ac3} does not match any code"
                    f" in code-set '{Settings.get_current().codeset3.name}'"
                )
        else:
            ac3_instances = ac3

        # aggregate emissions for each source-type per sourceid
        # TODO, ac1-3 and tolerance not used in calculate_source_emissions yet
        # tolerance = None
        for sourcetype in sourcetypes:
            self.log.debug(f"- {sourcetype}source emissions")
            if sourcetype == POINT:
                if not PointSource.objects.exists():
                    continue
                ids = point_ids
            elif sourcetype == AREA:
                if not AreaSource.objects.exists():
                    continue
                ids = area_ids
            elif sourcetype == ROAD:
                if not RoadSource.objects.exists():
                    continue
                ids = road_ids
            elif sourcetype == GRID:
                if not GridSource.objects.exists():
                    continue
                ids = grid_ids
            else:
                raise ValueError(
                    f"Rasterize cannot handle sourcetype {sourcetype} yet."
                )
            self.querysets[sourcetype] = calculate_source_emissions(
                sourcetype,
                substances=substances,
                srid=int(self.output.srid),
                name=name,
                ids=ids,
                tags=tags,
                polygon=polygon,
            )

    def _get_weights(self, polygon=None):
        """Get cell weights for all sourcetypes."""

        for sourcetype in self.querysets:
            if sourcetype == POINT:
                self._get_point_weights()
            elif sourcetype == AREA:
                self._get_area_weights()
            if sourcetype == ROAD:
                self._get_road_weights()
            elif sourcetype == GRID:
                self._get_grid_weights(polygon=polygon)

    def _get_point_weights(self):
        """Get cell weights for points.
        returns a dict with source_id as keys and
        (index_array, 1.0) as values

        complete records from query result are stored in dict
        with source_id as key.
        """
        col_map = self._cache.col_maps[POINT]
        for rec in self.querysets[POINT]:
            source_id = rec[col_map.source_id]

            if source_id not in self._cache.gridded_sources[POINT]:
                [[x, y]] = np.array(get_nodes_from_wkt(rec[col_map.wkt]))

                # check if source is within bounds
                if (x < self.x1 or y < self.y1) or (x > self.x2 or y > self.y2):
                    continue

                col = min(int((x - self.x1) / self.dx), self.nx - 1)
                row = min(self.ny - int(ceil((y - self.y1) / self.dy)), self.ny - 1)
                index = ((row,), (col,))

                # stores index array for consistency with other sourcetypes
                weights = (index, 1.0)
                self._cache.add_rec(rec, POINT, write_weights=True, weights=weights)
            else:
                self._cache.add_rec(rec, POINT, write_weights=False)

        # write last page to cache
        self._cache.write_weights(POINT)
        self._cache.write_emissions(POINT)

    def _get_area_weights(self):
        """Get cell weights for area sources.
        returns a dict with source_id as keys and
        (index_array, weight_array) as values

        complete records from query result are stored in a dict
        with source_id as key.
        """

        col_map = self._cache.col_maps[AREA]
        for rec in self.querysets[AREA]:
            source_id = rec[col_map.source_id]

            if source_id not in self._cache.gridded_sources[AREA]:
                source_weights = {}
                # extract nodes from area geometry in WKT format
                wkt = rec[col_map.wkt]
                nodes = np.array(get_nodes_from_wkt(wkt))

                is_within_extent = any(
                    self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2
                    for x, y in nodes
                )

                if is_within_extent:
                    even_odd_polygon_fill(
                        nodes,
                        source_weights,
                        self.extent,
                        self.nx,
                        self.ny,
                        subgridcells=2,
                    )

                if len(source_weights) > 0:
                    indices = list(zip(*source_weights.keys()))

                    index = (indices[0], indices[1])

                    weights = (
                        index,
                        np.fromiter(source_weights.values(), dtype=float),
                    )
                else:
                    weights = None
                self._cache.add_rec(rec, AREA, write_weights=True, weights=weights)
            else:
                self._cache.add_rec(rec, AREA, write_weights=False)

        # write last cache page to disk
        self._cache.write_weights(AREA)
        self._cache.write_emissions(AREA)

    def _get_road_weights(self):
        """Get cell weights for roads.
        returns a dict with road_id as keys and
        (index_array, weight_array) as values

        complete records from query result are stored in dict
        with road_id as key.
        """

        col_map = self._cache.col_maps[ROAD]
        for rec in self.querysets[ROAD]:
            source_id = rec[col_map.source_id]
            if source_id not in self._cache.gridded_sources[ROAD]:
                road_weights = {}
                # extract nodes from road geometry in WKT format
                wkt = rec[col_map.wkt]
                nodes = get_nodes_from_wkt(wkt)

                # if geometry is simplified, the length of the simplified
                # geometry should be used when rasterizing
                try:
                    road_length = rec[col_map.simple_length]
                except AttributeError:
                    road_length = rec[col_map.length]

                # sum weights for each segment to each cell index
                # (many segments can intersect the same cell)

                for i in range(1, len(nodes)):
                    p1_x, p1_y = nodes[i - 1]
                    p2_x, p2_y = nodes[i]

                    # rasterize segment and add weights to road_weights dict
                    # for each segment the weights are multiplied with
                    # the segment fraction of the road
                    # the resulting road weights will sum up to 1
                    ddaf_line_subpixel(
                        p1_x,
                        p1_y,
                        p2_x,
                        p2_y,
                        road_weights,
                        road_length,
                        self.extent,
                        self.dx,
                        self.dy,
                    )

                if len(road_weights) > 0:
                    indices = list(zip(*road_weights.keys()))

                    try:
                        ncells = indices[0].size
                    except AttributeError:
                        ncells = len(indices[0])
                    if self.levels is not None:
                        # road sources are added to lowest level
                        level = 0
                        # add z dimension to index array
                        index = (tuple([level] * ncells), indices[0], indices[1])
                    else:
                        index = (indices[0], indices[1])

                    # store cell indices and a weight array for each road id
                    weights = (
                        index,
                        np.fromiter(road_weights.values(), dtype=float),
                    )
                else:
                    weights = None
                self._cache.add_rec(rec, ROAD, write_weights=True, weights=weights)
            else:
                self._cache.add_rec(rec, ROAD, write_weights=False)

        # write last cache page to disk
        self._cache.write_weights(ROAD)
        # write a separate file for records of each substance
        self._cache.write_emissions(ROAD)

    def _get_grid_weights(self, polygon=None):
        """Store records of grid-sources in dict with source_id as key.

        returns a dict with source_id as keys and
        (index_array, weight_array) as values.

        Complete records from query
        result are stored in a dict with source_id as key.
        """
        col_map = self._cache.col_maps[GRID]
        for rec in self.querysets[GRID]:
            source_id = rec[col_map.source_id]
            raster_name = rec[col_map.raster]
            # spatial distribution of a grid is unique for each raster
            source_key = (source_id, raster_name)
            if source_key not in self._cache.gridded_sources[GRID]:
                try:
                    raster_data, metadata = get_gridsource_raster(
                        raster_name, clip_by=polygon
                    )
                except OutsideExtentError:
                    # no overlap between query and this grid,
                    # try next gridsource
                    break

                index_array, source_weights = resample_band(
                    raster_data,
                    metadata["extent"],
                    metadata["nodata"],
                    self.extent,
                    self.nx,
                    self.ny,
                    metadata["srid"],
                    self.srid,
                    subgridcells=2,
                )

                if len(source_weights) > 0:
                    if self.levels is not None:
                        # add weights in vertical direction
                        ac1 = rec[col_map.ac1]

                        if ac1 is not None:
                            # add indices and weights for vertical levels
                            try:
                                levels, level_weights = self.level_weights[ac1]
                            except KeyError:
                                # if no vertical distribution is assigned to the
                                # activity code, all emissions are put in the
                                # lowest layer
                                levels = np.array([0])
                                level_weights = np.ones(1, dtype=float)
                            index_array = (
                                np.tile(levels, index_array[0].size),
                                np.repeat(index_array[0], levels.size),
                                np.repeat(index_array[1], levels.size),
                            )
                            # weight each level with corresponding level-weight
                            source_weights = source_weights.repeat(
                                level_weights.size
                            ) * np.tile(level_weights, source_weights.size)
                        else:
                            index_array = (
                                np.zeros(index_array.size[0]),
                                index_array[0],
                                index_array[1],
                            )
                    weights = (index_array, source_weights)
                else:
                    weights = None

                # store emission record
                self._cache.add_rec(
                    rec,
                    GRID,
                    write_weights=True,
                    weights=weights,
                )
            else:
                self._cache.add_rec(rec, GRID)

        # write last cache page to disk
        self._cache.write_weights(GRID)
        self._cache.write_emissions(GRID)

    def _create_variables(  # noqa: C901, PLR0912, PLR0915
        self, substances, *, timeseries=True
    ):
        """create netCDF variables."""
        if timeseries:
            cell_methods = "1h-mean"
            time = True
            self.time_step = "1h"
        else:
            cell_methods = None
            time = False
            self.time_step = None

        self.variables = {}
        for substance in substances:
            result_file = os.path.join(self.output.path, substance.slug + ".nc")
            with nc.Dataset(result_file, "w", format="NETCDF4") as dset:
                write_general_attrs(dset)
                grid_mapping_var = self.create_gridmapping_variable(dset, self.crs)
                time_var, time_bounds_var = create_time_variable(dset)
                create_xy_variables(dset, self.extent, self.crs, self.nx, self.ny)
                subst_vars = self.variables.setdefault(substance.slug, {})
                # create variables also without emission in extent
                # if any(
                #     self._cache.has_substance(sourcetype, substance.id)
                #     for sourcetype in self.sourcetypes
                # ):
                param = Parameter.objects.get(quantity="emission", substance=substance)
                chunking = self._calc_chunking(
                    chunk_cache=1e8,
                )
                var_name = param.slug
                create_variable(
                    dset,
                    grid_mapping_var,
                    name=var_name,
                    unit=self.unit,
                    instance=self.instance,
                    cell_methods=cell_methods,
                    parameter=param.name,
                    time=time,
                    chunksizes=chunking,
                )
                subst_vars["field2d"] = {"emission": var_name}
        ncreated = 0
        for subst_vars in self.variables.values():
            for sourcetype_vars in subst_vars.values():
                ncreated += len(sourcetype_vars)
        return ncreated > 0

    def process(  # noqa: PLR0915
        self,
        substances,
        begin=None,
        end=None,
        sourcetypes=None,
        exclude_points=False,
        exclude_roads=False,
        point_ids=None,
        area_ids=None,
        grid_ids=None,
        road_ids=None,
        name=None,
        tags=None,
        polygon=None,
        ac1=None,
        ac2=None,
        ac3=None,
        cur=None,
        unit=None,
        aggregation=None,
        instance=None,
    ):
        """Write emissions to dataset.

        args:
            substances: an iterable of (or single) Substance model instances

        optional args:
            begin: datetime object in utc for first time rasterize
            end: datetime object in utc for last time to rasterize
            sourcetypes: 'point', 'area', 'grid' or 'road'
            exclude_points: point source emissions not rasterized
            exclude_roads: road source emissions not rasterized
            road_ids: list of road id's to include
            point_ids: list of road id's to include
            area_ids: list of road id's to include
            grid_ids: list of road id's to include
            name: source name (accepts regexp)
            tags: dictionary with tags and values to filter on
            polygon: only include sources within the provided polygon
            ac1: iterable of activity codes
            ac2: iterable of activity codes
            ac3: iterable of activity codes
            cur: db cursor object, used to execute query if provided
            unit: emission output unit
            aggregation: aggregation label of result variables
            instance: write emissions to specified variable instance
        """
        self.instance = instance
        self.aggregation = aggregation
        self.levels = None
        if polygon is None:
            # output extent
            x1, y1, x2, y2 = self.extent
            polygon = Polygon(
                ((x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)),
                srid=int(self.output.srid),
            )
        self.unit = unit or "kg/s"
        self.unit_conversion_factor = emis_conversion_factor_from_si(self.unit)

        # determine which sourcetypes should be rasterized
        self.sourcetypes = copy(sourcetypes) or list(SOURCETYPES)
        if exclude_points and POINT in self.sourcetypes:
            self.sourcetypes.remove(POINT)
        if exclude_roads and ROAD in self.sourcetypes:
            self.sourcetypes.remove(ROAD)

        if not hasattr(substances, "__iter__"):
            self.substances = [substances]
        else:
            self.substances = substances

        self.log.debug("reading records from database")

        # create querysets for all sources
        self._get_querysets(
            sourcetypes=sourcetypes,
            name=name,
            tags=tags,
            point_ids=point_ids,
            area_ids=area_ids,
            road_ids=road_ids,
            grid_ids=grid_ids,
            polygon=polygon,
            ac1=ac1,
            ac2=ac2,
            ac3=ac3,
            cur=cur,
        )
        try:
            Path(self.output.path).mkdir(exist_ok=True)
        except FileNotFoundError:
            raise FileNotFoundError(
                "parent directory of rasterized output does not exist "
                f"({str(self.output.path)})"
            )

        with EmissionCache(self.querysets) as cache:
            self._cache = cache

            self.log.debug("processing static data")
            # calculate raster cell weights for sources in querysets
            # and store in a dict
            self._get_weights(polygon=polygon)

            self.timezone = self.output.timezone

            if begin is not None and end is not None:
                self.log.debug("creating result variables")
                created = self._create_variables(self.substances, timeseries=True)

                # get time-variation profiles
                self._get_timevars(sourcetypes or SOURCETYPES)
                self.log.debug("calculating time-series emissions")
                self._process_timeseries(begin, end)
            else:
                self.log.debug("creating result variables")
                created = self._create_variables(self.substances, timeseries=False)
                # if no variables are created, skip out
                if not created:
                    self.reset()
                    self.log.info("no emissions found within requested extent")
                    return
                self.log.debug("calculating average emissions")
                self._process_average_emissions()

        self.reset()

    def _process_average_emissions(self):
        """Calculate average emission intensity for all substances and source-types."""
        for substance in self.substances:
            chunk = self._rasterize_average_chunk(substance, self.sourcetypes)

            if self.unit_conversion_factor != 1.0:
                chunk *= self.unit_conversion_factor
            result_file = os.path.join(self.output.path, substance.slug + ".nc")
            with nc.Dataset(result_file, "a", format="NETCDF4") as dset:
                self.set_data(dset, substance, chunk)

    def _process_timeseries(self, begin, end):  # noqa: C901, PLR0912
        # how many hours that will be processed in the same chunk
        # this is a compromise between required memory, execution time
        # the minimum chunk size of the netcdf variables is used

        min_time_chunksize = 1e9
        for substance in self.substances:
            result_file = os.path.join(self.output.path, substance.slug + ".nc")
            with nc.Dataset(result_file, "r", format="NETCDF4") as dset:
                # variable_name = 'Emission of '+substance.slug
                # or x, y, time
                time_chunking = dset.variables["time"].chunking()
                if time_chunking[0] < min_time_chunksize:
                    min_time_chunksize = time_chunking[0]

        # rasterizing chunks and writing to dataset
        chunk_begin = begin
        chunk_end = begin
        while chunk_end < end:
            # chunk includes chunk end-time, so nr of hours
            # should be reduced by one to get chunk dimension
            # matching chunksize
            chunk_end = min(
                chunk_begin + datetime.timedelta(hours=min_time_chunksize - 1), end
            )
            self.log.debug(
                f"processing {chunk_begin.strftime('%y%m%d %H')} "
                f"- {chunk_end.strftime('%y%m%d %H')}"
            )

            # emis intensity scaling time-series are generated from time-profiles
            self._timevariations_to_dataframe(chunk_begin, chunk_end)

            for substance in self.substances:
                self.log.debug(f"substance: {substance.slug}")
                # add raster timeseries
                emis_chunk = self._rasterize_chunk(
                    substance,
                    chunk_begin,
                    chunk_end,
                    self.sourcetypes,
                )

                if self.unit_conversion_factor != 1.0:
                    emis_chunk *= self.unit_conversion_factor

                result_file = os.path.join(self.output.path, substance.slug + ".nc")
                with nc.Dataset(result_file, "a", format="NETCDF4") as dset:
                    self.set_data(
                        dset,
                        substance,
                        emis_chunk,
                        timestamps=[chunk_begin, chunk_end],
                    )
                    # update time-span of variable and dataset

            # update chunk time interval
            chunk_begin = chunk_end + datetime.timedelta(hours=1)

    def set_data(self, dset, substance, data, timestamps=None):  # noqa: C901, PLR0912
        """Add chunk of data to variable."""

        var = dset[f"emission_{substance.slug}"]

        if timestamps is None:
            # map_oriented, np.flipud flips 2d data along second dimension
            var[:, :] = np.flipud(data)
        else:
            time_var = dset["time"]
            # map_oriented, np.fliplr flips 3d data along second dimension
            var[:, :, :] = np.fliplr(data)
            times = pd.date_range(timestamps[0], timestamps[1], freq=self.time_step)
            hours_since_1970 = (
                times - pd.to_datetime("1970-01-01").tz_localize(self.timezone)
            ).total_seconds() / 3600
            time_var[:] = hours_since_1970

    def _timeseries_emis(  # noqa: C901, PLR0912, PLR0915
        self, substance, begin, end, sourcetype
    ):
        """Get emission timeseries data chunk for sources.

        args:
            substance: substance to be processed as a Parameter instance
            begin: datatime object for first time-step to rasterize
            end: datetime object for last time-step to rasterize
            sourcetype: 'point or 'road'
        """

        self.log.debug(f"- discrete {sourcetype}sources")
        # number of timesteps in chunk
        timesteps = int((end - begin).total_seconds() / 3600) + 1

        # create an empty array
        emis_chunk = np.zeros(
            (timesteps, len(self._cache.feature_ids[sourcetype])), dtype=np.float32
        )

        # get mapping for query result column index
        col_map = self._cache.col_maps[sourcetype]

        # a template time-series that will be scaled with emission factors
        emis_fac_freeflow = np.ones((timesteps,))

        emis_ts = pd.Series(
            index=pd.date_range(start=begin, end=end, freq="h"),
            data=np.zeros((timesteps,)),
        )
        cstvs_cache = {}
        emis_fac_cache = {}
        # iterate over pages
        for page_ind in range(self._cache.emis_page_count(sourcetype, substance.pk)):
            page_nr = page_ind + 1
            try:
                emissions = self._cache.read_emissions(
                    sourcetype, substance.pk, page_nr
                )
            except NotInCacheError:
                break

            # aggregate emissions for each unique feature
            for rec in emissions:
                timevar_id = rec[col_map.timevar_id]
                emis = rec[col_map.emis]
                source_id = rec[col_map.source_id]

                # for road sources emissions are calculated using
                # ef corresponding to traffic condition for each hour
                if sourcetype == ROAD:
                    cstv_id = rec[col_map.coldstart_timevar_id]
                    coldstart_fraction = rec[col_map.coldstart_fraction]
                    coldstart_ef = rec[col_map.coldstart_ef]

                    # dataframe with coldstart time-variation for each hour
                    # (normalize coldstart var combined with flow variation)
                    if coldstart_fraction > 0 and coldstart_ef > 0:
                        if (cstv_id, timevar_id) not in cstvs_cache:
                            cstv_index = pd.date_range(
                                start=begin - datetime.timedelta(hours=1),
                                end=end - datetime.timedelta(hours=1),
                                freq="h",
                            )
                            cstvs_cache[(cstv_id, timevar_id)] = timevar_to_series(
                                cstv_index,
                                self.coldstart_timevars[cstv_id or "default"],
                                self.flow_timevars[timevar_id or "default"],
                                timezone=self.timezone,
                            )
                        coldstart_timevar_scalings = cstvs_cache[(cstv_id, timevar_id)]

                    # dataframe with intensity scalings for each hour
                    flow_timevar_scalings = self.flow_timevar_scalings[
                        timevar_id or "default"
                    ]
                    cong_prof_id = rec[col_map.congestion_profile_id or "default"]

                    # dataframe with traffic conditions (values 1-4)
                    traffic_conditions = self.traffic_conditions[
                        cong_prof_id or "default"
                    ]

                    # calculate emission timeseries
                    # exhaust emissions + coldstart emissions
                    flow = rec[col_map.veh_m_per_sec]
                    scaled_veh_flow = flow_timevar_scalings.to_numpy() * flow

                    freeflow_ef = rec[col_map.freeflow_ef]
                    heavy_ef = rec[col_map.heavy_ef]
                    saturated_ef = rec[col_map.saturated_ef]
                    stopngo_ef = rec[col_map.stopngo_ef]
                    emis_fac_key = (
                        cong_prof_id,
                        freeflow_ef,
                        heavy_ef,
                        saturated_ef,
                        stopngo_ef,
                    )

                    if emis_fac_key not in emis_fac_cache:
                        # array for emission factors for current vehicle
                        # one ef for each traffic condition

                        # create a full time-series of free-flow ef
                        emis_fac = emis_fac_freeflow * freeflow_ef

                        # replace ef where we have non free-flow conditions
                        emis_fac = np.where(traffic_conditions == 2, heavy_ef, emis_fac)
                        emis_fac = np.where(
                            traffic_conditions == 3, saturated_ef, emis_fac
                        )
                        emis_fac = np.where(
                            traffic_conditions == 4, stopngo_ef, emis_fac
                        )
                        emis_fac_cache[emis_fac_key] = emis_fac
                    else:
                        emis_fac = emis_fac_cache[emis_fac_key]

                    # calculate emission timeseries (kg/s)
                    if coldstart_ef > 0 and coldstart_fraction > 0:
                        coldstart_scaled_veh_flow = (
                            coldstart_timevar_scalings.to_numpy()
                            * coldstart_fraction
                            * coldstart_ef
                        )

                        emis_ts = (
                            scaled_veh_flow * emis_fac
                            + flow * coldstart_scaled_veh_flow
                        )
                    else:
                        emis_ts = scaled_veh_flow * emis_fac

                else:
                    # dataframe with intensity scalings for each hour
                    timevar_scalings = self.source_timevar_scalings[
                        timevar_id or "default"
                    ]

                    # calculate emission timeseries (kg/s)
                    emis_ts = timevar_scalings * emis

                # add emissions to chunk
                emis_chunk[:, self._cache.feature_ids[sourcetype][source_id]] += emis_ts
        return emis_chunk

    def _rasterize_average_chunk(self, substance, sourcetypes):
        """Rasterize and return emissions as a numpy array.

        args:
            substance: substance to be processed as Parameter instance
            sourcetypes: sequence containing 'point', 'area',
        """

        # create an empty array
        chunk = np.zeros((self.ny, self.nx), dtype=np.float32)

        for sourcetype in sourcetypes:
            if not self._cache.has_sourcetype(sourcetype):
                continue
            self.log.debug(f"gridding {sourcetype}sources")
            # iterate over pages
            for page_ind in range(
                self._cache.emis_page_count(sourcetype, substance.pk)
            ):
                page_nr = page_ind + 1
                try:
                    weights = self._cache.read_weights(sourcetype, page_nr)
                    emissions = self._cache.read_emissions(
                        sourcetype, substance.pk, page_nr
                    )
                except NotInCacheError:
                    break

                for rec in emissions:
                    col_map = self._cache.col_maps[sourcetype]
                    emis = rec[col_map.emis]
                    source_id = rec[col_map.source_id]

                    # NOTE: time-series emissions will not be possible to include
                    # without specifying a time-interval.
                    if sourcetype != GRID:
                        # get cell indices and weights for source
                        index_array, source_weights = weights[source_id]
                    else:
                        # get cell indices and weights for grid source raster
                        raster_name = rec[col_map.raster]
                        # get cell indices and weights for source
                        try:
                            index_array, source_weights = weights[
                                (source_id, raster_name)
                            ]
                        except KeyError:
                            # grid has no emissions within modelling area
                            continue

                    # add emissions to chunk at each index
                    chunk[index_array] += emis * source_weights

        return chunk

    def _timeseries_average_chunk(self, substance, sourcetype):
        """Get emissions for sources as a numpy array.

        args:
            substance: substance to be processed as Parameter instance
            sourcetype: 'point' or 'road'
        """

        # create an empty array
        chunk = np.zeros((self.ny, self.nx), dtype=np.float32)

        # create an empty array
        chunk = np.zeros((len(self._cache.feature_ids[sourcetype]),), dtype=np.float32)

        col_map = self._cache.col_maps[sourcetype]
        # iterate over pages
        for page_ind in range(self._cache.emis_page_count(sourcetype, substance.pk)):
            page_nr = page_ind + 1
            try:
                emissions = self._cache.read_emissions(
                    sourcetype, substance.pk, page_nr
                )
            except NotInCacheError:
                break

            # aggregate emissions for each unique feature
            for rec in emissions:
                emis = rec[col_map.emis]
                source_id = rec[col_map.source_id]
                chunk[self._cache.feature_ids[sourcetype][source_id]] += emis
        return chunk

    def _rasterize_chunk(  # noqa: C901, PLR0912, PLR0915
        self, substance, begin, end, sourcetypes
    ):
        """Rasterize and return as numpy array.

        args:
            substance: substance to process as Parameter instance
            begin: datatime object for first time-step to rasterize
            end: datetime object for last time-step to rasterize
            sourcetypes: sequence containing 'point', 'area'
        """

        # number of timesteps in chunk
        nr_timesteps = int((end - begin).total_seconds() / 3600) + 1

        # create an empty array
        chunk = np.zeros((nr_timesteps, self.ny, self.nx), dtype=np.float32)
        emis_fac_freeflow = np.ones((nr_timesteps,))
        cstvs_cache = {}
        emis_fac_cache = {}
        for sourcetype in sourcetypes:
            if not self._cache.has_sourcetype(sourcetype):
                continue
            self.log.debug(f"-gridding {sourcetype}sources")
            # iterate over pages
            for page_ind in range(
                self._cache.emis_page_count(sourcetype, substance.pk)
            ):
                page_nr = page_ind + 1
                try:
                    weights = self._cache.read_weights(sourcetype, page_nr)
                    emissions = self._cache.read_emissions(
                        sourcetype, substance.pk, page_nr
                    )
                except NotInCacheError:
                    break

                for rec in emissions:
                    col_map = self._cache.col_maps[sourcetype]
                    timevar_id = rec[col_map.timevar_id]
                    emis = rec[col_map.emis]
                    source_id = rec[col_map.source_id]

                    # for road sources emissions are calculated using
                    # ef corresponding to traffic condition for each hour
                    if sourcetype == ROAD:
                        cstv_id = rec[col_map.coldstart_timevar_id]
                        coldstart_fraction = rec[col_map.coldstart_fraction]
                        coldstart_ef = rec[col_map.coldstart_ef]

                        # dataframe with coldstart time-variation for each hour
                        # (normalize coldstart var combined with flow variation)
                        if coldstart_fraction > 0 and coldstart_ef > 0:
                            if (cstv_id, timevar_id) not in cstvs_cache:
                                cstv_index = pd.date_range(
                                    start=begin - datetime.timedelta(hours=1),
                                    end=end - datetime.timedelta(hours=1),
                                    freq="h",
                                )
                                cstvs_cache[(cstv_id, timevar_id)] = timevar_to_series(
                                    cstv_index,
                                    self.coldstart_timevars[cstv_id or "default"],
                                    self.flow_timevars[timevar_id or "default"],
                                    timezone=self.timezone,
                                )
                            coldstart_timevar_scalings = cstvs_cache[
                                (cstv_id, timevar_id)
                            ]

                        # dataframe with intensity scalings for each hour
                        flow_timevar_scalings = self.flow_timevar_scalings[
                            timevar_id or "default"
                        ]
                        cong_prof_id = rec[col_map.congestion_profile_id or "default"]

                        # dataframe with traffic conditions (values 1-4)
                        traffic_conditions = self.traffic_conditions[
                            cong_prof_id or "default"
                        ]

                        # calculate emission timeseries
                        # exhaust emissions + coldstart emissions
                        flow = rec[col_map.veh_m_per_sec]
                        scaled_veh_flow = flow_timevar_scalings.to_numpy() * flow

                        freeflow_ef = rec[col_map.freeflow_ef]
                        heavy_ef = rec[col_map.heavy_ef]
                        saturated_ef = rec[col_map.saturated_ef]
                        stopngo_ef = rec[col_map.stopngo_ef]

                        emis_fac_key = (
                            cong_prof_id,
                            freeflow_ef,
                            heavy_ef,
                            saturated_ef,
                            stopngo_ef,
                        )
                        if emis_fac_key not in emis_fac_cache:
                            # array for emission factors for current vehicle
                            # one ef for each traffic condition
                            emis_fac = emis_fac_freeflow * freeflow_ef
                            emis_fac = np.where(
                                traffic_conditions == 2, heavy_ef, emis_fac
                            )
                            emis_fac = np.where(
                                traffic_conditions == 3, saturated_ef, emis_fac
                            )
                            emis_fac = np.where(
                                traffic_conditions == 4, stopngo_ef, emis_fac
                            )
                            emis_fac_cache[emis_fac_key] = emis_fac
                        else:
                            emis_fac = emis_fac_cache[emis_fac_key]

                        if coldstart_ef > 0 and coldstart_fraction > 0:
                            coldstart_scaled_veh_flow = (
                                coldstart_timevar_scalings.to_numpy()
                                * coldstart_fraction
                                * coldstart_ef
                            )

                            emis_ts = (
                                scaled_veh_flow * emis_fac
                                + flow * coldstart_scaled_veh_flow
                            )
                        else:
                            emis_ts = scaled_veh_flow * emis_fac

                    else:
                        # dataframe with intensity scalings for each hour
                        timevar_scalings = self.source_timevar_scalings[
                            timevar_id or "default"
                        ]

                        # calculate emission timeseries scaled by timevar
                        emis_ts = timevar_scalings.to_numpy() * emis

                    if sourcetype != GRID:
                        # get cell indices and weights for source
                        index_array, source_weights = weights[source_id]
                    else:
                        raster_name = rec[col_map.raster]
                        try:
                            index_array, source_weights = weights[
                                (source_id, raster_name)
                            ]
                        except KeyError:
                            # grid has no emissions within modelling area
                            continue
                    # add time dimension to index array
                    try:
                        ncells = index_array[0].size
                    except AttributeError:
                        ncells = len(index_array[0])
                    index_array = (
                        np.tile(np.arange(nr_timesteps), ncells),
                        np.repeat(index_array[0], nr_timesteps),
                        np.repeat(index_array[1], nr_timesteps),
                    )

                    # organize 1D-array of emissions as the index array
                    emis_array = (source_weights * emis_ts[:, np.newaxis]).T.reshape(-1)

                    # add emissions to chunk at each index
                    chunk[index_array] += emis_array
        return chunk

    def _calc_chunking(
        self, time_chunksize=None, spatial_chunksize=None, chunk_cache=1e7
    ):
        """Return chunksizes for variable dimensions."""

        # if there is no time-dimension, chunking is not needed
        # for grids smaller than 100 x 100, chunksize covers the whole grid
        if len(self.timevars) == 0:
            return None

        # ensure chunk size is not larger than grid
        chunk_nx = min(self.nx, spatial_chunksize or 5)
        chunk_ny = min(self.ny, spatial_chunksize or 5)

        if time_chunksize is None:
            # assumes single precision (4 bytes per value)
            # max estimate based on full grid rather than limiting to spatial chunks,
            # (more practical if full grid fits in memory...)

            field_size_bytes = self.nx * self.ny * 4
            max_time_chunksize = int(chunk_cache / field_size_bytes)

            if self.time_step is not None:
                time_chunksize = int(
                    datetime.timedelta(hours=366 * 24)
                    / time_step_as_delta(self.time_step)
                )
            else:
                time_chunksize = 366

            time_chunksize = min(time_chunksize, max_time_chunksize)

        return (time_chunksize, chunk_ny, chunk_nx)

    def create_gridmapping_variable(self, dset: nc.Dataset, crs: rio.CRS):
        name = f"EPSG_{crs.to_epsg()}"
        grid_mapping = dset.createVariable(name, "i")
        epsg = crs.to_epsg()
        if epsg is None:
            epsg = crs.to_epsg(confidence_threshold=30)
            self.log.info(
                f"No exact match for EPSG and spatial ref, using best guess: {epsg}"
            )
            grid_mapping.srid = epsg
        grid_mapping.crs_wkt = crs.to_wkt()  # for CF Conventions 1.7
        return grid_mapping


def create_variable(
    dset: nc.Dataset,
    grid_mapping: nc.Variable,
    name: str,
    unit: Optional[str] = None,
    quantity: Optional[str] = None,
    instance: Optional[str] = None,
    cell_methods: Optional[str] = None,
    parameter: Optional[str] = None,
    height: Optional[float] = None,
    time: bool = True,
    chunksizes: Optional[tuple[int, ...]] = None,
):
    """create 2D variable."""
    if time:
        var = dset.createVariable(
            name,
            "f4",
            (TIME_NAME, Y_NAME, X_NAME),
            fill_value=np.nan,
            zlib=True,
            chunksizes=chunksizes,
        )
    else:
        var = dset.createVariable(
            name, "f4", (Y_NAME, X_NAME), fill_value=np.nan, zlib=True
        )

    var.units = unit or "unknown"
    var.grid_mapping = grid_mapping.name
    if parameter is not None:
        var.parameter = parameter
    if quantity is not None:
        var.quantity = quantity
    if instance is not None:
        var.instance = instance
    if cell_methods is not None:
        var.cell_methods = cell_methods
    if height is not None:
        var.height = height
    return var


GENERAL_ATTRIBUTES = [("Created_using_cetk", __version__)]


def write_general_attrs(dset: nc.Dataset):
    """add some global attributes."""
    for name, attr in GENERAL_ATTRIBUTES:
        if not hasattr(dset, name):
            setattr(dset, name, attr)

    if not hasattr(dset, "history"):
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime(
            "%Y%m%d %H:%M"
        )
        dset.history = f"{timestamp} created dataset"


# name of time-dimension and time-variable
TIME_NAME = "time"
X_NAME = "x"
Y_NAME = "y"
# name of time-bounds dimension and time-bounds variable
TIME_BOUNDS_NAME = "time_bounds"
# name of second dimension for bounds variables
BOUNDS_DIMENSION = "bounds_dim"
# netCDF reference time
TIME_ZERO = datetime.datetime(
    year=1970, month=1, day=1, hour=0, minute=0, second=0, tzinfo=datetime.timezone.utc
)


def create_time_variable(dset: nc.Dataset):
    """create time variable."""

    times = dset.createDimension(TIME_NAME, None)
    dset.createDimension(BOUNDS_DIMENSION, 2)
    times = dset.createVariable(TIME_NAME, "f8", (TIME_NAME,))
    times.calendar = "gregorian"
    times.units = f"hours since {TIME_ZERO:%Y-%m-%d %H:%M:%S}"
    times.bounds = TIME_BOUNDS_NAME
    times.long_name = "time"
    times.axis = "T"
    time_bounds = dset.createVariable(
        TIME_BOUNDS_NAME, "f8", (TIME_NAME, BOUNDS_DIMENSION)
    )
    return times, time_bounds


def create_xy_variables(
    dset: nc.Dataset, extent: tuple, crs: rio.CRS, nx: int, ny: int
):
    """Create a netCDF dataset with dimensions and metadata for 2D fields."""

    x1, y1, x2, y2 = extent
    dx = (x2 - x1) / nx
    dy = (y2 - y1) / ny

    dset.createDimension(X_NAME, nx)
    # create projected coordinate variables
    x = dset.createVariable(X_NAME, "f4", (X_NAME,))
    x.standard_name = "projection_x_coordinate"
    x.units = "m"
    x.axis = "X"
    x.description = "center of cell"
    x[:] = np.linspace(x1 + 0.5 * dx, x2 - 0.5 * dx, nx)

    dset.createDimension(Y_NAME, ny)
    y = dset.createVariable(Y_NAME, "f4", (Y_NAME,))
    y.standard_name = "projection_y_coordinate"
    y.units = "m"
    y.axis = "Y"
    y.description = "center of cell"
    y[:] = np.linspace(y1 + 0.5 * dy, y2 - 0.5 * dy, ny)
    return x, y


def make_naive_in_utc(time: datetime.datetime):
    """convert time to utc and make naive."""
    if time.tzinfo is not None:
        time_utc = time.astimezone(datetime.timezone.utc)
        time_utc.replace(tzinfo=None)
    else:
        time_utc = time
    return time_utc


def write_time(
    time_var: nc.Variable, time_bounds_var: nc.Variable, time_utc: datetime.datetime
):
    """write timestamp to file and return time-index"""

    left_bound = time_utc - datetime.timedelta(hours=1)
    # get index of time in netCDF
    if len(time_var) == 0:
        time_index = 0
    else:
        time_index = nc.date2index(time_utc, time_var, select="before") + 1

    # write time to netCDF (in numerical format)
    nc_time = nc.date2num(time_utc, time_var.units)
    nc_left_time_bound = nc.date2num(left_bound, time_var.units)
    nc_right_time_bound = nc_time

    time_bounds_var[time_index, :] = [nc_left_time_bound, nc_right_time_bound]
    time_var[time_index] = nc_time
    return time_index


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
