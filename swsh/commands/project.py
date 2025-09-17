#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request

# PROJECT API LOCATION (Compatibility API)
api_destination = "api/laml/2010-04-01/Accounts"
#

class ProjectCommand(BaseCommand):
    """Project/Account management commands"""

    def get_parser(self):
        """Create and return the argument parser for project commands"""
        # Create the top level parser for projects
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='PROJECT', help='project help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List Projects and Subprojects')
        list_parser.add_argument('-n', '--name', nargs='+', help='List Single Project by Friendly Name')
        list_parser.add_argument('-i', '--id', help='List SignalWire Space or Subspace with given SID')
        list_parser.add_argument('-j', '--json', action='store_true', help='List Projects in JSON format')
        list_parser.set_defaults(func=self.list_projects)

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create a subproject')
        create_parser.add_argument('-n', '--name', nargs='+', help='Create a subproject under the current project', required=True)
        create_parser.set_defaults(func=self.create_project)

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a project')
        update_parser.add_argument('-n', '--name', nargs='+', help='Update the name of a subproject')
        update_parser.add_argument('-i', '--id', help='SignalWire ID of the subproject', required=True)
        update_parser.set_defaults(func=self.update_project)

        return base_parser

    def handle_command(self, args):
        """
        Handle project command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func = getattr(args, 'func', None)
        if func is not None:
            func(args)
        else:
            self.shell.do_help('project')

    def list_projects(self, args):
        """
        List projects/accounts with optional filtering
        """

        query_params = ""
        if args.id:
            query_params = f"/{args.id}"
        elif args.name:
            name = ' '.join(args.name)
            name = urllib.parse.quote(name)
            query_params = f"?FriendlyName={name}"

        output, status_code = self._project_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            if args.json:
                output_json = json.loads(output)
                if args.id:
                    # Single project - display as-is
                    self.display_output(output, json_format=True)
                else:
                    # Multiple projects - extract accounts data
                    accounts_data = output_json.get("accounts", [])
                    self.display_output(json.dumps(accounts_data), json_format=True)
            else:
                output_json = json.loads(output)
                if args.id:
                    # Single project - display formatted
                    self.display_output(output, json_format=False)
                else:
                    # Multiple projects - extract and format accounts data only
                    accounts_data = output_json.get("accounts", [])
                    self.display_output(json.dumps({"data": accounts_data}), json_format=False)
        else:
            print(f"Error: {output}")

    def create_project(self, args):
        """
        Create a new subproject
        """

        if not args.name:
            print("Error: name is required for create\n")
            return

        friendly_name = ' '.join(args.name)
        payload = f"FriendlyName={urllib.parse.quote(friendly_name)}"

        output, status_code = self._project_func(req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            project_sid = output_json.get("sid", "unknown")
            project_name = output_json.get("friendly_name", friendly_name)
            print(f"Success! Subproject '{project_name}' created with SID: {project_sid}\n")

    def update_project(self, args):
        """
        Update an existing project
        """
        # TODO: Revist.  Not sure if there are other paramaters that can be updated.

        if not args.id:
            print("Project SID is required to update a project\n")
            return

        if not args.name:
            print("Name is required to update a project\n")
            return

        query_params = f"/{args.id}"
        friendly_name = ' '.join(args.name)
        payload = f"FriendlyName={urllib.parse.quote(friendly_name)}"

        output, status_code = self._project_func(query_params, req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            project_name = output_json.get("friendly_name", friendly_name)
            print(f"Complete. Project '{project_name}' (SID: {args.id}) has been updated.\n")

    def _project_func(self, query_params="", req_type="GET", payload=""):
        destination = f"{api_destination}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)