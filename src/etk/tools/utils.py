"""Utility functions for emission processing."""

# from django.contrib.gis.gdal import GDALRaster


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


def cache_codeset(code_set):
    if code_set is None:
        return {}
    return cache_queryset(code_set.codes.all(), "code")
