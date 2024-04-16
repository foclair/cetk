import pandas as pd
import pytest
from django.db import connection

from etk.edb import models
from etk.emissions.calc import calculate_source_emissions_df
from etk.emissions.views import (
    create_pointsource_emis_table,
    create_pointsource_emis_view,
)


def test_create_view(pointsources):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    create_pointsource_emis_view([NOx, SOx], unit="kg/year")


def test_create_table(pointsources):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    create_pointsource_emis_table([NOx, SOx], unit="kg/year")
    cur = connection.cursor()
    cur.execute("SELECT * from pointsource_emissions")
    df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    assert df.loc[0, "SOx"] == pytest.approx(2001000.0)


def test_calculate_emissions(pointsources):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    df = calculate_source_emissions_df("point", [NOx, SOx], unit="kg/year")
    assert df.loc[(1, "SOx"), "emis"] == pytest.approx(2001000.0)
