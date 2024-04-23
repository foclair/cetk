"""Unit and regression tests for the road class models."""

from collections import OrderedDict

import pytest
from django.db import IntegrityError
from pytest_django.asserts import assertNumQueries, assertQuerysetEqual

from etk.edb.models import (
    PrefetchRoadClassAttributes,
    RoadAttribute,
    RoadAttributeValue,
    RoadClass,
    RoadSource,
    TrafficSituation,
)


@pytest.fixture
def base_set(ifactory):
    return ifactory.edb.baseset()


@pytest.fixture
def road_attributes(base_set, ifactory):
    # Create a road attribute in another base set just to make
    # sure it doesn't interfere
    ifactory.edb.roadattribute(name="road type", slug="type", order=1)

    roadtype_attr = base_set.road_attributes.create(
        name="road type", slug="type", order=0
    )
    speed_attr = base_set.road_attributes.create(
        name="posted speed", slug="speed", order=1
    )
    RoadAttributeValue.objects.bulk_create(
        [
            RoadAttributeValue(attribute=roadtype_attr, value="dirt road"),
            RoadAttributeValue(attribute=roadtype_attr, value="highway"),
            RoadAttributeValue(attribute=speed_attr, value="50"),
            RoadAttributeValue(attribute=speed_attr, value="70"),
            RoadAttributeValue(attribute=speed_attr, value="90"),
            RoadAttributeValue(attribute=speed_attr, value="110"),
        ]
    )
    return [roadtype_attr, speed_attr]


@pytest.fixture
def traffic_situation(base_set, ifactory):
    return ifactory.edb.trafficsituation(base_set=base_set)


class TestRoadAttribute:
    @pytest.fixture
    def attr(self, base_set, ifactory):
        return ifactory.edb.roadattribute(
            name="My attribute", slug="my-attribute", order=0, base_set=base_set
        )

    @pytest.fixture
    def another_base_set(self, ifactory):
        return ifactory.edb.baseset()

    def test_ordering(self, base_set, ifactory):
        ifactory.edb.roadattribute(name="A", slug="a", order=1, base_set=base_set)
        ifactory.edb.roadattribute(name="B", slug="b", order=0, base_set=base_set)
        ifactory.edb.roadattribute(name="C", slug="c", order=2, base_set=base_set)
        assert "".join(base_set.road_attributes.values_list("name", flat=True)) == "BAC"

    def test_unique_name(self, attr, another_base_set):
        try:
            RoadAttribute.objects.create(
                name=attr.name, slug="another-slug", order=9, base_set=another_base_set
            )
        except IntegrityError:
            pytest.fail(
                "unexpected integrity error when creating an attribute with the same "
                "name in another base set"
            )
        with pytest.raises(IntegrityError) as excinfo:
            RoadAttribute.objects.create(
                name=attr.name, slug="another-slug", order=9, base_set=attr.base_set
            )
        assert "unique constraint" in str(excinfo.value)

    def test_unique_slug(self, attr, another_base_set):
        try:
            RoadAttribute.objects.create(
                name="Another name", slug=attr.slug, order=9, base_set=another_base_set
            )
        except IntegrityError:
            pytest.fail(
                "unexpected integrity error when creating an attribute with the same "
                "slug in another base set"
            )
        with pytest.raises(IntegrityError) as excinfo:
            RoadAttribute.objects.create(
                name="Another name", slug=attr.slug, order=9, base_set=attr.base_set
            )
        assert "unique constraint" in str(excinfo.value)

    def test_unique_order(self, attr, another_base_set):
        try:
            RoadAttribute.objects.create(
                name="Another name",
                slug="another-slug",
                order=attr.order,
                base_set=another_base_set,
            )
        except IntegrityError:
            pytest.fail(
                "unexpected integrity error when creating an attribute with the same "
                "order in another base set"
            )
        with pytest.raises(IntegrityError) as excinfo:
            RoadAttribute.objects.create(
                name="Another name",
                slug="another-slug",
                order=attr.order,
                base_set=attr.base_set,
            )
        assert "unique constraint" in str(excinfo.value)


