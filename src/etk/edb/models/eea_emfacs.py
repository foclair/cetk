from django.contrib.gis.db import models

from etk.edb.const import CHAR_FIELD_LENGTH
from etk.edb.ltreefield import LtreeField


class EEAEmissionFactor(models.Model):
    """Emission factors reported by EEA."""

    nfr_code = LtreeField(verbose_name="NFR code")
    sector = models.CharField(max_length=CHAR_FIELD_LENGTH, null=True)
    table = models.CharField(
        "table in EMEP/EEA Guidebook 2019", max_length=CHAR_FIELD_LENGTH
    )
    tier = models.CharField(max_length=CHAR_FIELD_LENGTH)
    technology = models.CharField(max_length=CHAR_FIELD_LENGTH, null=True)
    fuel = models.CharField(max_length=CHAR_FIELD_LENGTH, null=True)
    abatement = models.CharField(
        max_length=CHAR_FIELD_LENGTH, blank=True, default="", null=True
    )
    region = models.CharField(
        max_length=CHAR_FIELD_LENGTH, blank=True, default="", null=True
    )
    substance = models.ForeignKey(
        "Substance", on_delete=models.PROTECT, related_name="+", null=True
    )
    unknown_substance = models.CharField(
        max_length=CHAR_FIELD_LENGTH, blank=True, default="", null=True
    )
    value = models.FloatField("best estimate emission factor", default=0)
    unit = models.CharField(
        verbose_name="unit of emission factor value", max_length=CHAR_FIELD_LENGTH
    )
    lower = models.FloatField(
        "lower confidence interval emission factor", default=0, null=True
    )
    upper = models.FloatField(
        "upper confidence interval emission factor", default=0, null=True
    )
    reference = models.CharField(max_length=CHAR_FIELD_LENGTH, blank=True, null=True)

    class Meta:
        # duplicates in database, no constraint unique together.
        default_related_name = "eea_emissionfactors"
