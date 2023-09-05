from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _

from etk.edb.models.source_models import CodeSet


class Settings(models.Manager):
    """Inventory specific database settings, replaces gadgets Domain and Inventory."""

    srid = models.IntegerField(
        _("SRID"), help_text=_("Spatial reference system identifier")
    )
    extent = models.MultiPolygonField(_("extent"), geography=True)
    timezone = models.CharField(_("timezone"), max_length=64)

    # some functionality in Gadget only works for one out of the three codesets.
    primary_codeset = models.ForeignKey(
        CodeSet, on_delete=models.CASCADE, related_name="primary_codeset"
    )

    class Meta:
        db_table = "settings"
        default_related_name = "settings"
