from cetk.edb.models import ActivityCode, CodeSet, VerticalDist

from .utils import import_error, worksheet_to_dataframe


def import_codesetsheet(workbook, validation):
    return_message = []
    return_dict = {}
    nr_codesets = CodeSet.objects.count()
    data = workbook["CodeSet"].values
    df_codeset = worksheet_to_dataframe(data)
    slugs = df_codeset["slug"]
    update_codesets = []
    create_codesets = {}
    for row_nr, slug in enumerate(slugs):
        try:
            codeset = CodeSet.objects.get(slug=slug)
            setattr(codeset, "name", df_codeset["name"][row_nr])
            setattr(codeset, "description", df_codeset["description"][row_nr])
            update_codesets.append(codeset)
        except CodeSet.DoesNotExist:
            if nr_codesets + len(create_codesets) < 3:
                codeset = CodeSet(
                    name=df_codeset["name"][row_nr],
                    slug=slug,
                    description=df_codeset["description"][row_nr],
                )
                if slug not in create_codesets:
                    create_codesets[slug] = codeset
            else:
                return_message.append(
                    import_error(
                        "Trying to import a new codeset," " but can have maximum 3.",
                        validation=validation,
                    )
                )

    CodeSet.objects.bulk_create(create_codesets.values())
    CodeSet.objects.bulk_update(
        update_codesets,
        [
            "name",
            "description",
        ],
    )
    return_dict = {
        "codeset": {
            "updated": len(update_codesets),
            "created": len(create_codesets),
        }
    }
    return return_dict, return_message


def import_activitycodesheet(workbook, validation):
    return_message = []
    data = workbook["ActivityCode"].values
    df_activitycode = worksheet_to_dataframe(data)
    update_activitycodes = []
    create_activitycodes = {}
    for row_key, row in df_activitycode.iterrows():
        row_dict = row.to_dict()
        try:
            codeset = CodeSet.objects.get(slug=row_dict["codeset_slug"])
            if "vertical_distribution_slug" in row_dict:
                if row_dict["vertical_distribution_slug"] is not None:
                    try:
                        vdist = VerticalDist.objects.get(
                            slug=row_dict["vertical_distribution_slug"]
                        )
                        vdist_id = vdist.id
                    except VerticalDist.DoesNotExist:
                        return_message.append(
                            import_error(
                                f"Trying to import an activity-code "
                                "from row '{row_key}' but "
                                "Vertical Distribution "
                                f"'{row_dict['vertical_distribution_slug']}'"
                                " is not defined.",
                                validation=validation,
                            )
                        )
                else:
                    vdist_id = None
            else:
                vdist_id = None
            try:
                activitycode = ActivityCode.objects.get(
                    code_set_id=codeset.id, code=row_dict["activitycode"]
                )
                setattr(activitycode, "label", row_dict["label"])
                setattr(activitycode, "vertical_dist_id", vdist_id)
                update_activitycodes.append(activitycode)
            except ActivityCode.DoesNotExist:
                activitycode = ActivityCode(
                    code=row_dict["activitycode"],
                    label=row_dict["label"],
                    code_set_id=codeset.id,
                    vertical_dist_id=vdist_id,
                )
                create_activitycodes[row_dict["activitycode"]] = activitycode
        except CodeSet.DoesNotExist:
            return_message.append(
                import_error(
                    f"Trying to import an activity code from row '{row_key}'"
                    f"but CodeSet '{row_dict['codeset_slug']}' is not defined.",
                    validation=validation,
                )
            )
    ActivityCode.objects.bulk_create(create_activitycodes.values())
    ActivityCode.objects.bulk_update(
        update_activitycodes,
        [
            "label",
            "vertical_dist_id",
        ],
    )
    return_dict = {
        "activitycode": {
            "updated": len(update_activitycodes),
            "created": len(create_activitycodes),
        }
    }
    return return_dict, return_message
