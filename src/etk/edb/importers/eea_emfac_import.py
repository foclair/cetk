import logging

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from etk.edb.cache import cache_queryset
from etk.edb.models import Substance
from etk.edb.models.eea_emfacs import EEAEmissionFactor

from .utils import worksheet_to_dataframe

log = logging.getLogger(__name__)


def import_eea_emfacs(filepath, encoding=None):
    """Import point-sources from xlsx or csv-file.

    args
        filepath: path to file

    options
        encoding: encoding of file (default is utf-8)
    """
    existing_eea_emfacs = EEAEmissionFactor.objects.all()
    if len(existing_eea_emfacs) > 1:
        log.debug("emfacs have previously been imported")
        log.debug("for now delete all previous emfacs")
        # TODO if automatically linking EEA emfacs to applied emfacs,
        # then cannot remove but can only update, to avoid removing
        # an emfac which is used for a certain activity.
        existing_eea_emfacs.delete()

    substances = cache_queryset(Substance.objects.all(), "slug")

    extension = filepath.suffix
    if extension == ".csv":
        # read csv-file
        print("Warning, this is not as much tested as xlsx!")
        with open(filepath, encoding=encoding or "utf-8") as csvfile:
            log.debug("reading point-sources from csv-file")
            df = pd.read_csv(
                csvfile,
                sep=";",
                skip_blank_lines=True,
                comment="#",
            )
    elif extension == ".xlsx":
        # read spreadsheet
        try:
            workbook = load_workbook(filename=filepath)
        except Exception as exc:
            raise ImportError(str(exc))
        worksheet = workbook.worksheets[0]
        if len(workbook.worksheets) > 1:
            log.debug("debug: multiple sheets in spreadsheet, only importing 1st.")
        data = worksheet.values
        df = worksheet_to_dataframe(data)
        # TODO could replace NA by None?
        # df = df.replace(to_replace="NA", value=None)
    else:
        raise ImportError("Only xlsx and csv files are supported for import")

    row_nr = 2
    no_value_count = 0
    no_unit_count = 0
    create_eea_emfac = []
    for row_key, row in df.iterrows():
        emfac_data = {}
        row_dict = row.to_dict()
        for attr, key in {
            "nfr_code": "NFR",
            "sector": "Sector",
            "table": "Table",
            "tier": "Type",
            "technology": "Technology",
            "fuel": "Fuel",
            "abatement": "Abatement",
            "region": "Region",
            "substance": "Pollutant",
            "value": "Value",
            "unit": "Unit",
            "lower": "CI_lower",
            "upper": "CI_upper",
            "reference": "Reference",
        }.items():
            emfac_data[attr] = row_dict[key]
        # check if substance known
        try:
            subst = emfac_data["substance"]
        except KeyError:
            print(f"No pollutant given, ignoring row {row_nr}")
            row_nr += 1
            no_value_count += 1
            continue
        try:
            emfac_data["substance"] = substances[subst]
        except KeyError:
            if subst == "PM2.5":
                emfac_data["substance"] = substances["PM25"]
            else:
                # TODO log warning
                # many undefined substances in EEA so dont want to raise import warning
                print(f"Undefined substance {subst}")
                print("Saving pollutant as unknown_substance.")
                emfac_data["unknown_substance"] = subst
                emfac_data["substance"] = None
        if row_dict["Value"] is None:
            if (row_dict["CI_lower"] is None) and (row_dict["CI_upper"] is None):
                # TODO log warning
                print(f"No emission factor given, ignoring row {row_nr}")
                row_nr += 1
                no_value_count += 1
                continue
            else:
                # taking mean if both upper and lower not nan, if only one not nan,
                # take that value.
                emfac_data["value"] = np.nanmean(
                    np.array(
                        [row_dict["CI_lower"], row_dict["CI_upper"]], dtype=np.float64
                    )
                )
        if emfac_data["unit"] is None:
            # TODO log warning
            print(f"No unit given, ignoring row {row_nr}")
            row_nr += 1
            no_unit_count += 1
            continue
        # set data in EEA emfac data model
        try:
            float(emfac_data["value"])
        except ValueError:
            print(f"Non numerical value, ignoring row {row_nr}")
            row_nr += 1
            no_value_count += 1
            continue
        eea_emfac = EEAEmissionFactor()
        for key, val in emfac_data.items():
            setattr(eea_emfac, key, val)
        if not pd.isnull(eea_emfac.value):
            create_eea_emfac.append(eea_emfac)
        row_nr += 1

    EEAEmissionFactor.objects.bulk_create(create_eea_emfac)
    # TODO check for existing emfac and do not create twice, or only update
    # a bit challenging since database itself has duplicates.
    return_dict = {}
    return_dict["eea_emfacs_created"] = len(create_eea_emfac)
    return return_dict


# hardcode eea tables or read from import file?
EEA_Tables = {
    "coal_fplace": {"table": "3-12", "NFR": "1.A.4.b.i"},
    "coal_stove": {"table": "3-14", "NFR": "1.A.4.b.i"},
    "coal_shb_m": {"table": "3-15", "NFR": "1.A.4.b.i"},
    "coal_shb_a": {"table": "3-19", "NFR": "1.A.4.b.i"},
    "coal_mb_m": {"table": "3-22", "NFR": "1.A.4.a.i"},
    "coal_mb_a": {"table": "3-21", "NFR": "1.A.4.a.i"},
    "oil_stove": {"table": "3-17", "NFR": "1.A.4.b.i"},
    "oil_shb_m": {"table": "3-18", "NFR": "1.A.4.b.i"},
    "oil_mb_m": {"table": "3-24", "NFR": "1.A.4.a.i"},
    "oil_mb_a": {"table": "3-25", "NFR": "1.A.4.a.i"},
    "natural_gas_stove": {"table": "3-13", "NFR": "1.A.4.b.i"},
    "natural_gas_shb_m": {"table": "3-16", "NFR": "1.A.4.b.i"},
    "natural_gas_mb_m": {"table": "3-26", "NFR": "1.A.4.a.i"},
    "natural_gas_mb_a": {"table": "3-27", "NFR": "1.A.4.a.i"},
    "wood_stove": {"table": "3-40", "NFR": "1.A.4.b.i"},
    "wood_shb_a": {"table": "3-44", "NFR": "1.A.4.b.i"},
    "wood_shb_m": {"table": "3-43", "NFR": "1.A.4.b.i"},
    "wood_fplace": {"table": "3-39", "NFR": "1.A.4.b.i"},
    "wood_mb_a": {"table": "3-45", "NFR": "1.A.4.a.i"},
    "wood_mb_m": {"table": "3-47", "NFR": "1.A.4.a.i"},
    "pellets_shb_a": {"table": "3-44", "NFR": "1.A.4.b.i"},
}

# lpg not specifically in eea, taken as natural_gas
# wood residue taken as wood, but appliance distributions may vary between
# wood & wood residue, or lpg and natural_gas.
eea_fuels = ["coal", "oil", "natural_gas", "wood", "pellets", "lpg", "wood_residue"]
eea_appliances = ["fplace", "stove", "shb_a", "shb_m", "mb_a", "mb_m"]

# combinations of fuel and appliance not in EEA
excluded_combinations = [
    ("oil", "fplace"),
    ("oil", "shb_a"),
    ("natural_gas", "fplace"),
    ("natural_gas", "shb_a"),
    ("pellets", "fplace"),
    ("pellets", "stove"),
    ("pellets", "shb_m"),
    ("pellets", "mb_a"),
    ("pellets", "mb_m"),
]
