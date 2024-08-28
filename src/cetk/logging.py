"""Utility functions for logging."""

import logging
import os
import sys

# For convenience
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, getLogger, root  # noqa

_logLevels = {
    "0": logging.NOTSET,
    "1": logging.WARNING,
    "2": logging.INFO,
    "3": logging.DEBUG,
}


class CetkHandler(logging.Handler):

    """Log handler for cetk."""


def create_terminal_handler(loglevel=logging.INFO, prog=None):
    """Configure a log handler for the terminal."""
    if prog is None:
        prog = os.path.basename(sys.argv[0])
    streamhandler = logging.StreamHandler()
    streamhandler.setLevel(loglevel)
    format = ": ".join((prog, "%(levelname)s", "%(message)s"))
    streamformatter = logging.Formatter(format)
    streamhandler.setFormatter(streamformatter)
    return streamhandler


def create_cetk_handler(loglevel=logging.INFO):
    """Configure a handler for the Prepper log."""
    handler = CetkHandler()
    handler.setLevel(loglevel)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    return handler


def create_file_handler(filename, loglevel=logging.INFO):
    """Configure a log handler for *filename*."""
    filehandler = logging.FileHandler(filename, mode="w", encoding="utf-8")
    filehandler.setLevel(loglevel)
    fmt = "%(asctime)s %(levelname)s %(name)s.%(funcName)s: %(message)s"
    fileformatter = logging.Formatter(fmt)
    filehandler.setFormatter(fileformatter)
    return filehandler


def configure(terminal_level=logging.WARNING, file_level=logging.INFO, filename=None):
    """Configure logging.

    *terminal_level* sets the minimum log level to send to stderr.
     *file_level* sets the minimum log level to send to the file given
     *by *filename*.  If *filename* is None, no log records will be
     *sent to file.

    """
    baselogger = logging.getLogger("cetk")
    baselogger.setLevel(logging.INFO)
    if terminal_level:
        baselogger.addHandler(create_terminal_handler(terminal_level))
    if filename and file_level:
        baselogger.addHandler(create_file_handler(filename, file_level))
