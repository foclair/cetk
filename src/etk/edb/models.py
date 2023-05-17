"""Emission database models."""

import ast
import datetime

import numpy as np
import pandas as pd
import pytz

# from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

# from django.db.models import Sum
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from etk.edb.const import CHAR_FIELD_LENGTH, WGS84_SRID
from etk.edb.copy import copy_codeset, copy_model_instance
from etk.edb.ltreefield import LtreeField
from etk.settings import TIME_ZONE

# eller
# from django.db import models, but maybe geodjango models api
# inherits normal django api?
# https://docs.djangoproject.com/en/4.2/ref/models/
# https://docs.djangoproject.com/en/4.2/ref/contrib/gis/model-api/


# TODO is a locid necessary when starting inventories from scratch, instead of importing
# existing gadget databases?
# locid = models.AutoField(primary_key=True, auto_created=True, editable=False)

SRID = WGS84_SRID


class BaseNamedModel(models.Model):
    """Base class for models with a name and a slug field."""

    class Meta:
        abstract = True

    def clean(self):
        if not self.slug and self.name:
            self.slug = slugify(self.name)

    def __str__(self):
        return self.name


class NamedModelManager(models.Manager):
    """Database manager for named models."""

    def get_by_natural_key(self, slug):
        """Return a model instance given its slug."""
        return self.get(slug=slug)


class NaturalKeyManager(models.Manager):

    """Database manager for models with natural key."""

    def get_by_natural_key(self, *key):
        """Return a model instance given its natural key."""
        return self.get(**dict(zip(self.model.natural_key_fields, key)))


class NamedModel(BaseNamedModel):
    """A model with a unique name and slug."""

    name = models.CharField(_("name"), max_length=64, unique=True)
    slug = models.SlugField(_("slug"), max_length=64, unique=True)

    objects = NamedModelManager()

    class Meta:
        abstract = True

    def natural_key(self):
        """Return the natural key (the slug) for this model instance."""
        return (self.slug,)


class Substance(NamedModel):
    """A chemical substance."""

    long_name = models.CharField(_("long name"), max_length=64)

    class Meta:
        db_table = "substances"
        default_related_name = "substances"


class Parameter(NamedModel):
    """A parameter."""

    quantity = models.CharField(_("physical quantity"), max_length=30)
    substance = models.ForeignKey(
        Substance, on_delete=models.CASCADE, null=True, verbose_name=_("substance")
    )

    class Meta:
        db_table = "parameters"
        default_related_name = "parameters"

    def validate_unique(self, *args, **kwargs):
        """Avoid duplicate emission or conc. parameters for a substance."""
        super().validate_unique(*args, **kwargs)
        if self.quantity in ("emission", "concentration"):
            duplicates = type(self).objects.filter(
                quantity=self.quantity, substance=self.substance
            )
            if duplicates.exists():
                raise ValidationError(
                    {
                        NON_FIELD_ERRORS: [
                            f"A parameter for {self.quantity} of {self.substance} "
                            f"already exist"
                        ]
                    }
                )

    def _auto_name(self):
        """Auto-generate a name."""
        quantity = self.quantity.capitalize()
        if self.substance is not None:
            self.name = f"{quantity} {self.substance.name}"
        else:
            self.name = quantity

    def _auto_slug(self):
        """Auto-generate a slug."""
        if self.substance is not None:
            quantity = slugify(self.quantity)
            self.slug = f"{quantity}_{self.substance.slug}"
        else:
            self.slug = slugify(self.name)

    def save(self, *args, **kwargs):
        """Overloads save to auto-generate name and slug if missing."""
        if self.name is None:
            self._auto_name()
        if self.slug is None:
            self._auto_slug()
        super().save(*args, **kwargs)


class SourceSubstance(models.Model):
    """An abstract models for source substance emissions."""

    value = models.FloatField(default=0, verbose_name="source emission")
    substance = models.ForeignKey(
        "Substance", on_delete=models.PROTECT, related_name="+"
    )
    updated = models.DateTimeField(verbose_name="date of last update", auto_now=True)

    class Meta:
        abstract = True
        default_related_name = "substances"
        unique_together = ("source", "substance")

    def __str__(self):
        return self.substance.name


class Domain(NamedModel):
    """A spatial domain."""

    srid = models.IntegerField(
        _("SRID"), help_text=_("Spatial reference system identifier")
    )
    extent = models.MultiPolygonField(_("extent"), geography=True)
    timezone = models.CharField(_("timezone"), max_length=64)
    # users = models.ManyToManyField(settings.AUTH_USER_MODEL, verbose_name=_("users"))

    class Meta:
        db_table = "domains"
        default_related_name = "domains"

    @property
    def utc_offset(self):
        tz = pytz.timezone(self.timezone)
        offset_1jan = tz.utcoffset(datetime.datetime(2012, 1, 1))
        offset_1jul = tz.utcoffset(datetime.datetime(2012, 7, 1))
        dst_jan = tz.dst(datetime.datetime(2012, 1, 1))
        return offset_1jan if dst_jan == datetime.timedelta(0) else offset_1jul


