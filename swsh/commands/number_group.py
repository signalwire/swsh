#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request

# NUMBER GROUP API LOCATION
api_destination = "api/relay/rest/number_groups"
#

class NumberGroupCommand(BaseCommand):
    """Number Group management commands"""

    def get_parser(self):
        """Create and return the argument parser for number_group commands"""
        # Create the top level parser for number groups
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='NUMBER GROUP', help='number_group help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List Number Groups for the Project')
        list_parser.add_argument('-n', '--name', nargs='+', help='Return all Number Groups containing this value')
        list_parser.add_argument('-i', '--id', help='Return a Number Group with the given ID')
        list_parser.add_argument('-j', '--json', action='store_true', help='List Number Groups in JSON Format')
        list_parser.set_defaults(func=self.list_number_groups)

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create Number Group for the Project')
        create_parser.add_argument('-n', '--name', nargs='+', help='Name given to a Number Group within the project', required=True)
        create_parser.add_argument('-s', '--sticky-sender', help='Whether the number group uses the same From number for outbound requests', choices=['true', 'false'], default='false')
        create_parser.set_defaults(func=self.manage_number_group, create=True)

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update Number Groups for the Project')
        update_parser.add_argument('-n', '--name', nargs='+', help='Update the name of a Number Group')
        update_parser.add_argument('-i', '--id', help='ID of the Number Group to be updated', required=True)
        update_parser.add_argument('-s', '--sticky-sender', help='Whether the number group uses the same From number for Outbound requests', choices=['true', 'false'], default='false')
        update_parser.set_defaults(func=self.manage_number_group, update=True)

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete Number Groups for the Project')
        delete_parser.add_argument('-i', '--id', help='ID of the Number Group to be deleted', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force delete. Will not ask to confirm delete of Number Group')
        delete_parser.set_defaults(func=self.manage_number_group, delete=True)

        return base_parser

    def handle_command(self, args):
        """
        Handle number_group command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func = getattr(args, 'func', None)
        if func is not None:
            func(args)
        else:
            self.shell.do_help('number_group')

    def list_number_groups(self, args):
        """
        List Number Groups with optional filtering
        """

        query_params = ""
        if args.id:
            query_params = f"/{args.id}"
        elif args.name:
            name = ' '.join(args.name)
            name = urllib.parse.quote(name)
            query_params = f"?filter_name={name}"

        output, status_code = self._number_group_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)
        else:
            print(f"Error: {output}")

    def manage_number_group(self, args):
        """
        Create / Update / Delete a Number Group
        """

        if 'delete' in args and args.delete:
            return self._delete_number_group(args)
        elif 'create' in args and args.create:
            return self._create_number_group(args)
        else:
            # Assume an update
            return self._update_number_group(args)

    def _create_number_group(self, args):
        """
        Create a new Number Group
        """

        if not args.name:
            print("Error: name is required for create\n")
            return

        payload = self._build_payload(args)

        output, status_code = self._number_group_func(req_type="POST", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)

        if valid:
            output_json = json.loads(output)
            group_id = output_json.get("id", "unknown")
            print(f"Success! Number Group {group_id} created\n")

    def _update_number_group(self, args):
        """
        Update an existing Number Group
        """

        if not args.id:
            print("Number Group ID is required to update a Number Group\n")
            return

        query_params = f"/{args.id}"

        payload = self._build_payload(args)

        output, status_code = self._number_group_func(query_params, req_type="PUT", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)

        if valid:
            print(f"Complete. Number Group {args.id} has been updated.\n")

    def _delete_number_group(self, args):
        """
        Delete a Number Group
        """

        if not args.id:
            print("Number Group ID is required for deletion\n")
            return

        if self.confirm_deletion("Number Group", args.id, args.force):
            query_params = f"/{args.id}"
            output, status_code = self._number_group_func(query_params, req_type="DELETE")
            valid = self.handle_standard_response(output, status_code)

            if valid:
                print(f"Success! Number Group {args.id} Removed\n")
        else:
            print("Delete operation cancelled\n")

    def _build_payload(self, args):
        keys = ["name", "sticky_sender"]

        payload_data = {}
        for k, v in vars(args).items():
            if k in keys and v is not None:
                if isinstance(v, list):
                    payload_data[k] = ' '.join(v)
                else:
                    payload_data[k] = v

        return (json.dumps(payload_data))

    def _number_group_func(self, query_params="", req_type="GET", payload={}):
        destination = f"{api_destination}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)