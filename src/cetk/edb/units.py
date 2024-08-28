"""Utility functions for managing emission units."""


MASS_UNIT_TO_KILOGRAMS = {
    "ng": 1.0e-12,
    "µg": 1.0e-9,  # support both micro letter and small greek letter mu
    "μg": 1.0e-9,
    "microg": 1.0e-9,
    "mg": 1.0e-6,
    "g": 0.001,
    "hg": 0.1,
    "kg": 1.0,
    "ton": 1000,
    "tonne": 1000,
    "t": 1000,
    "Mg": 1000,
    "kt": 1.0e6,
    "Gg": 1.0e6,
    "Tg": 1.0e9,
}

TIME_UNIT_TO_SECONDS = {
    "ms": 1.0e-3,
    "s": 1.0,
    "min": 60,
    "h": 3600,
    "hour": 3600,
    "day": 3600 * 24,
    "year": 3600 * 24 * 365.25,
    "yr": 3600 * 24 * 365.25,
}

ENERGY_UNIT_TO_GIGAJOULES = {
    "J": 1.0e-39,
    "kWh": 3.6e-3,
    "MWh": 3.6,
    "GJ": 1.0,
}

LENGTH_UNIT_TO_METERS = {"km": 1000, "m": 1.0}


def emission_unit_to_si(value, unit):
    """convert value to si-units (kg/s)."""

    try:
        mass_unit, time_unit = unit.split("/")
    except ValueError:
        raise ValueError(f"conversion of emission unit {unit} is not supported")

    try:
        return (
            value * MASS_UNIT_TO_KILOGRAMS[mass_unit] / TIME_UNIT_TO_SECONDS[time_unit]
        )
    except KeyError:
        if mass_unit not in MASS_UNIT_TO_KILOGRAMS:
            raise KeyError(f"no conversion factor defined for mass-unit {mass_unit}")
        else:
            raise KeyError(f"no conversion factor defined for time-unit {time_unit}")


def emis_conversion_factor_from_si(unit):
    try:
        mass_unit, time_unit = unit.split("/")
    except ValueError:
        raise ValueError(f"conversion of emission unit {unit} is not supported")

    try:
        return TIME_UNIT_TO_SECONDS[time_unit] / MASS_UNIT_TO_KILOGRAMS[mass_unit]
    except KeyError:
        if mass_unit not in MASS_UNIT_TO_KILOGRAMS:
            raise KeyError(f"no conversion factor defined for mass-unit {mass_unit}")
        else:
            raise KeyError(f"no conversion factor defined for time-unit {time_unit}")


def vehicle_ef_unit_to_si(value, mass_unit, length_unit):
    """convert mass/(veh*length) to si-units kg/(veh*m)."""

    try:
        return (
            value
            * MASS_UNIT_TO_KILOGRAMS[mass_unit]
            / LENGTH_UNIT_TO_METERS[length_unit]
        )
    except KeyError:
        if mass_unit not in MASS_UNIT_TO_KILOGRAMS:
            raise KeyError(f"no conversion factor defined for mass-unit {mass_unit}")
        else:
            raise KeyError(
                f"no conversion factor defined for length-unit {length_unit}"
            )


def activity_rate_unit_to_si(value, unit):
    """convert activity rate unit to si-units [s⁻¹]."""

    activity_unit, time_unit = unit.split("/")
    try:
        return value / TIME_UNIT_TO_SECONDS[time_unit]
    except KeyError:
        raise KeyError(f"no conversion factor defined for time-unit {time_unit}")


def activity_rate_unit_from_si(value, unit):
    """convert activity rate from si-units [s⁻¹]."""

    activity_unit, time_unit = unit.split("/")
    try:
        return value * TIME_UNIT_TO_SECONDS[time_unit]
    except KeyError:
        raise KeyError(f"no conversion factor defined for time-unit {time_unit}")


def activity_ef_unit_to_si(value, unit):
    """convert activity emission factor unit to si-units [kg]."""

    mass_unit, activity_unit = unit.split("/")
    try:
        return value * MASS_UNIT_TO_KILOGRAMS[mass_unit]
    except KeyError:
        raise KeyError(f"no conversion factor defined for mass-unit {mass_unit}")


def heating_demand_unit_to_si(value, unit):
    """convert heating demand unit to (almost) si-units [GJ s⁻¹]."""

    energy_unit, time_unit = unit.split("/")
    try:
        return (
            value
            * ENERGY_UNIT_TO_GIGAJOULES[energy_unit]
            / TIME_UNIT_TO_SECONDS[time_unit]
        )
    except KeyError:
        if time_unit not in TIME_UNIT_TO_SECONDS:
            raise KeyError(f"no conversion factor defined for time-unit {time_unit}")
        else:
            raise KeyError(
                f"no conversion factor defined for energy-unit {energy_unit}"
            )


def heating_ef_unit_to_si(value, unit):
    """convert heating emission factor unit to (almost) si-units [kg/GJ]."""

    mass_unit, energy_unit = unit.split("/")
    try:
        return (
            value
            * MASS_UNIT_TO_KILOGRAMS[mass_unit]
            / ENERGY_UNIT_TO_GIGAJOULES[energy_unit]
        )
    except KeyError:
        if mass_unit not in MASS_UNIT_TO_KILOGRAMS:
            raise KeyError(f"no conversion factor defined for mass-unit {mass_unit}")
        else:
            raise KeyError(
                f"no conversion factor defined for energy-unit {energy_unit}"
            )
