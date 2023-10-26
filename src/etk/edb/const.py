WGS84_SRID = 4326
CHAR_FIELD_LENGTH = 100
CODE_FIELD_LENGTH = 50
DUMMY_SRID = 3857  # TODO is dummy used?
NODATA = -9999.0

# sheet names which are valid for data import
# NOTE these have to be kept updated manually
SHEET_NAMES = [
    "Timevar",
    "PointSource",
    "Activity",
    "EmissionFactor",
    "ActivityCode",
    "CodeSet",
]
# TODO add log warning if a sheet name exists in file to be imported
# which is not in SHEET_NAMES
