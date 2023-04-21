"""Command line interface for managing a Clair emission inventory offline."""

import os
import sys
import argparse
import logging
from operator import methodcaller

import django

import etk
from etk.db import migrate_db

log = logging.getLogger(__name__)


class Editor(object):

    def __init__(self):
        self.settings = etk.configure()
        self.db_path = self.settings.DATABASES["default"]["NAME"]

    def init(self):
        log.info(f'running migrations for database {self.db_path}')
        migrate_db()

    def import_data(self):
        print('not implemented')

    def export_data(self):
        print('not implemented')


def main():
    parser = argparse.ArgumentParser(
        description='Manage Clair offline emission inventories',
        usage='''eclair <command> [<args>]
        
        Main commands are:
        init     initialize or migrate an sqlite inventory
        import   import data
        export   export data
        '''
    )
    parser.add_argument(
        'command', help='Subcommand to run',
        choices=('init', 'import', 'export')
    )
    parser.add_argument(
        '-v',
        action=VerboseAction, dest='loglevel',
        default=logging.INFO,
        help='increase verbosity in terminal',
    )
    main_args = parser.parse_args(args=sys.argv[1:2])
    editor = Editor()
    if main_args.command == "init":
        sub_parser = argparse.ArgumentParser(
            description='Create and initialize a new offline inventory.'
        )
        subcommand_args = sub_parser.parse_args(sys.argv[2:])
        editor.init()
    elif main_args.command == "import":
        sub_parser = argparse.ArgumentParser(
            description='Import data from file'
        )
        subcommand_args = sub_parser.parse_args(sys.argv[2:])
        editor.import_data()
    elif main_args.command == "export":
        sub_parser = argparse.ArgumentParser(
            description='Export data to file'
        )
        subcommand_args = sub_parser.parse_args(sys.argv[2:])
        editor.export_data()


def create_terminal_handler(loglevel=logging.INFO, prog=None):
    """Configure a log handler for the terminal."""
    if prog is None:
        prog = os.path.basename(sys.argv[0])
    streamhandler = logging.StreamHandler()
    streamhandler.setLevel(loglevel)
    format = ': '.join((prog, '%(levelname)s', '%(message)s'))
    streamformatter = logging.Formatter(format)
    streamhandler.setFormatter(streamformatter)
    return streamhandler


class VerboseAction(argparse.Action):

    """Argparse action to handle terminal verbosity level."""

    def __init__(self, option_strings, dest,
                 default=logging.WARNING, help=None):
        baselogger = logging.getLogger(__name__)
        baselogger.setLevel(logging.DEBUG)
        self._loghandler = create_terminal_handler(default)
        baselogger.addHandler(self._loghandler)
        super(VerboseAction, self).__init__(
            option_strings, dest,
            nargs=0,
            default=default,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        currentlevel = getattr(namespace, self.dest, logging.WARNING)
        self._loghandler.setLevel(currentlevel - 10)
        setattr(namespace, self.dest, self._loghandler.level)
