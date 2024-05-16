"""A road class model."""

import functools
import itertools
from collections import OrderedDict
from operator import itemgetter

from django.db import models

from .road_models import TrafficSituation
from .source_models import BaseNamedModel


class RoadAttribute(BaseNamedModel):
    """A road attribute."""

    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, unique=True)
    order = models.PositiveSmallIntegerField(unique=True)

    class Meta:
        default_related_name = "road_attributes"
        ordering = ["order"]


class RoadAttributeValue(models.Model):
    """A valid road attribute value."""

    value = models.CharField(max_length=64)
    attribute = models.ForeignKey(
        RoadAttribute, on_delete=models.CASCADE, related_name="values"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["value", "attribute"], name="unique_road_attribute_value"
            )
        ]

    def __str__(self):
        return self.value


def get_valid_road_attribute_values():
    """Return a nested dict with ordered road attributes and their values."""
    return OrderedDict(
        (a, {v.value: v for v in a.values.all()})
        for a in RoadAttribute.objects.prefetch_related("values")
    )


class PrefetchRoadClassAttributes(models.Prefetch):
    """Custom Prefetch class to prefetch road class attributes."""

    def __init__(
        self, lookup="attribute_values", to_attr="prefetched_attribute_values"
    ):
        if not lookup.endswith("attribute_values"):
            lookup = f"{lookup}__attribute_values"
        super().__init__(
            lookup,
            queryset=RoadAttributeValue.objects.select_related("attribute").order_by(
                "attribute__order"
            ),
            to_attr=to_attr,
        )


class RoadClassQuerySet(models.QuerySet):
    """A custom query set for road classes."""

    def filter_on_attributes(self, attributes):
        """Return the road classes that have all of the given attributes."""

        def filter_one_attribute(qs, item):
            attr, value = item
            return qs.filter(
                attribute_values__attribute__slug=attr, attribute_values__value=value
            )

        return functools.reduce(filter_one_attribute, attributes.items(), self.all())


class RoadClassManager(models.Manager.from_queryset(RoadClassQuerySet)):
    """A custom database manager for road classes."""

    use_in_migrations = True

    def get_value_model(self):
        # Don't use RoadClassAttributeValue directly since we may be in a migration
        return self.model._meta.get_field("attribute_values").related_model

    def create_from_attributes(self, attributes, **kwargs):
        """Create a road class from an attribute mapping."""
        road_class = self.create(**kwargs)
        slugs = {k for k in attributes if not isinstance(k, RoadAttribute)}
        if slugs:
            attribute_instances = {
                a.slug: a for a in RoadAttribute.objects.filter(slug__in=slugs)
            }
            try:
                attributes = {
                    k if isinstance(k, RoadAttribute) else attribute_instances[k]: v
                    for k, v in attributes.items()
                }
            except KeyError as exc:
                raise RoadAttribute.DoesNotExist(
                    f"A road attribute with slug {exc} does not exist"
                )

        value_model = self.get_value_model()
        valid_values = get_valid_road_attribute_values()
        # check if values are given by names, then replace by RoadAttributeValues
        attribute_values = []
        for attr, val in attributes.items():
            if not isinstance(val, value_model):
                try:
                    attribute_values.append(valid_values[attr][val])
                except KeyError as exc:
                    raise value_model.DoesNotExist(
                        f"A value {exc} for road attribute '{attr.slug}' does not exist"
                    )
            else:
                attribute_values.append(val)

        road_class.attribute_values.set(attribute_values)
        return road_class

    def bulk_create_from_attribute_table(self, table, *, create_values=False):
        """Create road classes in bulk given an attribute *table*."""
        ts_ids = list(map(itemgetter(-1), table))
        traffic_situations = {
            ts.ts_id: ts
            for ts in TrafficSituation.objects.filter(ts_id__in=set(ts_ids))
        }
        road_classes = [
            self.model(traffic_situation=traffic_situations[ts_id]) for ts_id in ts_ids
        ]
        self.bulk_create(road_classes)
        ids = set([ts.id for ts in traffic_situations.values()])
        road_classes = self.model.objects.filter(traffic_situation_id__in=ids)
        if create_values:
            attributes = RoadAttribute.objects.all()
            value_model = self.get_value_model()
            valid_values = OrderedDict(
                (
                    a,
                    {
                        v: value_model(attribute=a, value=v)
                        for v in set(map(itemgetter(i), table))
                    },
                )
                for i, a in enumerate(attributes)
            )
            value_model.objects.bulk_create(
                [v for values in valid_values.values() for v in values.values()]
            )
        # need to define valid values even if create_values,
        # otherwise unsaved related object 'roadattributevalue'
        valid_values = get_valid_road_attribute_values()

        through_model = self.model.attribute_values.through
        try:
            values = [
                through_model(roadclass=c, roadattributevalue=valid_values[a][v])
                for c, row in zip(road_classes, table)
                for a, v in itertools.zip_longest(valid_values, row[:-1])
            ]
        except KeyError as err:
            raise RoadAttributeValue.DoesNotExist(f"invalid road attribute value {err}")
        through_model.objects.bulk_create(values)

        return road_classes


class RoadClass(models.Model):  # noqa: DJ008
    """A road class defined by a unique set of road attributes."""

    traffic_situation = models.ForeignKey("TrafficSituation", on_delete=models.CASCADE)
    attribute_values = models.ManyToManyField(RoadAttributeValue)

    objects = RoadClassManager()

    class Meta:
        default_related_name = "road_classes"

    @property
    def attributes(self):
        """An ordered dictionary mapping road attribute slugs to their values."""
        try:
            values = self.prefetched_attribute_values
        except AttributeError:
            values = self.attribute_values.select_related("attribute").order_by(
                "attribute__order"
            )
        return OrderedDict((v.attribute.slug, v.value) for v in values)
