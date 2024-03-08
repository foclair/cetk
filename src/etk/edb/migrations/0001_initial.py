# Generated by Django 4.2.2 on 2024-03-08 08:24

import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models

import etk.edb.ltreefield
import etk.edb.models.source_models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Activity",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=100, unique=True, verbose_name="name of activity"
                    ),
                ),
                (
                    "unit",
                    models.CharField(max_length=100, verbose_name="unit of activity"),
                ),
            ],
            options={
                "default_related_name": "activities",
            },
        ),
        migrations.CreateModel(
            name="ActivityCode",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", etk.edb.ltreefield.LtreeField(verbose_name="activity code")),
                (
                    "label",
                    models.CharField(
                        max_length=100, verbose_name="activity code label"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AreaSource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="name")),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="time of creation"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="time of last update"
                    ),
                ),
                (
                    "tags",
                    models.JSONField(
                        blank=True,
                        null=True,
                        verbose_name="user-defined key-value pairs",
                    ),
                ),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.PolygonField(
                        db_index=True,
                        geography=True,
                        srid=4326,
                        verbose_name="the extent of the area source",
                    ),
                ),
                (
                    "activitycode1",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activitycode",
                    ),
                ),
                (
                    "activitycode2",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activitycode",
                    ),
                ),
                (
                    "activitycode3",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activitycode",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "default_related_name": "areasources",
            },
        ),
        migrations.CreateModel(
            name="CodeSet",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=64)),
                ("slug", models.SlugField(max_length=64, unique=True)),
                (
                    "description",
                    models.CharField(
                        blank=True,
                        max_length=200,
                        null=True,
                        verbose_name="description",
                    ),
                ),
            ],
            options={
                "db_table": "codesets",
                "default_related_name": "codesets",
            },
        ),
        migrations.CreateModel(
            name="Facility",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="name")),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="time of creation"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="time of last update"
                    ),
                ),
                (
                    "tags",
                    models.JSONField(
                        blank=True,
                        null=True,
                        verbose_name="user-defined key-value pairs",
                    ),
                ),
                (
                    "official_id",
                    models.CharField(
                        db_index=True,
                        max_length=100,
                        unique=True,
                        verbose_name="official_id",
                    ),
                ),
            ],
            options={
                "default_related_name": "facilities",
            },
        ),
        migrations.CreateModel(
            name="GridSource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="name")),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="time of creation"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="time of last update"
                    ),
                ),
                (
                    "tags",
                    models.JSONField(
                        blank=True,
                        null=True,
                        verbose_name="user-defined key-value pairs",
                    ),
                ),
                (
                    "height",
                    models.FloatField(default=2.0, verbose_name="height above ground"),
                ),
                (
                    "activitycode1",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activitycode",
                    ),
                ),
                (
                    "activitycode2",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activitycode",
                    ),
                ),
                (
                    "activitycode3",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activitycode",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "default_related_name": "gridsources",
            },
        ),
        migrations.CreateModel(
            name="PointSource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="name")),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="time of creation"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="time of last update"
                    ),
                ),
                (
                    "tags",
                    models.JSONField(
                        blank=True,
                        null=True,
                        verbose_name="user-defined key-value pairs",
                    ),
                ),
                (
                    "chimney_height",
                    models.FloatField(default=0, verbose_name="chimney height [m]"),
                ),
                (
                    "chimney_outer_diameter",
                    models.FloatField(
                        default=1.0, verbose_name="chimney outer diameter [m]"
                    ),
                ),
                (
                    "chimney_inner_diameter",
                    models.FloatField(
                        default=0.9, verbose_name="chimney inner diameter [m]"
                    ),
                ),
                (
                    "chimney_gas_speed",
                    models.FloatField(
                        default=1.0, verbose_name="chimney gas speed [m/s]"
                    ),
                ),
                (
                    "chimney_gas_temperature",
                    models.FloatField(
                        default=373.0, verbose_name="chimney gas temperature [K]"
                    ),
                ),
                (
                    "house_width",
                    models.IntegerField(
                        default=0,
                        verbose_name="house width [m] (to estimate down draft)",
                    ),
                ),
                (
                    "house_height",
                    models.IntegerField(
                        default=0,
                        verbose_name="house height [m] (to estimate down draft)",
                    ),
                ),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.PointField(
                        db_index=True,
                        geography=True,
                        srid=4326,
                        verbose_name="the position of the point-source",
                    ),
                ),
                (
                    "activitycode1",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activitycode",
                    ),
                ),
                (
                    "activitycode2",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activitycode",
                    ),
                ),
                (
                    "activitycode3",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activitycode",
                    ),
                ),
                (
                    "facility",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="edb.facility",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "default_related_name": "pointsources",
            },
        ),
        migrations.CreateModel(
            name="Substance",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=64, unique=True, verbose_name="name"),
                ),
                (
                    "slug",
                    models.SlugField(max_length=64, unique=True, verbose_name="slug"),
                ),
                (
                    "long_name",
                    models.CharField(max_length=64, verbose_name="long name"),
                ),
            ],
            options={
                "db_table": "substances",
                "default_related_name": "substances",
            },
        ),
        migrations.CreateModel(
            name="Timevar",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                (
                    "typeday",
                    models.CharField(
                        default="["
                        + ",".join(
                            24 * ["[100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]"]
                        )
                        + "]",
                        max_length=12240,
                    ),
                ),
                (
                    "month",
                    models.CharField(
                        default=str(12 * [100.0]),
                        max_length=840,
                    ),
                ),
                ("typeday_sum", models.FloatField(editable=False)),
                ("_normalization_constant", models.FloatField(editable=False)),
            ],
            options={
                "abstract": False,
                "default_related_name": "timevars",
            },
        ),
        migrations.CreateModel(
            name="VerticalDist",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=64)),
                ("slug", models.SlugField(max_length=64, unique=True)),
                (
                    "weights",
                    models.CharField(
                        default=etk.edb.models.source_models.default_vertical_dist,
                        max_length=100,
                    ),
                ),
            ],
            options={
                "db_table": "vertical_distributions",
                "default_related_name": "vertical_distributions",
            },
        ),
        migrations.CreateModel(
            name="Settings",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "srid",
                    models.IntegerField(
                        help_text="Spatial reference system identifier",
                        verbose_name="SRID",
                    ),
                ),
                (
                    "extent",
                    django.contrib.gis.db.models.fields.PolygonField(
                        geography=True, srid=4326, verbose_name="extent"
                    ),
                ),
                ("timezone", models.CharField(max_length=64, verbose_name="timezone")),
                (
                    "codeset1",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="edb.codeset",
                    ),
                ),
                (
                    "codeset2",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="edb.codeset",
                    ),
                ),
                (
                    "codeset3",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="edb.codeset",
                    ),
                ),
            ],
            options={
                "db_table": "settings",
                "default_related_name": "settings",
            },
        ),
        migrations.CreateModel(
            name="PointSourceActivity",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("rate", models.FloatField(verbose_name="activity rate")),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activity",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="edb.pointsource",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "default_related_name": "activities",
            },
        ),
        migrations.AddField(
            model_name="pointsource",
            name="timevar",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="edb.timevar",
            ),
        ),
        migrations.CreateModel(
            name="Parameter",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=64, unique=True, verbose_name="name"),
                ),
                (
                    "slug",
                    models.SlugField(max_length=64, unique=True, verbose_name="slug"),
                ),
                (
                    "quantity",
                    models.CharField(max_length=30, verbose_name="physical quantity"),
                ),
                (
                    "substance",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="edb.substance",
                        verbose_name="substance",
                    ),
                ),
            ],
            options={
                "db_table": "parameters",
                "default_related_name": "parameters",
            },
        ),
        migrations.CreateModel(
            name="GridSourceSubstance",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("value", models.FloatField(default=0, verbose_name="source emission")),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="date of last update"
                    ),
                ),
                (
                    "raster",
                    models.CharField(
                        max_length=100, verbose_name="distribution raster"
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="edb.gridsource"
                    ),
                ),
                (
                    "substance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.substance",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "default_related_name": "substances",
            },
        ),
        migrations.CreateModel(
            name="GridSourceActivity",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("rate", models.FloatField(verbose_name="activity rate")),
                (
                    "raster",
                    models.CharField(
                        max_length=100, verbose_name="distribution raster"
                    ),
                ),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activity",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="edb.gridsource"
                    ),
                ),
            ],
            options={
                "abstract": False,
                "default_related_name": "activities",
            },
        ),
        migrations.AddField(
            model_name="gridsource",
            name="timevar",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="edb.timevar",
            ),
        ),
        migrations.CreateModel(
            name="EmissionFactor",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("factor", models.FloatField(default=0)),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="edb.activity"
                    ),
                ),
                (
                    "substance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.substance",
                    ),
                ),
            ],
            options={
                "default_related_name": "emissionfactors",
            },
        ),
        migrations.CreateModel(
            name="EEAEmissionFactor",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nfr_code", etk.edb.ltreefield.LtreeField(verbose_name="NFR code")),
                ("sector", models.CharField(max_length=100, null=True)),
                (
                    "table",
                    models.CharField(
                        max_length=100, verbose_name="table in EMEP/EEA Guidebook 2019"
                    ),
                ),
                ("tier", models.CharField(max_length=100)),
                ("technology", models.CharField(max_length=100, null=True)),
                ("fuel", models.CharField(max_length=100, null=True)),
                (
                    "abatement",
                    models.CharField(blank=True, default="", max_length=100, null=True),
                ),
                (
                    "region",
                    models.CharField(blank=True, default="", max_length=100, null=True),
                ),
                (
                    "unknown_substance",
                    models.CharField(blank=True, default="", max_length=100, null=True),
                ),
                (
                    "value",
                    models.FloatField(
                        default=0, verbose_name="best estimate emission factor"
                    ),
                ),
                (
                    "unit",
                    models.CharField(
                        max_length=100, verbose_name="unit of emission factor value"
                    ),
                ),
                (
                    "lower",
                    models.FloatField(
                        default=0,
                        null=True,
                        verbose_name="lower confidence interval emission factor",
                    ),
                ),
                (
                    "upper",
                    models.FloatField(
                        default=0,
                        null=True,
                        verbose_name="upper confidence interval emission factor",
                    ),
                ),
                ("reference", models.CharField(blank=True, max_length=100, null=True)),
                (
                    "substance",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.substance",
                    ),
                ),
            ],
            options={
                "default_related_name": "eea_emissionfactors",
            },
        ),
        migrations.CreateModel(
            name="AreaSourceSubstance",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("value", models.FloatField(default=0, verbose_name="source emission")),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="date of last update"
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="edb.areasource"
                    ),
                ),
                (
                    "substance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.substance",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "default_related_name": "substances",
            },
        ),
        migrations.CreateModel(
            name="AreaSourceActivity",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("rate", models.FloatField(verbose_name="activity rate")),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.activity",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="edb.areasource"
                    ),
                ),
            ],
            options={
                "abstract": False,
                "default_related_name": "activities",
            },
        ),
        migrations.AddField(
            model_name="areasource",
            name="facility",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="edb.facility",
            ),
        ),
        migrations.AddField(
            model_name="areasource",
            name="timevar",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="edb.timevar",
            ),
        ),
        migrations.AddField(
            model_name="activitycode",
            name="code_set",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="codes",
                to="edb.codeset",
            ),
        ),
        migrations.AddField(
            model_name="activitycode",
            name="vertical_dist",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="edb.verticaldist",
            ),
        ),
        migrations.CreateModel(
            name="PointSourceSubstance",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("value", models.FloatField(default=0, verbose_name="source emission")),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="date of last update"
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="edb.pointsource",
                    ),
                ),
                (
                    "substance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="edb.substance",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "default_related_name": "substances",
                "unique_together": {("source", "substance")},
            },
        ),
        migrations.AddConstraint(
            model_name="pointsourceactivity",
            constraint=models.UniqueConstraint(
                fields=("source", "activity"),
                name="pointsourceactivity_unique_activity_in_source",
            ),
        ),
        migrations.AddIndex(
            model_name="pointsource",
            index=models.Index(
                fields=["activitycode1", "activitycode2", "activitycode3"],
                name="pointsource_activities_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="pointsource",
            unique_together={("facility", "name")},
        ),
        migrations.AlterUniqueTogether(
            name="gridsourcesubstance",
            unique_together={("source", "substance")},
        ),
        migrations.AddConstraint(
            model_name="gridsourceactivity",
            constraint=models.UniqueConstraint(
                fields=("source", "activity"),
                name="gridsourceactivity_unique_activity_in_source",
            ),
        ),
        migrations.AddIndex(
            model_name="gridsource",
            index=models.Index(
                fields=["activitycode1", "activitycode2", "activitycode3"],
                name="gridsource_activities_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="gridsource",
            constraint=models.UniqueConstraint(
                fields=("name",), name="gridsource_unique_name"
            ),
        ),
        migrations.AddConstraint(
            model_name="emissionfactor",
            constraint=models.UniqueConstraint(
                fields=("activity", "substance"),
                name="emissionfactor_activity_substance_unique_together",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="areasourcesubstance",
            unique_together={("source", "substance")},
        ),
        migrations.AddConstraint(
            model_name="areasourceactivity",
            constraint=models.UniqueConstraint(
                fields=("source", "activity"),
                name="areasourceactivity_unique_activity_in_source",
            ),
        ),
        migrations.AddIndex(
            model_name="areasource",
            index=models.Index(
                fields=["activitycode1", "activitycode2", "activitycode3"],
                name="areasource_activities_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="areasource",
            constraint=models.UniqueConstraint(
                fields=("facility", "name"), name="areasource_unique_facility_and_name"
            ),
        ),
        migrations.AddConstraint(
            model_name="activitycode",
            constraint=models.UniqueConstraint(
                fields=("code_set", "code"), name="unique code in codeset"
            ),
        ),
    ]
