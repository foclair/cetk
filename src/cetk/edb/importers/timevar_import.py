import numpy as np
from django.db import IntegrityError

from cetk.edb.models import ColdstartTimevar, FlowTimevar, Timevar

from .utils import import_error, worksheet_to_dataframe


def import_timevarsheet(workbook, validation=False, sheetname="Timevar"):
    return_message = []
    timevar_data = workbook[sheetname].values
    df_timevar = worksheet_to_dataframe(timevar_data)
    if sheetname == "Timevar":
        keyname = "emission"
    if sheetname == "FlowTimevar":
        keyname = "flow"
    if sheetname == "ColdstartTimevar":
        keyname = "coldstart"
    timevar_dict = {keyname: {}}

    # NB this only works if Excel file has exact same format
    nr_timevars = (len(df_timevar["ID"]) + 1) // 27
    for i in range(nr_timevars):
        label = df_timevar["ID"][i * 27]
        typeday = np.asarray(
            df_timevar[
                [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                ]
            ][i * 27 : i * 27 + 24]
        )
        month = np.asarray(df_timevar.iloc[i * 27 + 25, 2:14])
        typeday_str = np.array2string(typeday).replace("\n", "").replace(" ", ", ")
        month_str = np.array2string(month).replace("\n", "").replace(" ", ", ")
        timevar_dict[keyname].update(
            {label: {"typeday": typeday_str, "month": month_str}}
        )
    tv, return_append = import_timevars(
        timevar_dict, overwrite=True, validation=validation
    )
    return_message += return_append
    return_dict = {"timevar": {"updated or created": len(tv[keyname])}}
    return return_dict, return_message


def import_timevars(timevar_data, overwrite=False, validation=False):
    """import time-variation profiles."""

    # Timevar instances must not be created by bulk_create as the save function
    # is overloaded to calculate the normation constant.
    def make_timevar(data, timevarclass, subname=None, validation=False):
        retdict = {}
        for name, timevar_data in data.items():
            try:
                typeday = timevar_data["typeday"]
                month = timevar_data["month"]
                if type(typeday) == list:
                    typeday = str(typeday)
                if type(month) == list:
                    month = str(month)
                if overwrite:
                    newobj, _ = timevarclass.objects.update_or_create(
                        name=name,
                        defaults={"typeday": typeday, "month": month},
                    )
                else:
                    try:
                        newobj = timevarclass.objects.create(
                            name=name, typeday=typeday, month=month
                        )
                    except IntegrityError:
                        raise IntegrityError(
                            f"{timevarclass.__name__} {name} "
                            f"already exist in inventory."
                        )
                retdict[name] = newobj
            except KeyError:
                return_message.append(
                    import_error(
                        f"Invalid specification of timevar {name}"
                        f", are 'typeday' and 'month' given?",
                        validation=validation,
                    )
                )
        return retdict

    return_message = []
    timevars = {}
    for vartype, subdict in timevar_data.items():
        if vartype == "emission":
            timevars.setdefault("emission", {}).update(
                make_timevar(timevar_data[vartype], Timevar)
            )
        elif vartype == "flow":
            timevars.setdefault("flow", {}).update(
                make_timevar(timevar_data[vartype], FlowTimevar)
            )
        elif vartype == "coldstart":
            timevars.setdefault("coldstart", {}).update(
                make_timevar(timevar_data[vartype], ColdstartTimevar)
            )
        else:
            return_message.append(
                import_error(
                    f"invalid time-variation type '{vartype}' specified",
                    validation=validation,
                )
            )
    return timevars, return_message
