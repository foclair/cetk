"""Emission database models."""

# import numpy as np
from django.contrib.gis.db import models
from django.db.models import Sum

CHAR_FIELD_LENGTH = 100
SRID = 4326



class Substance(models.Model):
    '''A substance.'''

    id = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    name = models.CharField('name', max_length=64, unique=True)
    slug = models.SlugField('slug', max_length=64, unique=True)
    long_name = models.CharField(
        verbose_name='Descriptive name', max_length=64
    )

    class Meta:
        db_table = 'substance'
        default_related_name = 'substances'

    def __str__(self):
        return self.name


class Fuel(models.Model):
    '''A fuel.'''

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    name = models.CharField(max_length=CHAR_FIELD_LENGTH)

    class Meta:
        db_table = 'fuel'
        
    def __str__(self):
        return self.name


class ActivityCode(models.Model):
    """An abstract model for an activity code."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    label = models.CharField(
        verbose_name='activity code label',
        max_length=100
    )

    code = models.CharField(
        verbose_name='activity code',
        max_length=20,
        unique=True
    )

    class Meta:
        abstract = True

    def __str__(self):
        """Return a unicode representation of this activity code."""
        return self.code

    def matches(self, filters):
        """Compare with a (list of) filter code(s).
        args
        filters: list of accepted codes

        Filters should be '.'-separated codes
        comparison is only made for code levels included in filter
        i.e. the code 1.A.2.i will match the filter 1.A
        """

        code_parts = self.code.split('.')

        for f in filters:
            matches = True
            filter_parts = f.code.split('.')

            # filter has more code-parts than code
            if len(filter_parts) > len(code_parts):
                matches = False
                continue

            # compare code with filter part by part
            for i, filter_part in enumerate(filter_parts):
                if filter_part != code_parts[i]:
                    matches = False
                    break
            if matches:
                return matches
        return matches


class ActivityCode1(ActivityCode):
    """Actvity code 1."""

    class Meta:
        db_table = 'activitycode1'


class ActivityCode2(ActivityCode):
    """Actvity code 2."""

    class Meta:
        db_table = 'activitycode2'


class ActivityCode3(ActivityCode):
    """Actvity code 3."""

    class Meta:
        db_table = 'activitycode3'


def default_timevar_typeday():
    return str(24 * [7 * [100.0]])


def default_timevar_month():
    return str(12 * [100.0])


class Timevar(models.Model):
    '''A base class for an emission time-variation.'''

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    name = models.CharField(
        verbose_name='name of time variation profile',
        max_length=CHAR_FIELD_LENGTH,
        unique=True
    )

    typeday = models.CharField(
        verbose_name='A table of hourly variation within a typical week',
        max_length=1000
    )

    month = models.CharField(
        verbose_name='A table of monthly variations',
        max_length=100,
        default=default_timevar_month,
    )

    class Meta:
        abstract = True

    def __str__(self):
        """Return a unicode representation of this timevariation."""
        return self.name


class SourceTimevar(Timevar):
    """A source time-variation profile."""

    class Meta:
        db_table = 'sourcetimevar'


class RoadTimevar(Timevar):
    """A road time-variation profile."""

    class Meta:
        db_table = 'roadtimevar'


def default_congestion_profile_traffic_condition():
    return str(24 * [7 * [1]])


class CongestionProfile(models.Model):
    """A congestion level time profile."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    name = models.CharField(
        verbose_name='name of congestion profile',
        max_length=CHAR_FIELD_LENGTH,
        unique=True
    )

    # a 2d-field of traffic condition indices
    # 1: freeflow, 2: heavy, 3: congested, 4: stopngo
    # typical conditions given for a typeweek
    # hours are rows and days are columns
    traffic_condition = models.CharField(
        verbose_name='A table of hourly congestion levels in a typical week.',
        max_length=800,
        default=default_congestion_profile_traffic_condition,
    )

    class Meta:
        db_table = 'congestion_profile'

    def __str__(self):
        return self.name


