#!/usr/bin/env python3
import cmd2
import json
import os
import subprocess
import tempfile
import urllib.parse
from .base import BaseCommand
from functions import http_request, get_environment

# AI AGENT API LOCATION (Fabric API)
# Endpoint: /api/fabric/resources/ai_agents
# Reference: https://developer.signalwire.com/rest/signalwire-rest/endpoints/fabric/ai-agents-create/
api_destination = "api/fabric/resources/ai_agents"


class AiAgentCommand(BaseCommand):
    """AI Agent management commands for SignalWire SWML-based voice AI"""

    def __init__(self, shell_instance):
        super().__init__(shell_instance)
        self.editor = os.environ.get('EDITOR', 'pyvim')

    def get_parser(self):
        """Create and return the argument parser for ai_agent commands"""
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='AI AGENT', help='ai_agent help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List AI Agents for a Project')
        list_parser.add_argument('-n', '--name', nargs='+', help='Filter AI Agents by name')
        list_parser.add_argument('-i', '--id', help='Retrieve a specific AI Agent by SignalWire ID')
        list_parser.add_argument('-j', '--json', action='store_true', help='Output AI Agents in JSON format')
        list_parser.set_defaults(func='list_agents')

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create an AI Agent')
        create_parser.add_argument('-n', '--name', nargs='+', help='Identifiable name of the AI Agent', required=True)
        create_parser.add_argument('--contents', help='SWML JSON contents of the AI Agent. Leave blank to use an editor')
        create_parser.set_defaults(func='create_agent')

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update an AI Agent')
        update_parser.add_argument('-i', '--id', help='SignalWire ID of the AI Agent to update', required=True)
        update_parser.add_argument('-n', '--name', nargs='+', help='Update the name of the AI Agent')
        update_parser.add_argument('--contents', help='Update SWML JSON contents. Leave blank to use an editor')
        update_parser.set_defaults(func='update_agent')

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete/Remove an AI Agent')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the AI Agent to delete', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force removal. Will not ask to confirm delete')
        delete_parser.set_defaults(func='delete_agent')

        return base_parser

    def handle_command(self, args):
        """
        Handle ai_agent command routing
        """
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('ai_agent')

    def list_agents(self, args):
        """
        List AI Agents with optional filtering
        """

        query_params = ""
        if args.id:
            query_params = f"/{args.id}"
        elif args.name:
            name = ' '.join(args.name)
            name = urllib.parse.quote(name)
            query_params = f"?Name={name}"

        output, status_code = self._ai_agent_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=False)

        if valid:
            if args.json:
                output_json = json.loads(output)
                if args.id:
                    # Single agent - display as-is
                    self.display_output(output, json_format=True)
                else:
                    # Multiple agents - extract data array
                    agents_data = output_json.get("data", [])
                    self.display_output(json.dumps(agents_data), json_format=True)
            else:
                output_json = json.loads(output)
                if args.id:
                    # Single agent - display formatted
                    self.display_output(output, json_format=False)
                else:
                    # Multiple agents - extract and format data only
                    agents_data = output_json.get("data", [])
                    if not agents_data:
                        print("No AI Agents found\n")
                    else:
                        self.display_output(json.dumps({"data": agents_data}), json_format=False)
        else:
            print(f"Error: {output}")

    def create_agent(self, args):
        """
        Create a new AI Agent
        """

        if not args.name:
            print("Error: name is required for create\n")
            return

        name = ' '.join(args.name)
        contents = None

        if args.contents:
            contents = args.contents
        else:
            # Open editor for SWML contents
            contents = self._edit_swml_contents()
            if contents is None:
                print("AI Agent creation cancelled\n")
                return

        # Prepare JSON payload
        payload = {
            "name": name,
            "contents": contents
        }

        output, status_code = self._ai_agent_func("", req_type="POST", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code, compatibility_mode=False)

        if valid:
            output_json = json.loads(output)
            agent_id = output_json.get("id", "unknown")
            agent_name = output_json.get("name", name)
            print(f"Success! AI Agent '{agent_name}' created with ID: {agent_id}\n")

    def update_agent(self, args):
        """
        Update an existing AI Agent
        """

        if not args.id:
            print("AI Agent ID is required to update an agent\n")
            return

        query_params = f"/{args.id}"
        payload = {}

        # Handle name update
        if args.name:
            name = ' '.join(args.name)
            payload["name"] = name

        # Handle contents update
        if args.contents:
            payload["contents"] = args.contents
        elif not args.name:
            # No name provided and no contents on command line, open editor
            current_contents = self._get_current_contents(args.id)
            if current_contents is None:
                print("Could not retrieve current AI Agent contents\n")
                return

            new_contents = self._edit_swml_contents(current_contents, args.id)
            if new_contents is None:
                print("AI Agent update cancelled\n")
                return
            payload["contents"] = new_contents

        if not payload:
            print("No update parameters provided\n")
            return

        output, status_code = self._ai_agent_func(query_params, req_type="PATCH", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code, compatibility_mode=False)

        if valid:
            output_json = json.loads(output)
            agent_name = output_json.get("name", "AI Agent")
            print(f"Complete. AI Agent '{agent_name}' (ID: {args.id}) has been updated.\n")

    def delete_agent(self, args):
        """
        Delete/remove an AI Agent
        """

        if not args.id:
            print("AI Agent ID is required to delete an agent\n")
            return

        if self.confirm_deletion("AI Agent", args.id, args.force):
            query_params = f"/{args.id}"
            output, status_code = self._ai_agent_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success
            if status_code == 204:
                print(f"Success! AI Agent {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=False)
                if not valid:
                    print(f"Error deleting AI Agent: {output}")
        else:
            print("Delete operation cancelled\n")

    def _get_current_contents(self, agent_id):
        """
        Get current contents of an AI Agent for editing
        """
        query_params = f"/{agent_id}"
        output, status_code = self._ai_agent_func(query_params, req_type="GET")

        if status_code == 200:
            try:
                output_json = json.loads(output)
                contents = output_json.get("contents", "")
                # Contents may be a string or dict depending on API response
                if isinstance(contents, dict):
                    return json.dumps(contents, indent=2)
                return contents
            except json.JSONDecodeError:
                return None
        return None

    def _edit_swml_contents(self, initial_contents=None, agent_id=None):
        """
        Open editor to edit SWML JSON contents
        Uses subprocess and tempfile for security
        """
        default_template = {
            "version": "1.0.0",
            "sections": {
                "main": [
                    {
                        "ai": {
                            "prompt": {
                                "text": "<WRITE YOUR PROMPT HERE>"
                            }
                        }
                    }
                ]
            }
        }

        if initial_contents:
            # Try to parse as JSON for pretty printing
            try:
                if isinstance(initial_contents, str):
                    contents_dict = json.loads(initial_contents)
                else:
                    contents_dict = initial_contents
                contents = json.dumps(contents_dict, indent=2)
            except (json.JSONDecodeError, TypeError):
                contents = initial_contents
        else:
            contents = json.dumps(default_template, indent=2)

        # Create temporary file with .swml extension
        suffix = '.swml'
        prefix = f'ai_agent_{agent_id}_' if agent_id else 'ai_agent_'

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, prefix=prefix, delete=False) as f:
                f.write(contents)
                temp_filename = f.name

            # Use subprocess to open editor
            try:
                subprocess.run([self.editor, temp_filename], check=True)
            except subprocess.CalledProcessError:
                print(f"Error opening editor {self.editor}")
                self._cleanup_temp_file(temp_filename)
                return None
            except FileNotFoundError:
                print(f"Editor {self.editor} not found")
                self._cleanup_temp_file(temp_filename)
                return None

            # Read the edited contents
            with open(temp_filename, 'r') as f:
                edited_contents = f.read()

            # Clean up temporary file
            self._cleanup_temp_file(temp_filename)

            # Validate JSON
            try:
                json.loads(edited_contents)
            except json.JSONDecodeError as e:
                print(f"Error: The edited contents are not valid JSON: {e}")
                return None

            # Check if contents were changed by comparing with original
            original_normalized = contents.strip()
            edited_normalized = edited_contents.strip()

            if original_normalized == edited_normalized:
                # No changes made
                return None

            return edited_normalized

        except IOError as e:
            print(f"Error handling temporary file: {e}")
            return None

    def _cleanup_temp_file(self, filename):
        """Safely remove temporary file"""
        try:
            os.remove(filename)
        except OSError:
            pass  # File might have been removed already

    def _ai_agent_func(self, query_params="", req_type="GET", payload=""):
        """Construct API destination and make request"""
        destination = f"{api_destination}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)
