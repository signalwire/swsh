#!/usr/bin/env python3
import cmd2
import json
import os
import subprocess
import urllib.parse
from .base import BaseCommand
from functions import http_request, get_environment

# CXML BIN API LOCATION (Compatibility API)
# Endpoint: /api/laml/2010-04-01/Accounts/{AccountSid}/LamlBins
api_destination = "api/laml/2010-04-01/Accounts"
#


class CxmlBinCommand(BaseCommand):
    """cXML Bin management commands (formerly LaML Bin)"""

    def __init__(self, shell_instance):
        super().__init__(shell_instance)
        self.editor = os.environ.get('EDITOR', 'pyvim')

    def get_parser(self):
        """Create and return the argument parser for cxml_bin commands"""
        # Create the top level parser for cXML Bins
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='CXML BIN', help='cxml_bin help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List cXML Bins for a Project')
        list_parser.add_argument('-n', '--name', nargs='+', help='Filter cXML Bins by name')
        list_parser.add_argument('-i', '--id', help='Retrieve a specific cXML Bin by SignalWire ID')
        list_parser.add_argument('-j', '--json', action='store_true', help='Output cXML Bins in JSON format')
        list_parser.set_defaults(func='list_bins')

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create a cXML Bin')
        create_parser.add_argument('-n', '--name', nargs='+', help='Identifiable name of the cXML Bin', required=True)
        create_parser.add_argument('--contents', nargs='+', help='XML contents of the cXML Bin. Put formatted XML in single quotes, or leave blank to use an editor')
        create_parser.set_defaults(func='create_bin')

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a cXML Bin')
        update_parser.add_argument('-i', '--id', help='SignalWire ID of the cXML Bin to update', required=True)
        update_parser.add_argument('-n', '--name', nargs='+', help='Update the name of the cXML Bin')
        update_parser.add_argument('--contents', nargs='+', help='Update XML contents of the cXML Bin. Put formatted XML in single quotes, or leave blank to use an editor')
        update_parser.set_defaults(func='update_bin')

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete/Remove a cXML Bin')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the cXML Bin to delete', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force removal. Will not ask to confirm delete of cXML Bin')
        delete_parser.set_defaults(func='delete_bin')

        return base_parser

    def handle_command(self, args):
        """
        Handle cxml_bin command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('cxml_bin')

    def list_bins(self, args):
        """
        List cXML Bins with optional filtering
        """

        query_params = "/LamlBins"
        if args.id:
            query_params = f"/LamlBins/{args.id}"
        elif args.name:
            name = ' '.join(args.name)
            name = urllib.parse.quote(name)
            query_params = f"/LamlBins?Name={name}"

        output, status_code = self._cxml_bin_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            if args.json:
                output_json = json.loads(output)
                if args.id:
                    # Single bin - display as-is
                    self.display_output(output, json_format=True)
                else:
                    # Multiple bins - extract laml_bins data
                    bins_data = output_json.get("laml_bins", [])
                    self.display_output(json.dumps(bins_data), json_format=True)
            else:
                output_json = json.loads(output)
                if args.id:
                    # Single bin - display formatted
                    self.display_output(output, json_format=False)
                else:
                    # Multiple bins - extract and format laml_bins data only
                    bins_data = output_json.get("laml_bins", [])
                    self.display_output(json.dumps({"data": bins_data}), json_format=False)
        else:
            print(f"Error: {output}")

    def create_bin(self, args):
        """
        Create a new cXML Bin
        """

        if not args.name:
            print("Error: name is required for create\n")
            return

        name = ' '.join(args.name)
        contents = None

        if args.contents:
            contents = ' '.join(args.contents)
        else:
            # Open editor for contents
            contents = self._edit_cxml_contents()
            if contents is None:
                print("cXML Bin creation cancelled\n")
                return

        # Prepare payload for compatibility API (form-encoded)
        payload_parts = []
        payload_parts.append(f"Name={urllib.parse.quote(name)}")
        payload_parts.append(f"Contents={urllib.parse.quote(contents, safe='/')}")
        payload = "&".join(payload_parts)

        output, status_code = self._cxml_bin_func("/LamlBins", req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            bin_sid = output_json.get("sid", "unknown")
            bin_name = output_json.get("name", name)
            print(f"Success! cXML Bin '{bin_name}' created with SID: {bin_sid}\n")

    def update_bin(self, args):
        """
        Update an existing cXML Bin
        """

        if not args.id:
            print("cXML Bin SID is required to update a bin\n")
            return

        query_params = f"/LamlBins/{args.id}"
        payload_parts = []

        # Handle name update
        if args.name:
            name = ' '.join(args.name)
            payload_parts.append(f"Name={urllib.parse.quote(name)}")

        # Handle contents update
        if args.contents:
            contents = ' '.join(args.contents)
            payload_parts.append(f"Contents={urllib.parse.quote(contents, safe='/')}")
        elif not args.name:
            # No name provided and no contents on command line, open editor
            current_contents = self._get_current_contents(args.id)
            if current_contents is None:
                print("Could not retrieve current cXML Bin contents\n")
                return

            new_contents = self._edit_cxml_contents(current_contents, args.id)
            if new_contents is None:
                print("cXML Bin update cancelled\n")
                return
            payload_parts.append(f"Contents={urllib.parse.quote(new_contents, safe='/')}")

        if not payload_parts:
            print("No update parameters provided\n")
            return

        payload = "&".join(payload_parts)

        output, status_code = self._cxml_bin_func(query_params, req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            bin_name = output_json.get("name", "cXML Bin")
            print(f"Complete. cXML Bin '{bin_name}' (SID: {args.id}) has been updated.\n")

    def delete_bin(self, args):
        """
        Delete/remove a cXML Bin
        """

        if not args.id:
            print("cXML Bin SID is required to delete a bin\n")
            return

        if self.confirm_deletion("cXML Bin", args.id, args.force):
            query_params = f"/LamlBins/{args.id}"
            output, status_code = self._cxml_bin_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success
            if status_code == 204:
                print(f"Success! cXML Bin {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
                if not valid:
                    print(f"Error deleting cXML Bin: {output}")
        else:
            print("Delete operation cancelled\n")

    def _get_current_contents(self, bin_id):
        """
        Get current contents of a cXML Bin for editing
        """
        query_params = f"/LamlBins/{bin_id}"
        output, status_code = self._cxml_bin_func(query_params, req_type="GET")

        if status_code == 200:
            try:
                output_json = json.loads(output)
                return output_json.get("contents", "").strip()
            except json.JSONDecodeError:
                return None
        return None

    def _edit_cxml_contents(self, initial_contents=None, bin_id=None):
        """
        Open editor to edit cXML contents
        Uses subprocess instead of os.system for security
        """
        default_template = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
</Response>"""

        contents = initial_contents if initial_contents else default_template

        # Create temporary file
        if bin_id:
            filename = f"{bin_id}.xml"
        else:
            filename = "cxml.xml"

        try:
            with open(filename, 'w') as f:
                f.write(contents)

            # Use subprocess instead of os.system to prevent shell injection
            try:
                subprocess.run([self.editor, filename], check=True)
            except subprocess.CalledProcessError:
                print(f"Error opening editor {self.editor}")
                return None
            except FileNotFoundError:
                print(f"Editor {self.editor} not found")
                return None

            # Read the edited contents
            with open(filename, 'r') as f:
                edited_contents = f.read()

            # Clean up temporary file
            try:
                os.remove(filename)
            except OSError:
                pass  # File might have been removed already

            # Check if contents were changed by comparing with original
            # Normalize whitespace for comparison
            original_normalized = contents.strip()
            edited_normalized = edited_contents.strip()

            if original_normalized == edited_normalized:
                # No changes made
                return None

            return edited_normalized

        except IOError as e:
            print(f"Error handling file {filename}: {e}")
            return None

    def _cxml_bin_func(self, query_params="", req_type="GET", payload=""):
        """Get project ID from environment and construct API destination"""
        _, project_id, _ = get_environment()
        destination = f"{api_destination}/{project_id}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)
