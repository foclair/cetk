import pandas as pd
import pytest
from django.db import connection

from cetk.edb import models
from cetk.emissions.calc import calculate_source_emissions_df
from cetk.emissions.views import create_emission_table, create_emission_view


def test_create_view(areasources):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    create_emission_view("area", [NOx, SOx], unit="kg/year")


def test_create_table(areasources):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    create_emission_table("area", [NOx, SOx], unit="kg/year")
    cur = connection.cursor()
    cur.execute("SELECT * from areasource_emissions")
    df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    assert df.loc[:, "SOx"].sum() == pytest.approx(2001000.0)


def test_calculate_emissions(areasources):
    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    df = calculate_source_emissions_df("area", [NOx, SOx], unit="kg/year")
    assert df.loc[(slice(None), "SOx"), "emis"].sum() == pytest.approx(2001000.0)
