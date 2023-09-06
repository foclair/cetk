from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _

from etk.edb.models.source_models import CodeSet


class SettingsManager(models.Manager):
    # makes sure always just one instance of settings exists
    def get_queryset(self):
        return super().get_queryset()[:1]


class Settings(models.Model):
    """Inventory specific database settings, replaces gadgets Domain and Inventory."""

    srid = models.IntegerField(
        _("SRID"), help_text=_("Spatial reference system identifier")
    )
    extent = models.PolygonField(_("extent"), geography=True)
    timezone = models.CharField(_("timezone"), max_length=64)

    # some functionality in Gadget only works for one out of the three codesets.
    primary_codeset = models.ForeignKey(
        CodeSet, on_delete=models.CASCADE, related_name="primary_codeset"
    )

    objects = SettingsManager()

    class Meta:
        db_table = "settings"
        default_related_name = "settings"

    def get_current(self):
        # Retrieve the settings, if exist
        try:
            return Settings.objects.get()
        except Settings.DoesNotExist:
            return None

    def update(self, srid=None, extent=None, timezone=None, primary_codeset=None):
        # Retrieve settings and update
        settings = self.get_current()
        if settings:
            # if exist
            if srid is not None:
                settings.srid = srid
            if extent is None:
                settings.extent = extent
            if timezone is not None:
                settings.timezone = timezone
            if primary_codeset is None:
                settings.primary_codest = primary_codeset
            settings.save()
        else:
            # If no instance exists, create a new one
            Settings.objects.create(
                srid=srid,
                extent=extent,
                timezone=timezone,
                primary_codeset=primary_codeset,
            )
