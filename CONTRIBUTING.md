# Contributing

  * [Library scope](#library-scope)
  * [Dependency management](#dependency-management)
  * [Testing](#testing)

## Library scope

## Installation
# Linux
``` console
$ git clone https://git.smhi.se/foclair/etk.git
$ cd etk
$ python3.9 -m venv --prompt etk .venv
$ . .venv/bin/activate
$ pip install -U pip setuptools wheel
$ pip install -i https://test.pypi.org/simple/ rastafari==0.2.2
$ pip install -r requirements.txt
$ pip install djangorestframework
$ pre-commit install
```
# Windows
``` console
$ git clone https://git.smhi.se/foclair/etk.git
$ cd etk
$ python3.9 -m venv --prompt etk .venv
$ . .venv/Scripts/activate
$ pip install pre-commit
$ pip install -e .
```
# General
To run pre-commit on all files:
``` console
$ pre-commit run --all-files
```

### Dependency management

Dependencies are organized in the following files:
TODO not all of these files exist here?

| Filename                           | Contents                                                                  |
| ---------------------------------- | ------------------------------------------------------------------------- |
| constraints.txt                    | Version constraints for pinned requirements                               |
| requirements.txt                   | Pinned requirements for _using_ etk (don't edit)                   |
| setup.py                    	     | Loose requirements for _using_ etk
