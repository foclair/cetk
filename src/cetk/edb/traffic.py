import pandas as pd

from cetk.edb.models import CongestionProfile

LoS = CongestionProfile.LevelOfService
# We express the adjustments as differences to be able to vectorize
# the operations in get_traffic_velocity().
VELOCITY_ADJUSTMENTS = {
    20: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: +10, LoS.SATURATED: -5},
        "heavy": {LoS.FREEFLOW: +10, LoS.HEAVY: +10, LoS.SATURATED: -5},
    },
    30: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: +10, LoS.SATURATED: -5},
        "heavy": {LoS.FREEFLOW: +10, LoS.HEAVY: +10, LoS.SATURATED: -5},
    },
    40: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: 0, LoS.SATURATED: -10},
        "heavy": {LoS.FREEFLOW: +5, LoS.HEAVY: 0, LoS.SATURATED: -10},
    },
    50: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: 0, LoS.SATURATED: -10},
        "heavy": {LoS.FREEFLOW: +5, LoS.HEAVY: 0, LoS.SATURATED: -10},
    },
    60: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: 0, LoS.SATURATED: -10},
        "heavy": {LoS.FREEFLOW: +5, LoS.HEAVY: 0, LoS.SATURATED: -10},
    },
    70: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: 0, LoS.SATURATED: -10},
        "heavy": {LoS.FREEFLOW: 0, LoS.HEAVY: 0, LoS.SATURATED: -10},
    },
    80: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: 0, LoS.SATURATED: -10},
        "heavy": {LoS.FREEFLOW: 0, LoS.HEAVY: 0, LoS.SATURATED: -10},
    },
    90: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: 0, LoS.SATURATED: -15},
        "heavy": {LoS.FREEFLOW: 0, LoS.HEAVY: 0, LoS.SATURATED: -15},
    },
    100: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: 0, LoS.SATURATED: -20},
        "heavy": {LoS.FREEFLOW: -10, LoS.HEAVY: -10, LoS.SATURATED: -20},
    },
    110: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: -10, LoS.SATURATED: -25},
        "heavy": {LoS.FREEFLOW: -20, LoS.HEAVY: -20, LoS.SATURATED: -25},
    },
    120: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: -10, LoS.SATURATED: -30},
        "heavy": {LoS.FREEFLOW: -30, LoS.HEAVY: -30, LoS.SATURATED: -30},
    },
    130: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: -10, LoS.SATURATED: -40},
        "heavy": {LoS.FREEFLOW: -40, LoS.HEAVY: -40, LoS.SATURATED: -40},
    },
    140: {
        "light": {LoS.FREEFLOW: +10, LoS.HEAVY: -10, LoS.SATURATED: -40},
        "heavy": {LoS.FREEFLOW: -50, LoS.HEAVY: -50, LoS.SATURATED: -50},
    },
}


def los_to_velocity(los_series, posted_speed):
    """derive dynamic vehicle speed from level of service and posted speed."""
    adjustments = VELOCITY_ADJUSTMENTS[posted_speed]
    v_li = pd.Series(posted_speed, index=los_series.index, name="V(li)")
    for los, delta in adjustments["light"].items():
        v_li[los_series == los] += delta
    v_li[los_series == LoS.STOPNGO] = 10 if posted_speed < 70 else 20
    v_he = pd.Series(posted_speed, index=los_series.index, name="V(he)")
    for los, delta in adjustments["heavy"].items():
        v_he[los_series == los] += delta
    v_he[los_series == LoS.STOPNGO] = 10 if posted_speed < 70 else 20
    return v_li, v_he
