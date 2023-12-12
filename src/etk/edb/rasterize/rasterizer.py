"""Rasterization of emission sources."""

import datetime
from copy import copy
from math import ceil

import numpy as np
import pandas as pd
from django.contrib.gis.geos import Polygon
from rastafari import even_odd_polygon_fill

# TODO EmissionCache needs to be updated when road and grid sources introduced
from etk.edb.cache import EmissionCache, NotInCacheError
from etk.edb.models.common_models import Settings
from etk.edb.models.source_models import (
    AreaSource,
    Parameter,
    PointSource,
    Timevar,
    timevar_to_series,
)
from etk.edb.units import emis_conversion_factor_from_si
from etk.emissions.calc import calculate_source_emissions
from etk.tools.utils import get_nodes_from_wkt

# short  source type identifiers for conveniency
POINT = PointSource.sourcetype
AREA = AreaSource.sourcetype

# supported source types
SOURCETYPES = (POINT, AREA)


class Field2D:
    pass


class Field3D:
    pass


class EmissionRasterizer:
    """An emission time-series rasterizer.

    writes emissions to outputfile in units kg/s

    """

    def __init__(
        self,
        output,
        nx,
        ny,
        job=None,
    ):
        """
        args
            output: output.path: path to store NetCDF files
                    output.extent: extent of the raster (x1, y1, x2, y2)
                    output.srid: SRID of output
                    output.timezone: timezone of output
            nx: raster dimension in x-direction
            ny: raster dimension in y-direction
        """
        self.timevars = {}
        self.level_weights = {}
        self.output = output
        self.extent = output.extent
        self._cache = None
        self.nx = nx
        self.ny = ny
        self.sourcetypes = []

        # querysets for emission
        self.querysets = {}

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

        if POINT in sourcetypes or AREA in sourcetypes:
            for tvar in self.timevars.all():
                self.timevars[tvar.id] = tvar
            default = Timevar
            self.timevars["default"] = default

    def _get_level_weights(self):
        """redistribute vertical distr. into levels of result dataset."""
        # don't use levels yet
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
            # eval is needed in etk because arrays stored as CharField in sqlite
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
        time_index = pd.date_range(begin, end, freq="H")
        one_hour = datetime.timedelta(hours=1)
        shifted_index = pd.date_range(begin - one_hour, end - one_hour, freq="H")
        self.source_timevar_scalings = pd.DataFrame(
            {
                tvar.id
                or "default": timevar_to_series(
                    shifted_index, tvar, timezone=self.timezone
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
        polygon=None,
        substances=None,
        ac1=None,
        ac2=None,
        ac3=None,
        *,
        cur=None,
    ):
        """Get querysets for emissions."""
        # TODO cannot use calculate_source_emissions() because need to filter for ac!
        # TODO is substances only used for traffic work, or also something else?
        sourcetypes = sourcetypes or SOURCETYPES
        # not used; srid = Settings.get_current().srid

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
                if not PointSource.objects.exists:
                    continue
                ids = point_ids
            elif sourcetype == AREA:
                if not AreaSource.objects.exists:
                    continue
                ids = area_ids
            else:
                raise ValueError(
                    f"Rasterize cannot handle sourcetype {sourcetype} yet."
                )
            # TODO check, should add unit="kg/s"? default unit for
            # calculate_source_emissions is kg/year!
            self.querysets[sourcetype] = calculate_source_emissions(
                sourcetype,
                substances=substances,
                name=name,
                ids=ids,
                tags=tags,
                polygon=polygon,
            )

    def _get_weights(self):
        """Get cell weights for all sourcetypes."""

        for sourcetype in self.querysets:
            if sourcetype == POINT:
                self._get_point_weights()
            elif sourcetype == AREA:
                self._get_area_weights()

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
                x = rec[col_map.x]
                y = rec[col_map.y]
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

                even_odd_polygon_fill(
                    nodes,
                    source_weights,
                    self.dataset.extent,
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

    def _create_variables(  # noqa: C901, PLR0912, PLR0915
        self, substances, *, timeseries=True
    ):
        """create netCDF variables."""

        if timeseries:
            time_unit = "hours"
            time_step = "1H"
        else:
            time_unit = None
            time_step = None

        self.variables = {}
        for substance in substances:
            subst_vars = self.variables.setdefault(substance.slug, {})
            # create dataset variables for storage
            if any(
                self._cache.has_substance(sourcetype, substance.id)
                for sourcetype in self.sourcetypes
            ):
                param = Parameter.objects.get(quantity="emission", substance=substance)
                # TODO function create_field2d not implemented yet,
                # this should be replaced by solweig alternative?
                # should not create table Field2D like in gadget, we do not
                # want the fields in database.
                subst_vars[Field2D.VARIABLE_TYPE] = {
                    "emission": self.dataset.create_field2d(
                        parameter=param,
                        name=f"Emission of {substance.name}",
                        unit=self.unit,
                        time_unit=time_unit,
                        time_step=time_step,
                        aggregation=self.aggregation,
                        instance=self.instance,
                        nx=self.nx,
                        ny=self.ny,
                        chunk_cache=1e8,
                    )
                }
        ncreated = 0
        for subst_vars in self.variables.values():
            for sourcetype_vars in subst_vars.values():
                ncreated += len(sourcetype_vars)
        # return True if any variables are created
        return ncreated > 0

    def process(  # noqa: PLR0915
        self,
        substances,
        begin=None,
        end=None,
        sourcetypes=None,
        *,
        exclude_points=False,
        point_ids=None,
        area_ids=None,
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
        if polygon is None:
            # output extent
            x1, y1, x2, y2 = self.extent
            polygon = Polygon(
                ((x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)),
                srid=self.output.srid,
            )

        self.unit = unit or "kg/s"
        self.unit_conversion_factor = emis_conversion_factor_from_si(self.unit)

        # determine which sourcetypes should be rasterized
        self.sourcetypes = copy(sourcetypes) or list(SOURCETYPES)
        if exclude_points and POINT in self.sourcetypes:
            self.sourcetypes.remove(POINT)

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
            polygon=polygon,
            ac1=ac1,
            ac2=ac2,
            ac3=ac3,
            cur=cur,
        )
        with EmissionCache(self.querysets) as cache:
            self._cache = cache

            self.log.debug("processing static data")
            # calculate raster cell weights for sources in querysets
            # and store in a dict
            self._get_weights()

            self.timezone = self.output.timezone

            if begin is not None and end is not None:
                self.log.debug("creating result variables")
                # TODO, how should this be done when we don't have traffic work
                # and thus no substances with extras?
                # created = self._create_variables(self.substances, timeseries=True) ?
                created = self._create_variables(
                    self.substances_with_extras, timeseries=True
                )
                # if no variables are created, skip out
                if not created:
                    self.reset()
                    self.log.debug("no emissions found within requested extent")
                    return

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
            subst_vars = self.variables[substance.slug]
            # get average emissions (without time-dimension)
            for sourcetype_vars in subst_vars.values():
                for var in sourcetype_vars.values():
                    if isinstance(var, (Field2D, Field3D)):
                        chunk = self._rasterize_average_chunk(
                            substance, self.sourcetypes_as_raster
                        )
                    else:
                        chunk = self._timeseries_average_chunk(
                            substance, var.feature_type
                        )

                    if self.unit_conversion_factor != 1.0:
                        chunk *= self.unit_conversion_factor
                    with var.open("a"):
                        var.set_data(chunk)
                        var.save()

    def _process_timeseries(self, begin, end):  # noqa: C901, PLR0912
        # how many hours that will be processed in the same chunk
        # this is a compromise between required memory, execution time
        # the minimum chunk size of the netcdf variables is used
        min_time_chunksize = 1e9
        for substance_vars in self.variables.values():
            for vartypes in substance_vars.values():
                for v in vartypes.values():
                    with v.open("r"):
                        if v.get_time_chunksize() < min_time_chunksize:
                            min_time_chunksize = v.get_time_chunksize()

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
                subst_vars = self.variables[substance.slug]
                for sourcetype_vars in subst_vars.values():
                    try:
                        var = sourcetype_vars["emission"]
                    except KeyError:
                        # no emissions for sourcetype
                        continue
                    # TODO how is this done without Field2D class?
                    if isinstance(var, (Field2D, Field3D)):
                        # add raster timeseries
                        emis_chunk = self._rasterize_chunk(
                            substance,
                            chunk_begin,
                            chunk_end,
                            self.sourcetypes,
                        )
                    else:
                        # add point or road timeseries
                        emis_chunk = self._timeseries_emis(
                            substance, chunk_begin, chunk_end, var.feature_type
                        )

                    if self.unit_conversion_factor != 1.0:
                        emis_chunk *= self.unit_conversion_factor
                    with var.open("a"):
                        if isinstance(var, Field3D):
                            var.set_data(
                                emis_chunk,
                                timestamps=[chunk_begin, chunk_end],
                                contiguous=True,
                                sparse=False,
                            )
                        else:
                            var.set_data(
                                emis_chunk,
                                timestamps=[chunk_begin, chunk_end],
                                contiguous=True,
                            )
                        # update time-span of variable and dataset
                        var.save()

            # update chunk time interval
            chunk_begin = chunk_end + datetime.timedelta(hours=1)

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

        emis_ts = pd.Series(
            index=pd.date_range(start=begin, end=end, freq="H"),
            data=np.zeros((timesteps,)),
        )

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

                # dataframe with intensity scalings for each hour
                timevar_scalings = self.source_timevar_scalings[timevar_id or "default"]

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

                    # get cell indices and weights for source
                    index_array, source_weights = weights[source_id]

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

                    # dataframe with intensity scalings for each hour
                    timevar_scalings = self.source_timevar_scalings[
                        timevar_id or "default"
                    ]
                    if (
                        sourcetype == POINT
                        and rec[col_map.temperature_variation_id] is not None
                    ):
                        # temperature variation scaling must be done per record,
                        # since it depends on coordinates of point (through T2m)
                        if self.t2m_field2d is not None:
                            temperature_variation_scalings = (
                                self._get_pointsource_tempvar_weights(
                                    begin, end, rec, col_map
                                )
                            )
                            # making sure yearly total is conserved, varied to T2m
                            emis_ts = temperature_variation_scalings.to_numpy() * emis
                        else:
                            # TODO give error instead of warning!
                            raise RuntimeError(
                                f"Dataset has no temperature - "
                                f"cannot apply temperature-based variation for "
                                f"source {source_id}"
                            )
                    else:
                        # calculate emission timeseries scaled by timevar
                        emis_ts = timevar_scalings.to_numpy() * emis

                    # get cell indices and weights for source
                    index_array, source_weights = weights[source_id]

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
