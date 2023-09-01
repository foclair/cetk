# from django.db import transaction

# from etk.edb import models


def copy_model_instance(instance, **updated_fields):
    """Create a copy of a model instance in the database."""
    meta = instance._meta
    copy = meta.model(
        **{
            f.name: updated_fields.get(f.name, getattr(instance, f.name))
            for f in meta.get_fields()
            if not (f.one_to_many or f.many_to_many)
        }
    )
    copy.pk = None
    copy.save()
    return copy


# not necessary as we only have one domain?
# @transaction.atomic  # TODO is this line necessary?
# def copy_codeset(src, tgt):
#     """Copy activitycodes from one codeset to another."""
#     vertical_dists = {dist.name: dist for dist in tgt.domain.vertical_dists.all()}

#     def update_and_drop_id(instance):
#         instance.id = None
#         instance.code_set = tgt
#         if instance.vertical_dist is not None:
#             try:
#                 instance.vertical_dist = vertical_dists[instance.vertical_dist.name]
#             except KeyError:
#                 raise KeyError(  # or import incompatible baseset??
#                     f"Vertical distribution '{instance.vertical_dist.name}' not found"
#                     f"in domain '{tgt.domain.slug}' of target code-set, use "
#                     "'copy_vertical_distributions' to ensure they are available"
#                 )
#         return instance

#     codes = [update_and_drop_id(code) for code in src.codes.all()]
#     models.ActivityCode.objects.bulk_create(codes)
