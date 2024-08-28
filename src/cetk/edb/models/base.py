"""Abstract base models for cetk."""

from django.contrib.gis.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


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
