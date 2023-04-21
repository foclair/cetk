# Contributing

  * [Library scope](#library-scope)
  * [Dependency management](#dependency-management)
  * [Testing](#testing)

## Library scope

## Installation

``` console
$ git clone https://git.smhi.se/foclair/etk.git
$ cd etk
$ python3.9 -m venv --prompt gadget .venv
$ . .venv/bin/activate
$ pip install -U pip setuptools wheel
$ pip install -r dev/requirements.txt
$ pre-commit install
```

This environment won't be able to run the unit tests however.  Use the
top-level [requirements.txt](requirements.txt) file for this.


### Dependency management

Dependencies are organized in the following files:

| Filename                           | Contents                                                                  |
| ---------------------------------- | ------------------------------------------------------------------------- |
| constraints.txt                    | Version constraints for pinned requirements                               |
| requirements.txt                   | Pinned requirements for _using_ etk (don't edit)                   |
| setup.py                    	     | Loose requirements for _using_ etk

