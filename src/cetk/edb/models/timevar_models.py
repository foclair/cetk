import ast

import numpy as np
import pandas as pd
from django.contrib.gis.db import models

from cetk.edb.const import CHAR_FIELD_LENGTH
from cetk.edb.models.common_models import Settings


def default_timevar_typeday():
    return str(24 * [7 * [100.0]])


def default_timevar_month():
    return str(12 * [100.0])


def get_normalization_constant(typeday, month, timezone):
    commonyear = pd.date_range("2018", periods=24 * 365, freq="h", tz=timezone)
    values = typeday[commonyear.hour, commonyear.weekday] * month[commonyear.month - 1]
    return len(values) / values.sum()


def timevar_to_series(time_index, *timevars, timezone=None):
    """Produce normalized time series from one or more timevar instances."""
    if not timevars:
        raise TypeError("at least one timevar must be given")
    if timezone is None:
        timezone = Settings.get_current().timezone
    typeday = np.multiply.reduce([ast.literal_eval(t.typeday) for t in timevars])
    month = np.multiply.reduce([ast.literal_eval(t.month) for t in timevars])
    if len(timevars) > 1:
        normalization_constant = get_normalization_constant(typeday, month, timezone)
    else:
        normalization_constant = timevars[0].normalization_constant

    local_time_index = time_index.tz_convert(timezone)
    values = (
        typeday[local_time_index.hour, local_time_index.weekday]
        * month[local_time_index.month - 1]
    )
    return pd.Series(normalization_constant * values, index=time_index)


def timevar_normalize(timevar, timezone=None):
    """Set the normalization constants on a timevar instance."""
    if timezone is None:
        timezone = Settings.get_current().timezone
    typeday = np.array(ast.literal_eval(timevar.typeday))
    month = np.array(ast.literal_eval(timevar.month))
    timevar.typeday_sum = typeday.sum()
    timevar._normalization_constant = get_normalization_constant(
        typeday, month, timezone
    )
    return timevar


class TimevarBase(models.Model):
    name = models.CharField(max_length=CHAR_FIELD_LENGTH, unique=True)

    typeday = models.CharField(
        max_length=10 * len(default_timevar_typeday()),
        default=default_timevar_typeday(),
    )
    month = models.CharField(
        max_length=10 * len(default_timevar_month()), default=default_timevar_month()
    )

    # pre-calculated normalization constants
    typeday_sum = models.FloatField(editable=False)
    _normalization_constant = models.FloatField(editable=False)

    class Meta:
        abstract = True

    def __str__(self):
        """Return a unicode representation of this timevariation."""
        return self.name

    @property
    def normalization_constant(self):
        if self._normalization_constant is None:
            timevar_normalize(self)
        return self._normalization_constant

    def save(self, *args, **kwargs):
        """Overloads save to ensure normalizing factors are calculated."""
        timevar_normalize(self)
        super(TimevarBase, self).save(*args, **kwargs)


class Timevar(TimevarBase):
    """A source time-variation profile."""

    class Meta(TimevarBase.Meta):
        default_related_name = "timevars"


class FlowTimevar(TimevarBase):
    """A road time-variation profile."""

    class Meta(TimevarBase.Meta):
        default_related_name = "flow_timevars"


class ColdstartTimevar(TimevarBase):
    """A vehicle cold start time-variation profile."""

    class Meta(TimevarBase.Meta):
        default_related_name = "coldstart_timevars"
