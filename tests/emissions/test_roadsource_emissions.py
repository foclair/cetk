import pandas as pd
import pytest
from django.db import connection

from cetk.edb import models
from cetk.emissions.calc import calculate_source_emissions_df
from cetk.emissions.views import create_emission_table, create_emission_view


def test_calculate_emissions(roadsources):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    df = calculate_source_emissions_df("road", substances=[NOx, SOx], unit="kg/year")
    assert df.loc[(1, "SOx", "car"), "emis"] == pytest.approx(358.91682597946345)
    assert df.loc[(1, "SOx", "car"), "traffic_work"] == pytest.approx(84.03981206578662)


def test_create_view(roadsources):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    create_emission_view("road", [NOx, SOx], unit="kg/year")


def test_create_table(roadsources):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    create_emission_table("road", [NOx, SOx], unit="kg/year")
    cur = connection.cursor()
    cur.execute("SELECT * from roadsource_emissions")
    df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    assert df.loc[0, "SOx"] == pytest.approx(629.4304928506848)
