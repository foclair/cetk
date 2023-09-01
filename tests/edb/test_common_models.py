"""Unit and regression tests for edb models."""

# from collections import OrderedDict
import ast

import numpy as np
import pytest

from etk.edb.models import source_models


class TestActivityCodes:
    def test_activitycode1_manager_create(self, code_sets):
        """Test creating a new activitycode with reference to a code-set."""
        code_set = code_sets[0]
        ac1 = source_models.ActivityCode.objects.create(
            code="actcode1", label="label1", code_set=code_set
        )
        ac1_ref = code_set.codes.get(code="actcode1", code_set=code_set)
        assert ac1 == ac1_ref

        ac1, created = code_set.codes.get_or_create(code="actcode1", label="label1")
        assert not created
        assert ac1 == ac1_ref

        ac2, created = code_set.codes.get_or_create(code="actcode2", label="label2")
        assert created

    def test_get_children(self, code_sets):
        code_set = code_sets[0]
        ac1 = code_set.codes.get(code="1")
        ac13 = code_set.codes.get(code="1.3")
        ac131 = code_set.codes.get(code="1.3.1")
        # breakpoint()
        assert ac13 in list(ac1.get_children())
        assert ac131 not in list(ac1.get_children())
        assert ac131 in list(ac13.get_children())

    def test_get_parent(self, code_sets):
        code_set = code_sets[0]
        ac1 = code_set.codes.get(code="1")
        ac13 = code_set.codes.get(code="1.3")
        ac131 = code_set.codes.get(code="1.3.1")
        assert ac1 == ac13.get_parent()
        assert ac13 == ac131.get_parent()
        with pytest.raises(RuntimeError):
            ac1.get_parent()


class TestVerticalDist:
    def test_create_vertical_dist(self, code_sets):
        # code_sets only used to get fixture
        code_set = code_sets[0]  # noqa
        vdist = source_models.VerticalDist.objects.create(
            name="residential heating",
            weights="[[5, 0], [10, 0.3], [15, 0.7]]",
            slug="residential_heating",
        )
        assert len(np.array(ast.literal_eval(vdist.weights))) == 3

    def test_str(self, vertical_dist):
        assert str(vertical_dist) == vertical_dist.name
