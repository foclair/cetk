"""Nox configuration for cetk."""

import os
from pathlib import Path

import nox

nox.needs_version = ">=2024.03.02"
nox.options.default_venv_backend = "uv|virtualenv"
nox.options.sessions = ["django", "migrations", "test", "test-lowest"]

TEST_REQUIREMENTS = ["pytest", "pytest-cov", "pytest-django"]


@nox.session(name="requirements-dev")
def requirements_dev(session):
    """Re-compile the development requirements"""
    session.install("-c", "requirements-dev.txt", "uv")
    pip_compile(session, "requirements-dev.txt", "requirements-dev.in")


@nox.session(name="constraints-lowest", python="3.9")
def constraints_lowest(session):
    """Re-compile the constraints for the lowest allowed dependency versions"""
    session.install("-c", "requirements-dev.txt", "uv")
    session.run("rm", "-f", "constraints-lowest.txt", external=True)
    pip_compile(
        session,
        "constraints-lowest.txt",
        "pyproject.toml",
        "--resolution",
        "lowest-direct",
    )


@nox.session
def django(session):
    """Run Django's system checks"""
    install_cetk(session)
    session.run(
        "python", "manage.py", "check", "--fail-level=WARNING", *session.posargs
    )


@nox.session
def migrations(session):
    """Check that the database migrations are up-to-date"""
    install_cetk(session)
    args = session.posargs or ["--check"]
    session.run("python", "manage.py", "makemigrations", "--skip-checks", *args)


@nox.session
def test(session):
    """Run the unit and regression tests"""
    session.install("-c", "requirements-dev.txt", *TEST_REQUIREMENTS)
    install_cetk(session)
    session.run("pytest", *session.posargs)


@nox.session(name="test-lowest", python="3.9")
def test_lowest(session):
    """Run the unit and regression tests with the lowest allowed versions."""
    session.install("-c", "requirements-dev.txt", *TEST_REQUIREMENTS)
    install_cetk(session, lowest_versions=True)
    session.run(
        "pytest",
        "-Wdefault",
        "-Wignore::DeprecationWarning",
        "-Wignore::FutureWarning",
        "-Wignore::PendingDeprecationWarning",
        "-Wignore:numpy.ndarray size changed:RuntimeWarning",
        *session.posargs,
    )


def install_cetk(session, *, lowest_versions=False, use_wheel_in_ci=True):
    constraints = ("-c", "constraints-lowest.txt") if lowest_versions else ()
    if use_wheel_in_ci and "CI" in os.environ:
        # in CI we install cetk from the built wheel
        wheel = next(Path("./dist").glob("*.whl"))
        session.install(*constraints, wheel)
    else:
        # otherwise cetk is installed in editable mode to allow `nox -R`
        session.install(*constraints, "-e", ".")


def pip_compile(session, outputfile, *extra_args):
    # fmt: off
    session.run(
        "uv", "pip", "compile",
        "--quiet",
        "--output-file", outputfile,
        "--custom-compile-command", f"nox -s {session.name}",
        *session.posargs, *extra_args,
    )
    # fmt: on
