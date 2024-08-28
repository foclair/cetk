# from django.db import transaction

# from cetk.edb import models


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
