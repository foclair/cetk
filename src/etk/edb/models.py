"""Emission database models."""

# import numpy as np
from django.conf import settings
from django.contrib.gis.db import models
# eller
# from django.db import models, but maybe geodjango models api inherits normal django api? 
# https://docs.djangoproject.com/en/4.2/ref/models/
# https://docs.djangoproject.com/en/4.2/ref/contrib/gis/model-api/

from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from etk.edb.const import CHAR_FIELD_LENGTH, WGS84_SRID
from etk.edb.copy import copy_codeset, copy_model_instance
from etk.edb.ltreefield import LtreeField

#TODO is a locid necessary when starting inventories from scratch, instead of importing existing gadget databases?
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
    #TODO ArrayField in Gadget, need for compatability, how to convert? 
    #ArrayField not supported in SQLite
    weights = models.CharField(max_length=CHAR_FIELD_LENGTH, default=default_vertical_dist)

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
            code__match=".".join(self.code.split(".")[:-1]) + ".*{1}",
            code_set=self.code_set,
        )
    def get_siblings(self):
        return self.get_siblings_and_self().exclude(pk=self.pk)
    def get_children(self):
        return self.code_set.codes.filter(code__match=self.code + ".*{1}")
    def is_leaf(self):
        """Return True if code is a leaf (i.e. has no sub-codes)."""
        return not self.get_decendents().exists()