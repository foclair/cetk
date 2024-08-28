"""signals issued by edb."""

from typing import Union

from django.db.backends.signals import connection_created
from django.dispatch import receiver

DEFAULT_TRAFFIC_CONDITIONS = str(24 * [7 * [1.0]])
DEFAULT_TRAFFIC_FLOW = str(24 * [7 * [100.0]])


def condition_weight(
    cond_str: Union[str, None],
    typeday_str: Union[str, None],
    typeday_sum: Union[float, None],
    cond: int,
):
    """
    calculate fraction of week with a given traffic condition (level of service).
    """

    # CongestionProfile.traffic condition and FlowTimevar.typeday
    # are arrays formatted as strings to alow storing in sqlite

    # They are converted to sequences of floats
    cond_str = cond_str or DEFAULT_TRAFFIC_CONDITIONS
    typeday_str = typeday_str or DEFAULT_TRAFFIC_FLOW

    hourly_conditions = map(
        float, cond_str.replace("[", "").replace("]", "").split(",")
    )
    hourly_flow = map(float, typeday_str.replace("[", "").replace("]", "").split(","))

    # filter hours with a given level of service, and sum flow during those hours
    veh_hours_with_cond = sum(
        flow for level, flow in zip(hourly_conditions, hourly_flow) if level == cond
    )
    return veh_hours_with_cond / typeday_sum


@receiver(connection_created)
def extend_sqlite(connection=None, **kwargs):
    connection.connection.create_function("condition_weight", 4, condition_weight)
