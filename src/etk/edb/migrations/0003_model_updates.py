# Generated by Django 4.2.2 on 2024-03-08 09:42

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("edb", "0002_data"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="gridsource",
            name="height",
        ),
        migrations.AlterField(
            model_name="timevar",
            name="typeday",
            field=models.CharField(
                default=str([24 * [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]]),
                max_length=12240,
            ),
        ),
    ]
