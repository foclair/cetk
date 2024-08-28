import pytest

from cetk.edb import models
from cetk.emissions.calc import calculate_source_emissions_df

# from cetk.emissions.views import create_gridsource_emis_table


# @pytest.mark.django_db(transaction=False)
# def test_create_table(gridsources):
#     NOx = models.Substance.objects.get(slug="NOx")
#     SOx = models.Substance.objects.get(slug="SOx")
#     create_gridsource_emis_table([NOx, SOx], unit="kg/year")
#     cur = connection.cursor()
#     cur.execute("SELECT * from gridsource_emissions")
#     df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
#     assert df.loc[0, "SOx"] == pytest.approx(2001000.0)


def test_calculate_emissions(gridsources):

    NOx = models.Substance.objects.get(slug="NOx")
    SOx = models.Substance.objects.get(slug="SOx")
    df = calculate_source_emissions_df("grid", [NOx, SOx], unit="ton/year")
    assert df.loc[(1, "SOx", "raster1"), "emis"] == pytest.approx(301.0)
