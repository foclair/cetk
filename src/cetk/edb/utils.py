"""EDB utility functions."""


def delete_sources(sourcetype, id_list):
    """Delete source from database. If source does not exist, go to next id but raise
    error after all ids have been tried."""
    not_deleted = []
    for source_id in id_list:
        try:
            sourcetype.objects.get(id=source_id).delete()
        except sourcetype.DoesNotExist:
            not_deleted.append(source_id)
    if not_deleted:
        raise ValueError(
            f"Cannot delete {sourcetype.sourcetype}(s) "
            f"with id {not_deleted}, do not exist. \n"
        )