def default_vertical_dist():
    return "[[5.0, 1.0]]"


class VerticalDist(BaseNamedModel):
    """Vertical distribution of GridSource emissions."""

    objects = NaturalKeyManager()

    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=64)
    domain = models.ForeignKey(
        "Domain", on_delete=models.CASCADE, related_name="vertical_dists"
    )
    # TODO ArrayField in Gadget, need for compatability, how to convert?
    # ArrayField not supported in SQLite
    weights = models.CharField(
        max_length=CHAR_FIELD_LENGTH, default=default_vertical_dist
    )

    class Meta:
        unique_together = (("domain", "name"), ("domain", "slug"))

    natural_key_fields = ("domain__slug", "slug")

    def natural_key(self):
        return (self.domain.slug, self.slug)

    def __str__(self):
        return self.name


class Activity(models.Model):
    """An emitting activity."""

    name = models.CharField(
        verbose_name="name of activity", max_length=CHAR_FIELD_LENGTH, unique=True
    )
    unit = models.CharField(
        verbose_name="unit of activity", max_length=CHAR_FIELD_LENGTH
    )

    class Meta:
        default_related_name = "activities"

    def __str__(self):
        """Return a unicode representation of this activity."""
        return self.name


class CodeSet(BaseNamedModel):
    """A set of activity codes."""

    objects = NaturalKeyManager()

    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=64)
    domain = models.ForeignKey(
        "Domain", on_delete=models.CASCADE, related_name="code_sets"
    )
    description = models.CharField(
        verbose_name="description", max_length=200, null=True, blank=True
    )

    class Meta:
        unique_together = (("domain", "name"), ("domain", "slug"))

    natural_key_fields = ("domain__slug", "slug")

    def natural_key(self):
        return (self.domain.slug, self.slug)

    def copy(self, domain=None, **updated_fields):
        """Create a copy of the CodeSet in another domain."""

        if domain is not None:
            updated_fields["domain"] = domain

        copy = copy_model_instance(self, **updated_fields)
        copy_codeset(self, copy)
        return copy

    def __str__(self):
        return self.name


class ActivityCode(models.Model):
    """An abstract model for an activity code."""

    objects = NaturalKeyManager()
    code = LtreeField(verbose_name="activity code")
    label = models.CharField(verbose_name="activity code label", max_length=100)
    code_set = models.ForeignKey(
        CodeSet, on_delete=models.CASCADE, related_name="codes"
    )
    vertical_dist = models.ForeignKey(
        VerticalDist, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    natural_key_fields = ("code_set__domain__slug", "code_set__slug", "code")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code_set", "code"], name="unique code in codeset"
            )
        ]

    def natural_key(self):
        return (self.code_set.domain.slug, self.code_set.slug, self.code)

    def __lt__(self, other):
        return self.code < other.code

    def __str__(self):
        """Return a unicode representation of this activity code."""
        return self.code

    def matches(self, filters):
        """Compare with a (list of) filter code(s).
        args
        filters: list of accepted codes
        Filters should be '.'-separated codes
        comparison is only made for code levels included in filter
        i.e. the code 1.A.2.i will match the filter 1.A
        """
        code_parts = self.code.split(".")
        for f in filters:
            matches = True
            filter_parts = f.code.split(".")
            # filter has more code-parts than code
            if len(filter_parts) > len(code_parts):
                matches = False
                continue
            # compare code with filter part by part
            for i, filter_part in enumerate(filter_parts):
                if filter_part != code_parts[i]:
                    matches = False
                    break
            if matches:
                return matches
        return matches

    def get_decendents(self):
        return self.get_decendents_and_self().exclude(pk=self.pk)

    def get_decendents_and_self(self):
        return ActivityCode.objects.filter(code__dore=self.code).filter(
            code_set=self.code_set
        )

    def get_ancestors(self):
        return self.get_ancestors_and_self().exclude(pk=self.pk)

    def get_ancestors_and_self(self):
        return ActivityCode.objects.filter(code__aore=self.code).filter(
            code_set=self.code_set
        )

    def get_parent(self):
        if "." not in self.code:
            raise RuntimeError(
                f"The code: {self} cannot have a parent as it is a root node"
            )
        return ActivityCode.objects.get(
            code__match=".".join(self.code.split(".")[:-1]), code_set=self.code_set
        )

    def get_siblings_and_self(self):
        return ActivityCode.objects.filter(
            code__match=".".join(self.code.split(".")[:-1]) + "._",
            code_set=self.code_set,
        )

    def get_siblings(self):
        return self.get_siblings_and_self().exclude(pk=self.pk)

    def get_children(self):
        return self.code_set.codes.filter(code__match=self.code + "._")

    def is_leaf(self):
        """Return True if code is a leaf (i.e. has no sub-codes)."""
        return not self.get_decendents().exists()