class Activity(models.Model):
    """An emitting activity."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    name = models.CharField(
        verbose_name='name of activity',
        max_length=CHAR_FIELD_LENGTH,
        unique=True
    )

    class Meta:
        db_table = 'activity'


    def __str__(self):
        """Return a unicode representation of this activity."""
        return self.name


class EmissionFactor(models.Model):
    """An emission factor."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    activity = models.ForeignKey(
        'Activity',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='emissionfactors'
    )

    substance = models.ForeignKey(
        'Substance',
        on_delete=models.CASCADE,
        related_name='+',
        db_index=True
    )

    factor = models.FloatField(default=0)

    class Meta:
        db_table = 'emissionfactor'
        default_related_name = 'substances'
        unique_together = ('activity', 'substance')

    def __str__(self):
        """Return a unicode representation of this emission factor."""
        return '{}: {}'.format(self.activity.name, self.substance.name)


class SourceEmission(models.Model):
    """An abstract model for source emissions."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    timevar = models.ForeignKey(
        'SourceTimevar',
        on_delete=models.PROTECT,
        related_name='+',
        db_index=True
    )

    activitycode1 = models.ForeignKey(
        'ActivityCode1',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )

    activitycode2 = models.ForeignKey(
        'ActivityCode2',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )

    activitycode3 = models.ForeignKey(
        'ActivityCode3',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )

    class Meta:
        abstract = True
        index_together = ('activitycode1', 'activitycode2', 'activitycode3')
        default_related_name = 'sources'


class SourceActivity(SourceEmission):
    """Base class for an emitting activity."""

    activity = models.ForeignKey(
        'Activity',
        on_delete=models.PROTECT,
        related_name='+',
        db_index=True
    )

    rate = models.FloatField(
        verbose_name='activity rate'
    )

    class Meta:
        abstract = True


class PointSourceActivity(SourceActivity):
    """An emitting activity of a point source."""

    source = models.ForeignKey(
        'PointSource',
        related_name='activities',
        on_delete=models.CASCADE,
        db_index=True
    )
    
    class Meta:
        db_table = 'pointsource_activity'

    def __str__(self):
        return '{}'.format(self.activity.name)


class AreaSourceActivity(SourceActivity):
    """An emitting activity of an area source."""

    source = models.ForeignKey(
        'AreaSource',
        related_name='activities',
        on_delete=models.CASCADE,
        db_index=True
    )
    
    class Meta:
        db_table = 'areasource_activity'

    def __str__(self):
        return '{}'.format(self.activity.name)


class SourceBase(models.Model):
    """Abstract base model for an emission source."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    name = models.CharField(
        'name',
        max_length=CHAR_FIELD_LENGTH,
        blank=False,
        db_index=True
    )
    info = models.CharField(
        verbose_name='general information',
        max_length=CHAR_FIELD_LENGTH, blank=True,
        null=True,
        db_index=True
    )
    infogiver = models.CharField(
        verbose_name='information source',
        blank=True,
        null=True,
        max_length=CHAR_FIELD_LENGTH
    )
    created = models.DateField(
        verbose_name='date of creation',
        auto_now_add=True,
        editable=False
    )
    updated = models.DateTimeField(
        verbose_name='date of last update',
        auto_now=True,
        editable=False
    )
    tags = models.CharField(
        verbose_name='dictionary of key-value pairs',
        max_length=100
    )

    def __str__(self):
        """Return a unicode representation of this source."""
        return self.name

    class Meta:
        abstract = True


