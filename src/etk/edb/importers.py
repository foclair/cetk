"""Data importers for the edb application."""

# import copy
import logging
from itertools import islice

import numpy as np
import pandas as pd
from django.contrib.gis.gdal import (
    AxisOrder,
    CoordTransform,
    DataSource,
    SpatialReference,
)
from django.contrib.gis.geos import Point, Polygon

# from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management.base import CommandError
from django.db import IntegrityError
from openpyxl import load_workbook

from etk.edb.const import WGS84_SRID
from etk.edb.models import (  # CodeSet,
    ActivityCode,
    Facility,
    PointSource,
    PointSourceSubstance,
    Substance,
    Timevar,
)
from etk.edb.units import emission_unit_to_si  # , vehicle_ef_unit_to_si

# from collections import OrderedDict
# from operator import itemgetter


log = logging.getLogger(__name__)

STATIC_POINT_SOURCE_ATTRIBUTE = [
    "name",
    "chimney_height",
    "chimney_outer_diameter",
    "chimney_inner_diameter",
    "chimney_gas_speed",
    "chimney_gas_temperature",
    "house_width",
    "house_height",
]


class ImportError(Exception):
    """Error while importing emission data."""

    pass


class TranslationFileError(Exception):
    """Structural error in translation file."""

    pass


def handle_msg(messages, msg, fail_early=False):
    """handle repeated error without bloating stderr/stdout.

    args
        messages: dict where messages are accumulated
        msg: message string
        fail_early: exit directly
    """

    if fail_early:
        raise ImportError(msg)

    if msg not in messages:
        log.debug(f"debug: {msg}")
        messages[msg] = 1
    else:
        messages[msg] += 1


def import_timevars(timevar_data, overwrite=False):
    """import time-variation profiles."""

    # Timevar instances must not be created by bulk_create as the save function
    # is overloaded to calculate the normation constant.
    def make_timevar(data, timevarclass, subname=None):
        retdict = {}
        for name, timevar_data in data.items():
            try:
                typeday = timevar_data["typeday"]
                month = timevar_data["month"]

                if overwrite:
                    newobj, _ = timevarclass.objects.update_or_create(
                        name=name,
                        defaults={"typeday": typeday, "month": month},
                    )
                else:
                    try:
                        newobj = timevarclass.objects.create(
                            name=name, typeday=typeday, month=month
                        )
                    except IntegrityError:
                        raise IntegrityError(
                            f"{timevarclass.__name__} {name} "
                            f"already exist in inventory."
                        )
                retdict[name] = newobj
            except KeyError:
                raise ImportError(
                    f"Invalid specification of timevar {name}"
                    f", are 'typeday' and 'month' given?"
                )
        return retdict

    timevars = {}
    for vartype, subdict in timevar_data.items():
        if vartype == "emission":
            timevars["emission"] = make_timevar(timevar_data[vartype], Timevar)
        else:
            raise ImportError(f"invalid time-variation type '{vartype}' specified")
    return timevars


class PointSourceSeries(pd.core.series.Series):
    def get(self, attr_name):
        return self[attr_name]


def filter_out(feature, exclude):
    """filter features by attribute."""

    for attr_name, val in exclude.items():
        if val != str(feature.get(attr_name)):
            return False
    return True


def import_point_sources(
    sourcefile,
    config,
    timevars=None,
    exclude=None,
    only=None,
    codeset=None,
):
    psp = PointSourceParser(sourcefile, config, timevars, exclude, only, codeset)
    psp.parsefile()
    pslist = [psp.psdict[key] for key in psp.psdict.keys()]
    psp.sourcemodel.objects.bulk_create([ps["source"] for ps in pslist])
    substlist = list()
    for ps in pslist:
        for values in psp.substdict.values():
            if values["substance"] in ps["substvals"]:
                emission = ps["substvals"][values["substance"]]
                if emission[0] is not None:
                    substlist.append(
                        psp.substancemodel(
                            source=ps["source"],
                            substance=values["substance"],
                            value=emission_unit_to_si(emission[0], emission[1]),
                        )
                    )
    psp.substancemodel.objects.bulk_create(substlist)


