import pandas as pd

from cetk.edb.cache import cache_queryset
from cetk.edb.models import Settings


class ValidationError(Exception):
    """Error while validating emission data."""

    pass


class EmptySheet(Exception):
    """Error trying to read data from an empty sheet."""

    pass


def nan2None(d):
    out = d.copy()
    for k, val in out.items():
        out[k] = val if pd.notna(k) else val
    return out


def import_error(message, return_message="", validation=False):
    """import error management"""
    if not validation:
        raise ValidationError(f"VALIDATION: {message}")
    else:
        return_message += f"VALIDATION: {message}\n"
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
    data = list(data)
    if not data:
        raise EmptySheet("Sheet is empty")
    df = pd.DataFrame(data)
    # Set the first row as the header
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    # Remove completely empty rows
    df = df.dropna(how="all")
    # Remove completely empty columns without a header
    df = df.loc[:, ~(df.isna().all() & df.columns.isna())]
    return df


def get_substance_emission_columns(df):
    """return columns with substance emissions."""
    return [col for col in df.columns if col.startswith("subst:")]


def get_activity_rate_columns(df):
    """return columns with activity rates."""
    return [col for col in df.columns if col.startswith("act:")]
