# Eclair

Emission toolkit to import, validate, edit and analyse emissions.

## Installation
See also CONTRIBUTING.md for installation guidelines, unclear whether that is updated?
```
python3 -m venv --prompt etk .venv
. .venv/bin/activate
export PIP_EXTRA_INDEX_URL=https://gitlab.smhi.se/api/v4/projects/3495/packages/pypi/simple
python -m pip install -r ./requirements.txt
python -m pip install -e .
```
Check that installation was successful and receive information on how to use the toolkit:
```
python manage.py -h
```

Get started by
```
./manage.py makemigrations
./manage.py migrate
```
If you did not change the default path, then the migrate command should create
`~/.config/eclair/eclair.sqlite`

Run tests by
```
python -m pip install pytest-django
pytest ./tests/edb/test_models.py
```
