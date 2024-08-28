"""Unit tests of custom sqlite functions."""

from django.db import connection

from cetk.edb.signals import condition_weight


def test_condition_weight(test_flowtimevar, congestionprofiles):

    congestion_profile1 = congestionprofiles[0]

    weight_freeflow = condition_weight(
        congestion_profile1.traffic_condition,
        test_flowtimevar.typeday,
        test_flowtimevar.typeday_sum,
        1,
    )
    assert weight_freeflow == 1.0

    weight_heavy = condition_weight(
        congestion_profile1.traffic_condition,
        test_flowtimevar.typeday,
        test_flowtimevar.typeday_sum,
        2,
    )
    assert weight_heavy == 0

    weight_saturated = condition_weight(
        congestion_profile1.traffic_condition,
        test_flowtimevar.typeday,
        test_flowtimevar.typeday_sum,
        3,
    )
    assert weight_saturated == 0

    weight_stopngo = condition_weight(
        congestion_profile1.traffic_condition,
        test_flowtimevar.typeday,
        test_flowtimevar.typeday_sum,
        4,
    )
    assert weight_stopngo == 0


def test_apply_condition_weight(test_flowtimevar, congestionprofiles):
    cur = connection.cursor()
    recs = cur.execute(
        """
        SELECT c.id as congestion_id, t.id as timevar_id,
        condition_weight(c.traffic_condition, t.typeday, t.typeday_sum, 1) as freeflow,
        condition_weight(c.traffic_condition, t.typeday, t.typeday_sum, 2) as heavy,
        condition_weight(c.traffic_condition, t.typeday, t.typeday_sum, 3) as saturated,
        condition_weight(c.traffic_condition, t.typeday, t.typeday_sum, 4) as stopngo
        FROM edb_flowtimevar as t
        CROSS JOIN edb_congestionprofile as c
        """
    ).fetchall()
    assert recs[0][2] == 1.0
    assert recs[0][3] == 0.0