class TestRoadClass:
    def test_create_from_attributes(self, road_attributes, traffic_situation):
        roadtype, speed = road_attributes
        attributes = [(roadtype, "highway"), (speed, "110")]
        with assertNumQueries(5):
            road_class = RoadClass.objects.create_from_attributes(
                dict(attributes), traffic_situation=traffic_situation
            )
        with assertNumQueries(1):
            assert road_class.attributes == OrderedDict(
                (a.slug, v) for a, v in attributes
            )
        assert all(
            v.attribute in road_attributes for v in road_class.attribute_values.all()
        )
        assert road_class.traffic_situation == traffic_situation

    def test_create_from_attributes_with_slugs(
        self, road_attributes, traffic_situation
    ):
        roadtype, speed = road_attributes
        attributes = [(roadtype.slug, "highway"), (speed.slug, "110")]
        with assertNumQueries(6):
            road_class = RoadClass.objects.create_from_attributes(
                dict(attributes), traffic_situation=traffic_situation
            )
        with assertNumQueries(1):
            assert road_class.attributes == OrderedDict(attributes)
        assert all(
            v.attribute in road_attributes for v in road_class.attribute_values.all()
        )
        assert road_class.traffic_situation == traffic_situation

    def test_create_from_attributes_with_invalid_value_slugs(
        self, road_attributes, traffic_situation
    ):
        roadtype, speed = road_attributes
        attributes = {roadtype.slug: "highway", speed.slug: "9000"}
        with pytest.raises(RoadAttributeValue.DoesNotExist) as excinfo:
            RoadClass.objects.create_from_attributes(
                attributes, traffic_situation=traffic_situation
            )
        assert "A value '9000'" in str(excinfo.value)

    def test_bulk_create_from_attribute_table(
        self, base_set, road_attributes, ifactory
    ):
        roadtype, speed = road_attributes
        ts1 = ifactory.edb.trafficsituation(ts_id="t1", base_set=base_set)
        ts2 = ifactory.edb.trafficsituation(ts_id="t2", base_set=base_set)
        table = [("dirt road", "50", ts1.ts_id), ("highway", "110", ts2.ts_id)]
        with assertNumQueries(5):
            road_classes = RoadClass.objects.bulk_create_from_attribute_table(
                base_set, table
            )
        assert len(road_classes) == 2
        assertQuerysetEqual(
            RoadClass.objects.filter(traffic_situation__in=[ts1, ts2]).order_by(
                "traffic_situation__ts_id"
            ),
            road_classes,
        )
        rc1, rc2 = road_classes
        assert rc1.attributes == OrderedDict([("type", "dirt road"), ("speed", "50")])
        assert rc2.attributes == OrderedDict([("type", "highway"), ("speed", "110")])

    def test_bulk_create_from_attribute_table_with_create_values(
        self, base_set, ifactory
    ):
        roadtype, speed = [
            RoadAttribute(name="road type", slug="type", order=0, base_set=base_set),
            RoadAttribute(
                name="posted speed", slug="speed", order=1, base_set=base_set
            ),
        ]
        RoadAttribute.objects.bulk_create([roadtype, speed])
        ts1 = ifactory.edb.trafficsituation(ts_id="t1", base_set=base_set)
        ts2 = ifactory.edb.trafficsituation(ts_id="t2", base_set=base_set)
        table = [("dirt road", "50", ts1.ts_id), ("highway", "110", ts2.ts_id)]
        with assertNumQueries(5):
            road_classes = RoadClass.objects.bulk_create_from_attribute_table(
                base_set, table, create_values=True
            )

        assert len(road_classes) == 2
        assertQuerysetEqual(
            RoadClass.objects.filter(traffic_situation__in=[ts1, ts2]).order_by(
                "traffic_situation__ts_id"
            ),
            road_classes,
        )
        rc1, rc2 = road_classes
        assert rc1.attributes == OrderedDict([("type", "dirt road"), ("speed", "50")])
        assert rc2.attributes == OrderedDict([("type", "highway"), ("speed", "110")])

        assertQuerysetEqual(
            RoadAttributeValue.objects.filter(attribute=roadtype).order_by("value"),
            ["dirt road", "highway"],
            str,
        )
        assertQuerysetEqual(
            RoadAttributeValue.objects.filter(attribute=speed).order_by("value"),
            ["110", "50"],
            str,
        )

    @pytest.mark.parametrize("values", [("v1",), ("v1", "v2", "v3")])
    def test_bulk_create_from_attribute_table_with_invalid_table(
        self, traffic_situation, values
    ):
        with pytest.raises(RoadAttributeValue.DoesNotExist) as excinfo:
            RoadClass.objects.bulk_create_from_attribute_table(
                traffic_situation.base_set, [(*values, traffic_situation.ts_id)]
            )
        assert "invalid road attribute value" in str(excinfo.value)

    @pytest.mark.usefixtures("road_attributes")
    @pytest.mark.parametrize(
        "attributes,expected_ts_ids",
        [
            ({}, {"d50", "d70", "h70", "h90"}),
            ({"type": "dirt road"}, {"d50", "d70"}),
            ({"speed": "70"}, {"d70", "h70"}),
            ({"type": "dirt road", "speed": "70"}, {"d70"}),
        ],
    )
    def test_filter_on_attributes(self, base_set, attributes, expected_ts_ids):
        TrafficSituation.objects.bulk_create(
            [
                TrafficSituation(ts_id="d50", base_set=base_set),
                TrafficSituation(ts_id="d70", base_set=base_set),
                TrafficSituation(ts_id="h70", base_set=base_set),
                TrafficSituation(ts_id="h90", base_set=base_set),
            ]
        )
        RoadClass.objects.bulk_create_from_attribute_table(
            base_set,
            [
                ("dirt road", "50", "d50"),
                ("dirt road", "70", "d70"),
                ("highway", "70", "h70"),
                ("highway", "90", "h90"),
            ],
        )
        with assertNumQueries(1):
            ts_ids = set(
                RoadClass.objects.filter(traffic_situation__base_set=base_set)
                .filter_on_attributes(attributes)
                .values_list("traffic_situation__ts_id", flat=True)
            )
        assert ts_ids == expected_ts_ids


class TestPrefetchRoadClassAttributes:
    @pytest.fixture
    def road_classes(self, road_attributes, traffic_situation):  # noqa: ARG002
        return RoadClass.objects.bulk_create_from_attribute_table(
            traffic_situation.base_set,
            [
                ("dirt road", "50", traffic_situation.ts_id),
                ("highway", "110", traffic_situation.ts_id),
            ],
        )

    @pytest.mark.usefixtures("road_classes")
    def test_with_road_classes(self):
        with assertNumQueries(2):
            road_classes = list(
                RoadClass.objects.prefetch_related(PrefetchRoadClassAttributes())
            )
        with assertNumQueries(0):
            for road_class in road_classes:
                assert road_class.attributes

    def test_with_road_sources(self, road_classes, ifactory):
        for road_class in road_classes:
            ifactory.edb.roadsource(roadclass=road_class)
        with assertNumQueries(2):
            road_sources = list(
                RoadSource.objects.select_related("roadclass").prefetch_related(
                    PrefetchRoadClassAttributes("roadclass")
                )
            )
        with assertNumQueries(0):
            for road_source in road_sources:
                assert road_source.roadclass.attributes
