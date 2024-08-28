"""Unit and regression tests for the road class models."""

from collections import OrderedDict

import pytest
from django.db import IntegrityError
from pytest_django.asserts import assertNumQueries, assertQuerySetEqual

from cetk.edb.models import (
    PrefetchRoadClassAttributes,
    RoadAttribute,
    RoadAttributeValue,
    RoadClass,
    RoadSource,
    TrafficSituation,
)


@pytest.fixture
def road_attributes(db):
    # Create a road attribute
    RoadAttribute.objects.create(name="road type", slug="type", order=0)

    roadtype_attr = RoadAttribute.objects.get(name="road type")

    RoadAttribute.objects.create(name="posted speed", slug="speed", order=1)
    speed_attr = RoadAttribute.objects.get(name="posted speed")
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
def traffic_situation(db):
    TrafficSituation.objects.create()
    return TrafficSituation.objects.first()


class TestRoadAttribute:
    @pytest.fixture
    def attr(self, db):
        RoadAttribute.objects.create(name="My attribute", slug="my-attribute", order=0)
        return RoadAttribute.objects.get(name="My attribute")

    def test_ordering(self, db):
        RoadAttribute.objects.create(name="A", slug="a", order=1)
        RoadAttribute.objects.create(name="B", slug="b", order=0)
        RoadAttribute.objects.create(name="C", slug="c", order=2)
        assert "".join(RoadAttribute.objects.values_list("name", flat=True)) == "BAC"

    def test_unique_name(self, attr):
        with pytest.raises(IntegrityError) as excinfo:
            RoadAttribute.objects.create(name=attr.name, slug="another-slug", order=9)
        assert "UNIQUE constraint" in str(excinfo.value)

    def test_unique_slug(self, attr):
        with pytest.raises(IntegrityError) as excinfo:
            RoadAttribute.objects.create(name="Another name", slug=attr.slug, order=9)
        assert "UNIQUE constraint" in str(excinfo.value)

    def test_unique_order(self, attr):
        with pytest.raises(IntegrityError) as excinfo:
            RoadAttribute.objects.create(
                name="Another name",
                slug="another-slug",
                order=attr.order,
            )
        assert "UNIQUE constraint" in str(excinfo.value)


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

    def test_bulk_create_from_attribute_table(self, road_attributes):
        roadtype, speed = road_attributes
        TrafficSituation.objects.create(ts_id="t1")
        TrafficSituation.objects.create(ts_id="t2")
        ts1 = TrafficSituation.objects.get(ts_id="t1")
        ts2 = TrafficSituation.objects.get(ts_id="t2")
        table = [("dirt road", "50", ts1.ts_id), ("highway", "110", ts2.ts_id)]
        with assertNumQueries(6):
            RoadClass.objects.bulk_create_from_attribute_table(table)
        road_classes = RoadClass.objects.all()
        assert len(road_classes) == 2
        assertQuerySetEqual(
            RoadClass.objects.filter(traffic_situation__in=[ts1, ts2]).order_by(
                "traffic_situation__ts_id"
            ),
            road_classes,
        )
        rc1, rc2 = road_classes
        assert rc1.attributes == OrderedDict([("type", "dirt road"), ("speed", "50")])
        assert rc2.attributes == OrderedDict([("type", "highway"), ("speed", "110")])

    def test_bulk_create_from_attribute_table_with_create_values(self, db):
        roadtype, speed = [
            RoadAttribute(name="road type", slug="type", order=0),
            RoadAttribute(name="posted speed", slug="speed", order=1),
        ]
        RoadAttribute.objects.bulk_create([roadtype, speed])
        roadtype = RoadAttribute.objects.get(name="road type")
        speed = RoadAttribute.objects.get(name="posted speed")
        TrafficSituation.objects.create(ts_id="t1")
        TrafficSituation.objects.create(ts_id="t2")
        ts1 = TrafficSituation.objects.get(ts_id="t1")
        ts2 = TrafficSituation.objects.get(ts_id="t2")
        table = [("dirt road", "50", ts1.ts_id), ("highway", "110", ts2.ts_id)]
        with assertNumQueries(8):
            RoadClass.objects.bulk_create_from_attribute_table(
                table, create_values=True
            )
        road_classes = RoadClass.objects.all()

        assert len(road_classes) == 2
        assertQuerySetEqual(
            RoadClass.objects.filter(traffic_situation__in=[ts1, ts2]).order_by(
                "traffic_situation__ts_id"
            ),
            road_classes,
        )
        rc1, rc2 = road_classes
        assert rc1.attributes == OrderedDict([("type", "dirt road"), ("speed", "50")])
        assert rc2.attributes == OrderedDict([("type", "highway"), ("speed", "110")])

        assertQuerySetEqual(
            RoadAttributeValue.objects.filter(attribute=roadtype).order_by("value"),
            ["dirt road", "highway"],
            str,
        )
        assertQuerySetEqual(
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
                [(*values, traffic_situation.ts_id)]
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
    def test_filter_on_attributes(self, attributes, expected_ts_ids):
        TrafficSituation.objects.bulk_create(
            [
                TrafficSituation(ts_id="d50"),
                TrafficSituation(ts_id="d70"),
                TrafficSituation(ts_id="h70"),
                TrafficSituation(ts_id="h90"),
            ]
        )
        RoadClass.objects.bulk_create_from_attribute_table(
            [
                ("dirt road", "50", "d50"),
                ("dirt road", "70", "d70"),
                ("highway", "70", "h70"),
                ("highway", "90", "h90"),
            ],
        )
        with assertNumQueries(1):
            ts_ids = set(
                RoadClass.objects.filter_on_attributes(attributes).values_list(
                    "traffic_situation__ts_id", flat=True
                )
            )
        assert ts_ids == expected_ts_ids


class TestPrefetchRoadClassAttributes:
    @pytest.fixture
    def road_classes(self, road_attributes, traffic_situation):  # noqa: ARG002
        return RoadClass.objects.bulk_create_from_attribute_table(
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

    def test_with_road_sources(self, road_classes):

        with assertNumQueries(1):
            road_sources = list(
                RoadSource.objects.select_related("roadclass").prefetch_related(
                    PrefetchRoadClassAttributes("roadclass")
                )
            )
        with assertNumQueries(0):
            for road_source in road_sources:
                assert road_source.roadclass.attributes
