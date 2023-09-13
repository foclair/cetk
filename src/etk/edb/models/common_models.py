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
            }
        )[0]

    def get_codeset_index(self, codeset):
        """Return index of a specific codeset."""
        if codeset == self.codeset1:
            return 1
        elif codeset == self.codeset2:
            return 2
        elif codeset == self.codeset3:
            return 3
        else:
            raise ValueError(
                f"codeset '{codeset.slug}' not found in inventory settings"
            )
