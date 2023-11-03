from etk.emissions.calc import aggregate_emissions  # noqa


def test_aggregate_emissions(pointsources):
    """test aggregation of emissions"""
    df = aggregate_emissions()
    assert df.loc["total", ("emission", "NOx")] == 31557610.0