class SourceSubstance(SourceEmission):
    """An abstract models for source substance emissions."""

    value = models.FloatField(
        default=0,
        verbose_name='source emission'
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.substance.name


class PointSourceSubstance(SourceSubstance):
    """A point-source substance emission."""

    source = models.ForeignKey(
        'PointSource',
        related_name='substances',
        on_delete=models.CASCADE,
        db_index=True
    )

    substance = models.ForeignKey(
        'Substance', on_delete=models.CASCADE,
        related_name='+',
        db_index=True
    )

    class Meta:
        db_table = 'pointsource_substance'


class AreaSourceSubstance(SourceSubstance):
    """A area-source substance emission."""

    source = models.ForeignKey(
        'AreaSource',
        related_name='substances',
        on_delete=models.CASCADE,
        db_index=True
    )

    substance = models.ForeignKey(
        'Substance', on_delete=models.CASCADE,
        related_name='+',
        db_index=True
    )

    class Meta:
        db_table = 'areasource_substance'


class PointSource(SourceBase):
    """A point-source."""

    geom = models.PointField(
        'the position of the point-source',
        srid=SRID,
        geography=True,
        db_index=True
    )

    chimney_height = models.FloatField(
        'chimney height [m]',
        default=0
    )
    chimney_outer_diameter = models.FloatField(
        'chimney outer diameter [m]',
        default=0
    )
    chimney_inner_diameter = models.FloatField(
        'chimney inner diameter [m]',
        default=0
    )
    chimney_gas_speed = models.FloatField(
        'chimney gas speed [m/s]',
        default=0
    )
    chimney_gas_temperature = models.FloatField(
        'chimney gas temperature [deg C]',
        default=0
    )
    house_width = models.IntegerField(
        'house width [m] (to estimate down draft)',
        default=0
    )
    house_height = models.IntegerField(
        'house height [m] (to estimate down draft)',
        default=0
    )

    class Meta:
        default_related_name = 'pointsources'
        db_table = 'pointsource'


class AreaSource(SourceBase):
    """An area source."""

    geom = models.PolygonField(
        'the extent of the area source',
        srid=SRID,
        geography=True,
        db_index=True
    )
    
    class Meta:
        default_related_name = 'areasources'
        db_table = 'areasource'


class RoadClassAttribute(models.Model):
    '''A manadatory attribute of a roadclass.'''

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    name = models.CharField(
        verbose_name='Road class attribute verbose name',
        max_length=CHAR_FIELD_LENGTH,
        unique=True
    )

    label = models.SlugField(
        verbose_name='Road class attribute label',
        max_length=CHAR_FIELD_LENGTH
    )

    order = models.IntegerField(verbose_name='Roadclass attribute ordering')

    class Meta:
        db_table = 'roadclass_attribute'

    def __str__(self):
        return self.label


class RoadClassAttributeValue(models.Model):
    '''Acceptet values for a roadclass attribute.'''

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    roadclass_attribute = models.ForeignKey(
        'RoadClassAttribute',
        on_delete=models.CASCADE,
        related_name='values'
    )

    value = models.CharField(
        verbose_name='Attribute value',
        max_length=60
    )

    class Meta:
        db_table = 'roadclass_attribute_value'
        unique_together = ('roadclass_attribute', 'value')

    def __str__(self):
        return str(self.value)


class RoadClass(models.Model):
    '''A road class.'''

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    properties = models.CharField(
        verbose_name='Road class property dictionary',
        max_length=100,
        unique=True
    )

    class Meta:
        db_table = 'roadclass'
        verbose_name_plural = "Road classes"


class VehicleEF(models.Model):
    """An emission factor for a vehicle on a specific roadclass."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    roadclass = models.ForeignKey(
        'RoadClass',
        on_delete=models.CASCADE,
        related_name='emissionfactors'
    )
    vehicle = models.ForeignKey(
        'Vehicle',
        on_delete=models.CASCADE,
        related_name='emissionfactors'
    )
    fuel = models.ForeignKey(
        'Fuel',
        on_delete=models.CASCADE,
        related_name='+'
    )
    substance = models.ForeignKey(
        'Substance',
        on_delete=models.CASCADE,
        related_name='+'
    )

    freeflow = models.FloatField(default=0)
    saturated = models.FloatField(default=0)
    congested = models.FloatField(default=0)
    stopngo = models.FloatField(default=0)
    coldstart = models.FloatField(default=0)

    class Meta:
        db_table = 'vehicle_ef'
        verbose_name_plural = "Vehicle emission factors"
        unique_together = ('substance', 'vehicle', 'roadclass', 'fuel')

    def __str__(self):
        return 'EF %s, %s, %i' % (
            self.substance.slug, self.fuel.name, self.roadclass.id
        )


class Vehicle(models.Model):
    """A vehicle."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    name = models.CharField(
        max_length=CHAR_FIELD_LENGTH,
        unique=True
    )
    info = models.CharField(
        max_length=CHAR_FIELD_LENGTH, null=True, blank=True
    )
    isheavy = models.BooleanField(default=False)
    max_speed = models.IntegerField(
        null=True, blank=True, default=130,
        choices=((s, f'{s}') for s in range(20, 150, 10))
    )
    activitycode1 = models.ForeignKey(
        'ActivityCode1',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )
    activitycode2 = models.ForeignKey(
        'ActivityCode2',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )
    activitycode3 = models.ForeignKey(
        'ActivityCode3',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'vehicle'

    def __str__(self):
        """Unicode representation of vehicle."""
        return self.name


class Fleet(models.Model):
    """Composition of vehicles."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    name = models.CharField(unique=True, max_length=CHAR_FIELD_LENGTH)

    is_template = models.BooleanField(
        verbose_name='Use fleet composition as a template',
        default=False
    )

    class Meta:
        db_table = 'fleet'

    def __str__(self):
        """Unicode representation of fleet."""
        return self.name

    def heavy_vehicle_share(self):
        """Sum of heavy vehicle fraction in Fleet."""
        share = self.vehicles.filter(
            vehicle__isheavy=True
        ).aggregate(Sum('fraction'))

        return share['fraction__sum'] or 0

    def light_vehicle_share(self):
        """Sum of heavy vehicle fraction in Fleet."""
        return 1 - self.heavy_vehicle_share()


class FleetMember(models.Model):
    """A member vehicle of a fleet."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    fleet = models.ForeignKey(
        'Fleet',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='vehicles'
    )

    vehicle = models.ForeignKey(
        'Vehicle', on_delete=models.CASCADE,
        db_index=True,
        related_name='+'
    )

    timevar = models.ForeignKey(
        'RoadTimevar',
        on_delete=models.PROTECT,
        related_name='+'
    )

    coldstart_timevar = models.ForeignKey(
        'RoadTimevar',
        on_delete=models.PROTECT,
        related_name='+'
    )

    fraction = models.FloatField(default=0.0)
    coldstart_fraction = models.FloatField(default=0.0)

    class Meta:
        db_table = 'fleet_member'
        unique_together = ('fleet', 'vehicle')

    def __str__(self):
        """Unicode representation of fleet member vehicle."""
        return self.vehicle.name


