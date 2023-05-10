# Contributing

  * [Library scope](#library-scope)
  * [Dependency management](#dependency-management)
  * [Testing](#testing)

## Library scope

## Installation

``` console
$ git clone https://git.smhi.se/foclair/etk.git
$ cd etk
$ python3.9 -m venv --prompt etk .venv
$ . .venv/bin/activate
$ pip install -U pip setuptools wheel
$ pip install -r requirements.txt
$ pre-commit install
```
To run pre-commit on all files:
``` console
$ pre-commit run --all-files
```

### Dependency management

Dependencies are organized in the following files:
TODO these files do not exist here?

| Filename                           | Contents                                                                  |
| ---------------------------------- | ------------------------------------------------------------------------- |
| constraints.txt                    | Version constraints for pinned requirements                               |
| requirements.txt                   | Pinned requirements for _using_ etk (don't edit)                   |
| setup.py                    	     | Loose requirements for _using_ etk
