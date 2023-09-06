"""Global pytest configuration."""

# import numpy as np
# import sys

import pytest

from etk.edb.models.source_models import CodeSet, VerticalDist


@pytest.fixture()
def vertical_dist(db):
    vdist = VerticalDist.objects.create(
        name="vdist1", weights="[[5.0, 0.4], [10.0, 0.6]]"
    )
    return vdist


@pytest.fixture()
def code_sets(vertical_dist):
    cs1 = CodeSet.objects.create(name="codeset1", slug="codeset1")
    cs1.codes.create(code="1", label="Energy")
    cs1.codes.create(
        code="1.1", label="Stationary combustion", vertical_dist=vertical_dist
    )
    cs1.codes.create(
        code="1.2", label="Fugitive emissions", vertical_dist=vertical_dist
    )
    cs1.codes.create(code="1.3", label="Road traffic")
    cs1.codes.create(code="1.3.1", label="Light vehicles")
    cs1.codes.create(code="1.3.2", label="Heavy vehicles")
    cs1.codes.create(code="2", label="Industrial processes")
    cs1.codes.create(code="2.1", label="Mobile combustion")
    cs1.codes.create(code="2.2", label="Other")
    cs1.codes.create(code="3", label="Diffuse sources")

    cs2 = CodeSet.objects.create(name="codeset2", slug="codeset2")
    cs2.codes.create(code="A", label="Bla bla")

    return (cs1, cs2)