def default_timevar_typeday():
    return str(24 * [7 * [100.0]])


def default_timevar_month():
    return str(12 * [100.0])


def get_normalization_constant(typeday, month, timezone):
    commonyear = pd.date_range("2018", periods=24 * 365, freq="H", tz=timezone)
    values = typeday[commonyear.hour, commonyear.weekday] * month[commonyear.month - 1]
    return len(values) / values.sum()


def normalize(timevar, timezone=None):
    """Set the normalization constants on a timevar instance."""
    if timezone is None:
        timezone = TIME_ZONE
    typeday = np.array(ast.literal_eval(timevar.typeday))
    month = np.array(ast.literal_eval(timevar.month))
    timevar.typeday_sum = typeday.sum()
    timevar._normalization_constant = get_normalization_constant(
        typeday, month, timezone
    )
    return timevar


class TimevarBase(models.Model):
    name = models.CharField(max_length=CHAR_FIELD_LENGTH, unique=True)
    # same domain for all data
    # domain = models.ForeignKey("Domain", on_delete=models.CASCADE)

    # typeday should be a 2d-field with hours as rows and weekdays as columns
    # ArrayField not supported in SQLite
    typeday = models.CharField(
        max_length=10 * len(default_timevar_typeday()),
        default=default_timevar_typeday(),
    )
    # month should be a 1d field with 12 values
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
            normalize(self)
        return self._normalization_constant

    def save(self, *args, **kwargs):
        """Overloads save to ensure normalizing factors are calculated."""
        normalize(self)
        super(TimevarBase, self).save(*args, **kwargs)


class Timevar(TimevarBase):
    """A source time-variation profile."""

    class Meta(TimevarBase.Meta):
        default_related_name = "timevars"


class SourceBase(models.Model):
    """Abstract base model for an emission source."""

    name = models.CharField("name", max_length=CHAR_FIELD_LENGTH, blank=False)
    created = models.DateTimeField(verbose_name="time of creation", auto_now_add=True)
    updated = models.DateTimeField(verbose_name="time of last update", auto_now=True)
    # TODO: do such tags work for Spatialite? Best to keep for CLAIR compatability?
    tags = models.JSONField(
        verbose_name="user-defined key-value pairs", blank=True, null=True
    )

    class Meta:
        abstract = True

    def __str__(self):
        """Return a unicode representation of this source."""
        return self.name


class PointAreaGridSourceBase(SourceBase):
    """Abstract base model for point, area and grid sources"""

    timevar = models.ForeignKey(
        "Timevar", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    activitycode1 = models.ForeignKey(
        "ActivityCode",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    activitycode2 = models.ForeignKey(
        "ActivityCode",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    activitycode3 = models.ForeignKey(
        "ActivityCode",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True
        index_together = ["activitycode1", "activitycode2", "activitycode3"]


class Facility(SourceBase):
    """A facility."""

    official_id = models.CharField(
        "official_id",
        max_length=CHAR_FIELD_LENGTH,
        blank=False,
        db_index=True,
        unique=True,
    )

    class Meta:
        default_related_name = "facilities"
        # unique_together = (("inventory", "official_id"), ("inventory", "name"))
        # TODO not sure if the unique = true in official id is sufficient
        # to replace line above?

    def __str__(self):
        return str(self.official_id)

    def __repr__(self):
        return str(self)


class PointSource(PointAreaGridSourceBase):
    """A point-source."""

    sourcetype = "point"

    chimney_height = models.FloatField("chimney height [m]", default=0)
    chimney_outer_diameter = models.FloatField(
        "chimney outer diameter [m]", default=1.0
    )
    chimney_inner_diameter = models.FloatField(
        "chimney inner diameter [m]", default=0.9
    )
    chimney_gas_speed = models.FloatField("chimney gas speed [m/s]", default=1.0)
    chimney_gas_temperature = models.FloatField(
        "chimney gas temperature [K]", default=373.0
    )
    house_width = models.IntegerField(
        "house width [m] (to estimate down draft)", default=0
    )
    house_height = models.IntegerField(
        "house height [m] (to estimate down draft)", default=0
    )
    geom = models.PointField(
        "the position of the point-source",
        srid=WGS84_SRID,
        geography=True,
        db_index=True,
    )
    facility = models.ForeignKey(
        "Facility", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta(PointAreaGridSourceBase.Meta):
        default_related_name = "pointsources"
        unique_together = ("facility", "name")


class PointSourceSubstance(SourceSubstance):
    """A point-source substance emission."""

    source = models.ForeignKey("PointSource", on_delete=models.CASCADE)