class FleetMemberFuel(models.Model):
    """A fuel used by a fleet member."""

    locid = models.AutoField(
        primary_key=True, auto_created=True, editable=False
    )

    id = models.IntegerField(editable=False, null=True, blank=True)

    updated = models.DateTimeField(
        verbose_name='date and time of action',
        auto_now=True,
        editable=False
    )

    fleet_member = models.ForeignKey(
        'FleetMember',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='fuels'
    )

    fuel = models.ForeignKey(
        'Fuel',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='+'
    )

    fraction = models.FloatField(default=0.0)

    class Meta:
        db_table = 'fleet_member_fuel'


class RoadSource(SourceBase):
    """A road source."""

    geom = models.LineStringField(
        'the road coordinates',
        srid=SRID,
        geography=True,
        db_index=True
    )

    flow = models.IntegerField('Annual average day traffic', default=0)
    nolanes = models.IntegerField('Number of lanes', default=2)
    speed = models.IntegerField(
        'Road sign speed [km/h]', default=70,
        choices=((s, f'{s}') for s in range(20, 150, 10))
    )
    width = models.FloatField('Road width [meters]', default=20.0)
    slope = models.IntegerField(
        'Slope [%]', default=0,
        choices=((s, f'{s}') for s in range(-10, 10))
    )

    heavy_vehicle_share = models.FloatField(
        null=True,
        blank=True
    )

    roadclass = models.ForeignKey(
        'RoadClass',
        on_delete=models.PROTECT,
        related_name='+'
    )

    fleet = models.ForeignKey(
        'Fleet',
        on_delete=models.PROTECT,
        related_name='+',
        null=True,
        blank=True
    )

    congestion_profile = models.ForeignKey(
        'CongestionProfile',
        on_delete=models.PROTECT,
        related_name='+'
    )

    class Meta:
        db_table = 'roadsource'
        default_related_name = 'roads'

    @property
    def light_vehicle_share(self):
        if self.heavy_vehicle_share is None:
            return None
        return 1 - self.heavy_vehicle_share

    def emission(self, substance=None, ac1=None, ac2=None, ac3=None):
        """Calculate emission for a roadsource.

        Default is to calculate emissions for all substances and vehicles

        optional:
            substances: a list of Substances
            ac1: a list of Activitycode1 instances
            ac2: a list of activitycode2 instances
            ac3: a list of activitycode3 instances
        """

        fleet_heavy_vehicle_share = self.fleet.heavy_vehicle_share()

        srid = self.inventory.project.domain.srid
        emis_by_veh_and_subst = {}
        for fleet_member in self.fleet.vehicles.all():
            veh = fleet_member.vehicle

            # Check if vehicle activity codes matches code filters
            # if not, the vehicle is excluded
            if ac1 is not None:
                if veh.activitycode1 is None:
                    continue
                elif not veh.activitycode1.matches(ac1):
                    continue

            if ac2 is not None:
                if veh.activitycode2 is None:
                    continue
                elif not veh.activitycode2.matches(ac2):

                    continue

            if ac3 is not None:
                if veh.activitycode3 is None:
                    continue
                elif not veh.activitycode3.matches(ac3):
                    continue

            conditions = self.congestion_profile.get_fractions(
                fleet_member.timevar
            )

            for fleet_member_fuel in fleet_member.fuels.all():

                emissionfactors = self.roadclass.emissionfactors.filter(
                    vehicle=veh, substance=substance,
                    fuel=fleet_member_fuel.fuel
                )
                for ef in emissionfactors:

                    # if heavy_vehicle_share is specified
                    # the fleet composition is rescaled to match this
                    # Note that if there are only heavy or only light vehicles
                    # in the fleet it is not possible to rescale using share
                    # of heavy traffic from road (should this result in warning
                    # when loading data?)
                    if self.heavy_vehicle_share is not None:
                        if veh.isheavy and fleet_heavy_vehicle_share != 0:
                            vehicle_fraction_corr_factor = (
                                self.heavy_vehicle_share /
                                fleet_heavy_vehicle_share
                            )
                        elif not veh.isheavy and  \
                                fleet_heavy_vehicle_share != 1:
                            vehicle_fraction_corr_factor = (
                                self.light_vehicle_share /
                                (1 - fleet_heavy_vehicle_share)
                            )
                        else:
                            # if the share of light/heavy vehicles is 0
                            vehicle_fraction_corr_factor = 0
                    else:
                        vehicle_fraction_corr_factor = 1

                    emis = (
                        self.flow *  # annual average day vehicle flow
                        self.geom.transform(srid, clone=True).length *
                        0.001 *  # km
                        vehicle_fraction_corr_factor *
                        fleet_member.fraction *
                        fleet_member_fuel.fraction *
                        (
                            ef.coldstart * fleet_member.coldstart_fraction +

                            ef.freeflow *
                            conditions['freeflow'] +

                            ef.saturated *
                            conditions['saturated'] +

                            ef.congested *
                            conditions['congested'] +

                            ef.stopngo *
                            conditions['stopngo']
                        ) *
                        0.001 / (3600 * 24)  # convert to g/s
                    )
                    if veh.id not in emis_by_veh_and_subst:
                        emis_by_veh_and_subst[veh.id] = {}
                    if ef.substance.id not in emis_by_veh_and_subst[veh.id]:
                        emis_by_veh_and_subst[veh.id][ef.substance.id] = emis
                    else:
                        emis_by_veh_and_subst[veh.id][ef.substance.id] += emis

        return emis_by_veh_and_subst


