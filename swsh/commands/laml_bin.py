#!/usr/bin/env python3
import cmd2
import json
import os
import subprocess
import tempfile
from .base import BaseCommand
from swsh.functions import laml_bin_func, change_verify


class LamlBinCommand(BaseCommand):
    """LAML Bin management commands"""
    
    def __init__(self, shell_instance):
        super().__init__(shell_instance)
        self.editor = os.environ.get('EDITOR', 'pyvim')
    
    def get_parser(self):
        """Create and return the argument parser for laml_bin commands"""
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='LAML BIN', help='laml_bin help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List LaML Bins for a Project')
        list_parser.add_argument('-j', '--json', action='store_true', help='List LaML Bins for project in JSON Format')
        list_parser.add_argument('-n', '--name', nargs='+', help='Find a LaML Bin by Name')
        list_parser.add_argument('-i', '--id', help='Find a LaML Bin by SignalWire ID')
        list_parser.set_defaults(func=self.list_bins)

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create a LaML Bin')
        create_parser.add_argument('-n', '--name', nargs='+', help='Friendly Name of the LaML Bin', required=True)
        create_parser.add_argument('-c', '--contents', nargs='+', help='LaML/XML contents of the LaML Bin')
        create_parser.set_defaults(func=self.create_bin)

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a LaML Bin')
        update_parser.add_argument('-i', '--id', help='ID of the LaML Bin to update', required=True)
        update_parser.add_argument('-n', '--name', nargs='+', help='Update the Friendly Name of the LaML Bin')
        update_parser.add_argument('-c', '--contents', nargs='+', help='Update LaML/XML contents of the LaML Bin')
        update_parser.set_defaults(func=self.update_bin)

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete a LaML Bin')
        delete_parser.add_argument('-i', '--id', help='ID of the LaML Bin to delete', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force delete. Will not ask to confirm delete of LaML Bin')
        delete_parser.set_defaults(func=self.delete_bin)

        return base_parser
    
    def handle_command(self, args):
        """Handle laml_bin command routing"""
        func = getattr(args, 'func', None)
        if func is not None:
            func(args)
        else:
            self.shell.do_help('laml_bin')

    def list_bins(self, args):
        """List LAML bins with optional filtering"""
        args = self.is_env_var(args)
        
        query_params = ""
        if args.name:
            if len(args.name) == 1:
                name = args.name[0]
            else:
                name = "%20".join(args.name)
            query_params = f"?Name={name}"
        elif args.id:
            query_params = f"/{args.id}"

        output, status_code = laml_bin_func(query_params)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
        
        if valid:
            output_json = json.loads(output)
            
            if args.id and args.json:
                self.print_json_response(output_json)
            elif args.id:
                self._print_single_bin(output_json, "1")
            elif args.json:
                bins = output_json.get("laml_bins", [])
                self.print_json_response(bins)
            else:
                bins = output_json.get("laml_bins", [])
                self._print_multiple_bins(bins)

    def create_bin(self, args):
        """Create a new LAML bin"""
        args = self.is_env_var(args)
        
        name = ' '.join(args.name)
        contents = None
        
        if args.contents:
            contents = ' '.join(args.contents)
        else:
            # Open editor for contents
            contents = self._edit_laml_contents()
            if contents is None:
                print("LaML Bin creation cancelled\n")
                return
        
        # Prepare payload for compatibility API
        payload = f"FriendlyName={name}&LamlBinData={contents}"
        
        output, status_code = laml_bin_func(req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
        
        if valid:
            output_json = json.loads(output)
            bin_sid = output_json.get("sid", "unknown")
            print(f"Success! LaML Bin {bin_sid} created\n")

    def update_bin(self, args):
        """Update an existing LAML bin"""
        args = self.is_env_var(args)
        
        query_params = f"/{args.id}"
        
        # Prepare update data
        update_data = {}
        
        if args.name:
            update_data["FriendlyName"] = ' '.join(args.name)
            
        if args.contents:
            update_data["LamlBinData"] = ' '.join(args.contents)
        else:
            # Get current contents and open editor
            current_contents = self._get_current_contents(args.id)
            if current_contents is None:
                print("Could not retrieve current LaML Bin contents\n")
                return
                
            new_contents = self._edit_laml_contents(current_contents, args.id)
            if new_contents is None:
                print("LaML Bin update cancelled\n")
                return
            update_data["LamlBinData"] = new_contents
        
        if not update_data:
            print("No update data provided\n")
            return
            
        # Create payload for compatibility API
        payload_parts = []
        for key, value in update_data.items():
            payload_parts.append(f"{key}={value}")
        payload = "&".join(payload_parts)
        
        output, status_code = laml_bin_func(query_params, req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
        
        if valid:
            print(f"Complete. LaML Bin {args.id} has been updated.\n")

    def delete_bin(self, args):
        """Delete a LAML bin"""
        args = self.is_env_var(args)
        
        if self.confirm_deletion("LaML Bin", args.id, args.force):
            query_params = f"/{args.id}"
            output, status_code = laml_bin_func(query_params, "DELETE")
            valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
            
            if valid:
                print(f"Success! LaML Bin {args.id} Removed\n")
        else:
            print("Delete operation cancelled\n")

    def _get_current_contents(self, bin_id):
        """Get current contents of a LAML bin"""
        query_params = f"/{bin_id}"
        output, status_code = laml_bin_func(query_params)
        
        if self.handle_standard_response(output, status_code, compatibility_mode=True):
            output_json = json.loads(output)
            return output_json.get("contents", "").strip()
        return None

    def _edit_laml_contents(self, initial_contents=None, bin_id=None):
        """Open editor to edit LAML contents - SECURITY FIX: Use subprocess instead of os.system"""
        default_template = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
</Response>"""
        
        contents = initial_contents if initial_contents else default_template
        
        # Create temporary file
        if bin_id:
            filename = f"{bin_id}.xml"
        else:
            filename = "laml.xml"
            
        try:
            with open(filename, 'w') as f:
                f.write(contents)
            
            # SECURITY FIX: Use subprocess instead of os.system to prevent shell injection
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
            
            # Check if contents were changed (for create operations)
            if initial_contents is None:
                changed = change_verify(default_template, edited_contents.split('\n'))
                if changed == 0:
                    return None
            
            # Clean up temporary file
            try:
                os.remove(filename)
            except OSError:
                pass  # File might have been removed already
                
            return edited_contents.strip()
            
        except IOError as e:
            print(f"Error handling file {filename}: {e}")
            return None

    def _print_single_bin(self, bin_data, number):
        """Print a single LAML bin in formatted output"""
        print(f"{number})")
        print(f"  LaML Bin ID:\t\t\t{bin_data.get('sid', 'N/A')}")
        print(f"  Friendly Name:\t\t{bin_data.get('friendly_name', 'N/A')}")
        print(f"  Date Created:\t\t\t{bin_data.get('date_created', 'N/A')}")
        print(f"  Date Updated:\t\t\t{bin_data.get('date_updated', 'N/A')}")
        print(f"  Contents:\n{bin_data.get('contents', 'N/A')}")
        print("")

    def _print_multiple_bins(self, bins_data):
        """Print multiple LAML bins in formatted output"""
        if not bins_data:
            print("No LaML Bins found\n")
            return
            
        for i, bin_data in enumerate(bins_data, 1):
            self._print_single_bin(bin_data, str(i))