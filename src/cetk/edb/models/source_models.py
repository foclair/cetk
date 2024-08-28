"""Emission database models."""


from django.contrib.gis.db import models

from cetk.edb.const import CHAR_FIELD_LENGTH, WGS84_SRID
from cetk.edb.ltreefield import LtreeField
from cetk.edb.models.base import BaseNamedModel, NaturalKeyManager

SRID = WGS84_SRID


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


def default_vertical_dist():
    return "[[5.0, 1.0]]"


class VerticalDist(BaseNamedModel):
    """Vertical distribution of GridSource emissions."""

    objects = NaturalKeyManager()

    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=64, unique=True)
    weights = models.CharField(
        max_length=CHAR_FIELD_LENGTH, default=default_vertical_dist
    )

    class Meta:
        db_table = "vertical_distributions"
        default_related_name = "vertical_distributions"

    natural_key_fields = "slug"

    def natural_key(self):
        return self.slug

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
    slug = models.SlugField(max_length=64, unique=True)
    description = models.CharField(
        verbose_name="description", max_length=200, null=True, blank=True
    )

    class Meta:
        db_table = "codesets"
        default_related_name = "codesets"

    natural_key_fields = "slug"

    def natural_key(self):
        return self.slug

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
    natural_key_fields = ("code_set__slug", "code")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code_set", "code"], name="unique code in codeset"
            )
        ]

    def natural_key(self):
        return (self.code_set.slug, self.code)

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
        indexes = [
            models.Index(
                fields=("activitycode1", "activitycode2", "activitycode3"),
                name="%(class)s_activities_idx",
            ),
        ]


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


class SourceActivity(models.Model):
    """Base class for an emitting activity."""

    rate = models.FloatField(verbose_name="activity rate")
    activity = models.ForeignKey("Activity", on_delete=models.PROTECT, related_name="+")

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=("source", "activity"),
                name="%(class)s_unique_activity_in_source",
            ),
        ]
        default_related_name = "activities"


class PointSourceActivity(SourceActivity):
    """An emitting activity of a point source."""

    source = models.ForeignKey("PointSource", on_delete=models.CASCADE)

    def __str__(self):
        return "{}".format(self.activity.name)


class EmissionFactor(models.Model):
    """An emission factor."""

    factor = models.FloatField(default=0)
    activity = models.ForeignKey("Activity", on_delete=models.PROTECT)
    substance = models.ForeignKey(
        "Substance", on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("activity", "substance"),
                name="emissionfactor_activity_substance_unique_together",
            ),
        ]
        default_related_name = "emissionfactors"


class AreaSource(PointAreaGridSourceBase):
    """An area source."""

    sourcetype = "area"

    geom = models.PolygonField(
        "the extent of the area source", srid=WGS84_SRID, geography=True, db_index=True
    )
    facility = models.ForeignKey(
        "Facility", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta(PointAreaGridSourceBase.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=("facility", "name"),
                name="areasource_unique_facility_and_name",
            ),
        ]
        default_related_name = "areasources"


class AreaSourceActivity(SourceActivity):
    """An emitting activity of an area source."""

    source = models.ForeignKey("AreaSource", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.activity.name}"


class AreaSourceSubstance(SourceSubstance):
    """An area-source substance emission."""

    source = models.ForeignKey("AreaSource", on_delete=models.CASCADE)