class GridSourceSubstance(SourceSubstance):
    """A substance emission of a grid-source ."""

    # TODO: add controls that band exists in GridSource geom

    source = models.ForeignKey(
        'GridSource',
        related_name='substances',
        on_delete=models.CASCADE,
        db_index=True
    )

    band = models.IntegerField(
        verbose_name='raster band index',
        default=0
    )

    substance = models.ForeignKey(
        'Substance', on_delete=models.CASCADE,
        related_name='+',
        db_index=True
    )

    class Meta:
        db_table = 'gridsource_substance'


class GridSourceActivity(SourceActivity):
    """An emitting activity for a grid-source."""

    # TODO: add controls that band exists in GridSource geom

    source = models.ForeignKey(
        'GridSource',
        related_name='activities',
        on_delete=models.CASCADE,
        db_index=True
    )

    band = models.IntegerField(
        verbose_name='raster band index',
        default=0
    )

    class Meta:
        db_table = 'gridsource_activity'


class GridSource(SourceBase):
    """A grid-source.

    the geom referes to a raster of varying srid
    due to limitations in django, a dummy srid is specified
    """

    raster_file = models.CharField(
        verbose_name='Path of raster file',
        max_length=100
    )

    height = models.FloatField(verbose_name='height above ground', default=2.0)

    class Meta:
        db_table = 'gridsource'
        
