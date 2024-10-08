# Generated by Django 1.11.11 on 2018-03-28 08:36
from __future__ import unicode_literals

from django.db import migrations
from django.utils.text import slugify

# slug, name and long_name of all substances
# these are also used to create corresponding emission and concentration params
SUBSTANCES = (
    ("activity", "activity", "Activity"),
    ("As", "As", "Arsenic"),
    ("BC", "BC", "Black Carbon"),
    ("BaP", "BaP", "Benzo[a]pyrene"),
    ("Cd", "Cd", "Cadmium"),
    ("Cr", "Cr", "Chromium"),
    ("Cu", "Cu", "Copper"),
    ("C6H6", "Benzene", "Benzene"),
    ("CH4", "Methane", "Methane"),
    ("CO", "CO", "Carbon monoxide"),
    ("CO2", "CO2", "Carbon dioxide"),
    (
        "Dioxin",
        "Dioxin",
        "Dioxin",
    ),
    ("HC", "Hydrocarbons", "Hydrocarbons"),
    ("HCB", "HCB", "Hexachlorobenzene"),
    ("HFC", "HFC", "Hydrofluorocarbons"),
    ("Hg", "Hg", "Mercury"),
    ("N2O", "N2O", "Nitrous oxide"),
    ("NH3", "NH3", "Ammonia"),
    ("Ni", "Ni", "Nickel"),
    ("NMHC", "NMHC", "Non-methane hydrocarbons"),
    ("NMVOC", "NMVOC", "Non-methane volatile organic compound"),
    ("NOx", "NOx", "Nitrogen oxides (as NO2)"),
    ("NO2", "NO2", "Nitrogen dioxide"),
    ("NO", "NO", "Nitrogen monooxide"),
    ("O3", "Ozone", "Ozone"),
    ("PAH4", "PAH4", "Sum of 4 polycyclic aromatic hydrocarbons"),
    ("Pb", "Pb", "Lead"),
    ("PFC", "PFC", "Perfluorocarbons"),
    ("PM10", "PM10", "Particulate matter < 10 micrometers in diameter"),
    ("PM25", "PM2.5", "Particulate matter < 2.5 micrometers in diameter"),
    ("PM10resusp", "PM10resusp", "Resuspended particles < 10 micrometers in diameter"),
    (
        "PM10wear",
        "PM10wear",
        "Particles < 10 micrometers in diameter from road, tyre and break wear",
    ),
    (
        "PM25resusp",
        "PM2.5resusp",
        "Resuspended particles < 2.5 micrometers in diameter",
    ),
    (
        "PM25wear",
        "PM2.5wear",
        "Particles < 2.5 micrometers in diameter from road, tyre and break wear",
    ),
    ("PN", "PN", "Particle Number"),
    ("Se", "Se", "Selenium"),
    ("PCB", "PCB", "Polychlorinated biphenyls"),
    ("SF6", "SF6", "Sulfur Hexafluoride"),
    ("SO2", "SO2", "Sulphur dioxide"),
    ("SOx", "SOx", "Sulphur oxides (as SO2)"),
    ("traffic_work", "traffic work", "Traffic work"),
    ("TSP", "TSP", "Total Suspended Particles"),
    ("Zn", "Zn", "Zinc"),
)

# quantity, slug, name
PARAMETERS = (
    ("temperature", "dtmp", "Air temperature difference"),
    ("temperature", "temp", "Air temperature"),
    ("wind speed", "wspd", "Wind speed"),
    ("wind direction", "wdir", "Wind direction"),
    ("radiation", "netr", "Net radiation"),
    ("radiation", "glob", "Global radiation"),
    ("cloud cover", "tcc", "Total Cloud Cover"),
    ("pressure", "pres", "Pressure"),
    ("pressure", "psea", "Pressure at sea level"),
    ("relative humidity", "rhum", "Relative Humidity"),
    ("1 hour precipitation", "1h_prec", "1 hour Precipitation"),
    ("1 hour snow", "1h_snow", "1 hour Snow"),
    ("mixing height", "zi", "Mixing height"),
    ("albedo", "albedo", "Albedo"),
    ("roughness length", "z0", "Roughness length"),
    ("traffic condition", "traffic_condition", "Traffic condition"),
    ("landuse class", "landuse_class", "Landuse class"),
    ("length", "lmo", "Monin Obukhov Length"),
    ("height", "height", "height"),
    ("height", "z_sl", "surface layer height"),
    ("heat flux", "h_sens", "Sensible heat flux"),
    ("scale", "theta_star", "Potential temperature scale"),
    ("scale", "u_star", "Friction velocity"),
    ("scale", "h_star", "heat flux scale"),
    ("scale", "w_star", "convective velocity scale"),
    ("dummy", "dummy", "dummy"),
)


def auto_name_parameter(instance):
    quantity = instance.quantity.capitalize()
    if instance.substance is not None:
        instance.name = f"{quantity} {instance.substance.name}"
    else:
        instance.name = quantity


def auto_slug_parameter(instance):
    if instance.substance is not None:
        quantity = slugify(instance.quantity)
        instance.slug = f"{quantity}_{instance.substance.slug}"
    else:
        instance.slug = slugify(instance.name)


def create_parameters(apps, schema_editor):
    Substance = apps.get_model("edb", "Substance")
    Parameter = apps.get_model("edb", "Parameter")

    # create substances and related parameters
    for slug, name, long_name in SUBSTANCES:
        substance = Substance.objects.create(slug=slug, name=name, long_name=long_name)

        # traffic work is created as 'traffic' parameter instead of 'emission'
        if slug == "traffic_work":
            Parameter.objects.create(
                quantity="traffic",
                slug="traffic_work",
                name="Traffic work",
                substance=substance,
            )
            continue

        # save is not called in migrations
        # and model methods are not available
        emis = Parameter(quantity="emission", substance=substance)
        auto_name_parameter(emis)
        auto_slug_parameter(emis)
        emis.save()

        conc = Parameter(quantity="concentration", substance=substance)
        auto_name_parameter(conc)
        auto_slug_parameter(conc)
        conc.save()

    # create generic parameters
    for quantity, slug, name in PARAMETERS:
        Parameter.objects.create(quantity=quantity, name=name, slug=slug)


class Migration(migrations.Migration):
    dependencies = [("edb", "0001_initial")]

    operations = [migrations.RunPython(create_parameters)]
