from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
from django.utils.translation import gettext_lazy as _

from etk.edb.const import WGS84_SRID
from etk.edb.models.source_models import CodeSet


class SettingsManager(models.Manager):
    # makes sure always just one instance of settings exists
    def get_queryset(self):
        return super().get_queryset()[:1]


DEFAULT_EXTENT = "Polygon((-25.0 35.0, -25.0 70.0, 40.0 70.0, 40.0 35.0, -25.0 35.0))"


class Settings(models.Model):
    """Inventory specific database settings, replaces gadgets Domain and Inventory."""

    srid = models.IntegerField(
        _("SRID"), help_text=_("Spatial reference system identifier")
    )
    extent = models.PolygonField(_("extent"), geography=True)

    # TODO dangerous, also defined in etk.settings.TIME_ZONE! Fix that only on def.
    timezone = models.CharField(_("timezone"), max_length=64)

    # some functionality in Gadget only works for one out of the three codesets.
    codeset1 = models.ForeignKey(
        CodeSet, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    codeset2 = models.ForeignKey(
        CodeSet, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    codeset3 = models.ForeignKey(
        CodeSet, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    objects = SettingsManager()

    class Meta:
        db_table = "settings"
        default_related_name = "settings"

    def get_current():
        # Retrieve the settings, if exist
        return Settings.objects.get_or_create(
            defaults={
                "srid": 3857,
                "timezone": "Europe/Stockholm",
                "extent": GEOSGeometry(DEFAULT_EXTENT, WGS84_SRID),
                "codeset1": CodeSet.objects.filter(id=1).first(),
                "codeset2": CodeSet.objects.filter(id=2).first(),
                "codeset3": CodeSet.objects.filter(id=3).first(),
            }
        )[0]

    def get_codeset_index(self, codeset):
        """Return index of a specific codeset."""
        if type(codeset) == str:
            codeset_slug = codeset
        elif type(codeset) == CodeSet:
            codeset_slug = codeset.slug
        else:
            raise ValueError(f"codeset '{codeset}' is not of valid type")
        # if self.codeset1 is not None:
        #     if codeset_slug == self.codeset1.slug:
        #         return 1
        # if self.codeset2 is not None:
        #     if codeset_slug == self.codeset2.slug:
        #         return 2
        # if self.codeset3 is not None:
        #     if codeset_slug == self.codeset3.slug:
        #         return 3
        if len(CodeSet.objects.filter(slug=codeset_slug)) > 0:
            return CodeSet.objects.filter(slug=codeset_slug).first().id
        else:
            raise ValueError(f"codeset '{codeset}' not found in inventory settings")