class PointSourceParser:
    def __init__(
        self,
        sourcefile,
        config,
        timevars=None,
        exclude=None,
        only=None,
        codeset=None,
    ):
        self.sourcefile = sourcefile
        self.config = config
        if timevars is None:
            self.timevars = timevars
        else:
            self.timevars = timevars["emission"]
        self.exclude = exclude
        self.only = only
        self.codeset = codeset
        self.psdict = dict()

    def parsefile(self):
        if self.sourcefile.endswith(".csv"):
            self.parse_csv_file()
        elif self.sourcefile.endswith(".shp"):
            self.parse_shape_file()
        elif self.sourcefile.endswith(".xlsx"):
            self.parse_spreadsheet()
        else:
            raise ImportError("Input file can only have extension .csv, .shp or .xlsx")

    def parse_csv_file(self):
        if "delimiter" in self.config:
            delimiter = self.config["delimiter"]
        else:
            delimiter = None
        try:
            df = pd.read_csv(self.sourcefile, delimiter=delimiter)
        except Exception as exc:
            raise CommandError(str(exc))
        self.get_substdict()
        if "srid" in self.config:
            src_proj = SpatialReference(
                self.config["srid"], axis_order=AxisOrder.AUTHORITY
            )
        else:
            raise RuntimeError(
                "No coordinate system provided. " "Set srid parameter in config file."
            )
        if len(self.config["coordinates"]) == 2:
            self.sourcemodel = PointSource
            self.substancemodel = PointSourceSubstance
            self.possible_attributes = STATIC_POINT_SOURCE_ATTRIBUTE
        # elif len(self.config["coordinates"]) == 4:
        #     self.sourcemodel = AreaSource
        #     self.substancemodel = AreaSourceSubstance
        #     self.possible_attributes = STATIC_AREA_SOURCE_ATTRIBUTE
        target_proj = SpatialReference(WGS84_SRID)
        self.trans = CoordTransform(src_proj, target_proj)
        for i, row in df.iterrows():
            feature = PointSourceSeries(row)
            if self.exclude is not None and filter_out(feature, self.exclude):
                continue
            if self.only is not None and not filter_out(feature, self.only):
                continue
            try:
                psvals = self.get_ps_vals(feature)
            except Skip:
                continue
            if "substance" in psvals:
                if psvals["substance"] not in self.substdict:
                    self.update_substdict(psvals["substance"])
                substvals = self.get_subst_vals_attribute(feature, psvals["substance"])
            else:
                substvals = self.get_subst_vals(feature)
            geom = self.geometry(row)
            self.update_psdict(psvals, substvals, geom)

    def geometry(self, row):
        coordinates = self.config["coordinates"]
        if self.sourcemodel == PointSource:
            geom = Point(row[coordinates[0]], row[coordinates[1]])
        else:
            geom = Polygon(
                [
                    (row[coordinates[0]], row[coordinates[1]]),
                    (row[coordinates[2]], row[coordinates[1]]),
                    (row[coordinates[2]], row[coordinates[3]]),
                    (row[coordinates[0]], row[coordinates[3]]),
                    (row[coordinates[0]], row[coordinates[1]]),
                ]
            )
        geom.transform(self.trans)
        return geom

    def parse_shape_file(self):
        try:
            datasource = DataSource(self.sourcefile)
        except Exception as exc:
            raise CommandError(str(exc))
        layer = datasource[0]
        self.get_substdict()

        if "srid" in self.config:
            src_proj = SpatialReference(
                self.config["srid"], axis_order=AxisOrder.AUTHORITY
            )
        else:
            src_proj = layer.srs
        if layer.geom_type.name == "Point":
            self.sourcemodel = PointSource
            self.substancemodel = PointSourceSubstance
            self.possible_attributes = STATIC_POINT_SOURCE_ATTRIBUTE
        # elif layer.geom_type.name == "Polygon":
        #     self.sourcemodel = AreaSource
        #     self.substancemodel = AreaSourceSubstance
        #     self.possible_attributes = STATIC_AREA_SOURCE_ATTRIBUTE
        target_proj = SpatialReference(WGS84_SRID)
        self.trans = CoordTransform(src_proj, target_proj)
        for feature in layer:
            if self.exclude is not None and filter_out(feature, self.exclude):
                continue
            if self.only is not None and not filter_out(feature, self.only):
                continue
            try:
                psvals = self.get_ps_vals(feature)
            except Skip:
                continue

            if "substance" in psvals:
                if psvals["substance"] not in self.substdict:
                    self.update_substdict(psvals["substance"])
                substvals = self.get_subst_vals_attribute(feature, psvals["substance"])
            else:
                substvals = self.get_subst_vals(feature)
            geom = feature.geom
            geom.transform(self.trans)
            self.update_psdict(psvals, substvals, geom.geos)

    def parse_spreadsheet(self):
        try:
            workbook = load_workbook(filename=self.sourcefile)
        except Exception as exc:
            raise CommandError(str(exc))
        worksheet = workbook.worksheets[0]
        if len(workbook.worksheets) > 1:
            log.debug("debug: multiple sheets in spreadsheet, only importing 1st.")
        data = worksheet.values
        cols = next(data)[1:]
        data = list(data)
        idx = [r[0] for r in data]
        data = (islice(r, 1, None) for r in data)
        df = pd.DataFrame(data, index=idx, columns=cols)
        print(df)
        # TODO same here with df as in parse_csv ?

    def get_substdict(self):
        self.substdict = dict()
        if "emissions" in self.config:
            for subst, values in self.config["emissions"].items():
                # breakpoint()
                substance = Substance.objects.get(slug=subst)
                values.update({"substance": substance})
                if "emission" not in values:
                    values.update({"emission": self.config["parameters"]["emission"]})
                if "unit" not in values and "unitval" not in values:
                    try:
                        values.update({"unit": self.config["parameters"]["unit"]})
                    except KeyError:
                        values.update({"unitval": self.config["defaults"]["unit"]})
                self.substdict[subst] = values
        else:
            # will be filled while parsing datafile
            self.substdict = dict()

    def update_substdict(self, subst):
        try:
            substance = Substance.objects.get(slug=subst)
        except Substance.DoesNotExist as e:
            raise Substance.DoesNotExist(subst + ": " + str(e))
        self.substdict[subst] = {
            "substance": substance,
            "emission": self.config["parameters"]["emission"],
        }
        try:
            self.substdict[subst]["unit"] = self.config["parameters"]["unit"]
        except KeyError:
            self.substdict[subst]["unitval"] = self.config["defaults"]["unit"]

    def update_psdict(self, psvals, substvals, geom):
        sourcearguments = {
            "geom": geom,
        }
        if self.timevars is not None:
            sourcearguments["timevar"] = self.timevars[psvals["timevar"]]

        if "facility_id" in psvals:
            if "facility_name" in psvals:
                name = psvals["facility_name"]
            else:
                name = psvals["facility_id"]
            facility, _ = Facility.objects.get_or_create(
                name=name, official_id=psvals["facility_id"]
            )
            sourcearguments["facility"] = facility

        if "activitycode1" in psvals:
            ac = ActivityCode.objects.filter(code_set=self.codeset).get(
                code=psvals["activitycode1"]
            )
            sourcearguments["activitycode1"] = ac

        for argname in self.possible_attributes:
            try:
                sourcearguments[argname] = psvals[argname]
            except KeyError:
                pass
        if "unique_source" in psvals:
            if psvals["unique_source"] in self.psdict:
                self.psdict[psvals["unique_source"]]["substvals"].update(substvals)
            else:
                source = self.sourcemodel(**sourcearguments)
                self.psdict[psvals["unique_source"]] = {
                    "source": source,
                    "psvals": psvals,
                    "substvals": substvals,
                }
        else:
            source = self.sourcemodel(**sourcearguments)
            self.psdict[len(self.psdict)] = {
                "source": source,
                "psvals": psvals,
                "substvals": substvals,
            }

    def get_ps_vals(self, feature):
        psvals = dict()
        if "parameters" in self.config:
            for parName, par in self.config["parameters"].items():
                if par is not None:
                    val = feature.get(par)
                psvals[parName] = get_parameter_value(val, parName, self.config)
        if "defaults" in self.config:
            for parName, value in self.config["defaults"].items():
                if (
                    parName not in psvals
                    or psvals[parName] is None
                    or np.isnan(psvals[parName])
                ):
                    psvals[parName] = value
        return psvals

    def get_subst_vals(self, feature):
        substvals = dict()
        for substance in self.substdict.keys():
            substvals.update(self.get_subst_vals_attribute(feature, substance))
        return substvals

    def get_subst_vals_attribute(self, feature, substance):
        emission = feature.get(self.substdict[substance]["emission"])
        try:
            unit = feature.get(self.substdict[substance]["unit"])
        except KeyError:
            unit = self.substdict[substance]["unitval"]
        try:
            unitmap = self.config["mappings"]["unit"]
            for ustr, ulist in unitmap.items():
                if unit in ulist:
                    unit = ustr
                    break
        except KeyError:
            pass

        return {self.substdict[substance]["substance"]: (emission, unit)}


def get_timevar(psval, config, timevars):
    try:
        return timevars[config["timevar"]]
    except KeyError:
        pass

    try:
        tvp = config["parameters"]["timevar"]
    except KeyError:
        return timevars["STANDARD"]

    if "timevarmapping" in config:
        for tv, params in config["mappings"]["timevar"].items():
            if psval["timevar"] in params:
                return timevars[tv]
    else:
        return timevars[tvp]
    return timevars["STANDARD"]


class Skip(Exception):
    pass


def get_parameter_value(parametervalue, parametername, config):
    if "mappings" in config and parametername in config["mappings"]:
        for mapname, params in config["mappings"][parametername].items():
            if parametervalue in params:
                mappedvalue = mapname
                break
        if "mappedvalue" not in locals():
            try:
                mappedvalue = config["mappings"]["defaults"][parametername]
            except KeyError:
                if (
                    "skipmissing" in config["mappings"]
                    and parametername in config["mappings"]["skipmissing"]
                ):
                    raise Skip()
                else:
                    raise TranslationFileError(
                        f"{parametername} has a mapping in config "
                        f"but {parametervalue} is not mapped and have no default value"
                    )
    else:
        mappedvalue = parametervalue

    return mappedvalue
