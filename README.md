# Emission ToolKit cetk

Emission toolkit for command line to import, validate, edit and analyse emissions.
Used in QGIS Plugin Eclair. This package is maintained by [Eef van Dongen][] at SMHI.

[Eef van Dongen]: mailto:eef.vandongen@smhi.se

## Installation
```
python3 -m venv --prompt cetk .venv
. .venv/bin/activate
python -m pip install -r ./requirements.txt
python -m pip install -e .
```
Check that installation was successful and receive information on how to use the toolkit:
```
cetk -h
```

Before using the toolkit, initialize the template database by:
```
cetkmanage migrate
```

If you did not change the default path, this should create
`~/.config/eclair/eclair.gpkg`

New databases can now be created by copying the template database. This is easiest done using the cetk command:
```
cetk create /home/myuser/mydatabase.gpkg
```

To use a specific database, set environment variable "CETK_DATABASE_PATH".
```
export CETK_DATABASE_PATH="/home/myuser/mydatabase.gpkg"
```

For more verbose logging, set environment variable CETK_DEBUG=1:
```
export CETK_DEBUG=1
```

## Contributing

### Environment
Install pre-commit hooks:

```
. .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
```

### Testing

Run tests by
```
pytest
```
### Update requirements

Install pip-tools:
```
pip install pip-tools
```
Update requirements.txt and requirements-dev.txt by:
```
./compilereqs
```
