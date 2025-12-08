#!/usr/bin/env python3
"""
LaML Bin Command - Backwards Compatibility Alias

This module provides the laml_bin command as an alias for the cxml_bin command.
The functionality is identical; this alias exists for backwards compatibility
with existing scripts and workflows.

For new implementations, prefer using 'cxml_bin' command.
"""

import cmd2
from .cxml_bin import CxmlBinCommand


class LamlBinCommand(CxmlBinCommand):
    """LaML Bin management commands (alias for cxml_bin)"""

    def get_parser(self):
        """Create and return the argument parser for laml_bin commands"""
        # Create a new parser with LAML BIN branding
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='LAML BIN', help='laml_bin help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List LaML Bins for a Project')
        list_parser.add_argument('-n', '--name', nargs='+', help='Filter LaML Bins by name')
        list_parser.add_argument('-i', '--id', help='Retrieve a specific LaML Bin by SignalWire ID')
        list_parser.add_argument('-j', '--json', action='store_true', help='Output LaML Bins in JSON format')
        list_parser.set_defaults(func='list_bins')

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create a LaML Bin')
        create_parser.add_argument('-n', '--name', nargs='+', help='Identifiable name of the LaML Bin', required=True)
        create_parser.add_argument('--contents', nargs='+', help='XML contents of the LaML Bin. Put formatted XML in single quotes, or leave blank to use an editor')
        create_parser.set_defaults(func='create_bin')

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a LaML Bin')
        update_parser.add_argument('-i', '--id', help='SignalWire ID of the LaML Bin to update', required=True)
        update_parser.add_argument('-n', '--name', nargs='+', help='Update the name of the LaML Bin')
        update_parser.add_argument('--contents', nargs='+', help='Update XML contents of the LaML Bin. Put formatted XML in single quotes, or leave blank to use an editor')
        update_parser.set_defaults(func='update_bin')

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete/Remove a LaML Bin')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the LaML Bin to delete', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force removal. Will not ask to confirm delete of LaML Bin')
        delete_parser.set_defaults(func='delete_bin')

        return base_parser

    def handle_command(self, args):
        """
        Handle laml_bin command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('laml_bin')
