from itertools import islice

import numpy as np
import pandas as pd

from etk.edb.cache import cache_queryset
from etk.edb.models import Settings


class ImportError(Exception):
    """Error while importing emission data."""

    pass


def nan2None(d):
    out = d.copy()
    for k, val in out.items():
        out[k] = val if pd.notna(k) else val
    return out


def import_error(message, return_message="", validation=False):
    """import error management"""
    if not validation:
        raise ImportError(message)
    else:
        return_message += message + "\n"
    return return_message


def import_row_error(msg, row_nr, validation=False):
    """import error managment with row nr"""
    return import_error(f"{msg}, on row {row_nr}", validation=validation)


def import_row_substance_error(msg, row_nr, substance, validation=False):
    """import error managment with row nr"""
    return import_error(
        f"{msg}, for '{substance}' on row {row_nr}", validation=validation
    )


def cache_codeset(code_set):
    """return dict {code: activitycode} for codeset."""
    if code_set is None:
        return {}
    return cache_queryset(code_set.codes.all(), "code")


def cache_codesets():
    """
    return list of dictionaries with activity-codes
    for all code-sets in Settings.
    """
    settings = Settings.get_current()
    code_sets = {}
    if settings.codeset1 is not None:
        code_sets[settings.codeset1.slug] = cache_codeset(settings.codeset1)
    if settings.codeset2 is not None:
        code_sets[settings.codeset2.slug] = cache_codeset(settings.codeset2)
    if settings.codeset3 is not None:
        code_sets[settings.codeset3.slug] = cache_codeset(settings.codeset3)
    return code_sets


def worksheet_to_dataframe(data):
    cols = next(data)
    data = list(data)
    data = (islice(r, 0, None) for r in data)
    df = pd.DataFrame(data, columns=cols)
    # remove empty rows
    empty_count = 0
    for ind in range(-1, -1 * (len(df) + 1), -1):
        if all([pd.isnull(val) for val in df.iloc[ind]]):
            empty_count += 1
        else:
            break
    # remove the last 'empty_count' lines
    df = df.head(df.shape[0] - empty_count)
    # remove empty columns without label
    if None in df.columns:
        if np.all([pd.isnull(val) for val in df[None].values]):
            df = df.drop(columns=[None])
    return df


def get_substance_emission_columns(df):
    """return columns with substance emissions."""
    return [col for col in df.columns if col.startswith("subst:")]


def get_activity_rate_columns(df):
    """return columns with activity rates."""
    return [col for col in df.columns if col.startswith("act:")]
