# Eclair

Emission toolkit to import, validate, edit and analyse emissions.

## Installation
```
python3 -m venv --prompt etk .venv
. .venv/bin/activate
export PIP_EXTRA_INDEX_URL=https://gitlab.smhi.se/api/v4/projects/3495/packages/pypi/simple
python -m pip install -r ./requirements.txt
python -m pip install -e .
```
Check that installation was successful and receive information on how to use the toolkit:
```
etk -h
```

Before using the toolkit, initialize the template database by:
```
etkmanage migrate
```

If you did not change the default path, this should create
`~/.config/eclair/eclair.sqlite`

New databases can now be created by copying the template database. This is easiest done using the etk command:
```
etk create /home/myuser/mydatabase.sqlite
```

To use a specific database, set environment variable "ETK_DATABASE_PATH".
```
export ETK_DATABASE_PATH="/home/myuser/mydatabase.sqlite"
```

For more verbose logging, set environment variable ETK_DEBUG=1:
```
export ETK_DEBUG=1
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
