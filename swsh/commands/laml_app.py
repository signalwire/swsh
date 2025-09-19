#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request

# LAML APPLICATION API LOCATION (Compatibility API)
api_destination = "api/laml/2010-04-01/Accounts"
#

class LamlAppCommand(BaseCommand):
    """LaML Application management commands"""

    def get_parser(self):
        """Create and return the argument parser for laml_app commands"""
        # Create the top level parser for LaML applications
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='LaML APP', help='laml_app help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List LaML Applications for the Project')
        list_parser.add_argument('-i', '--id', help='SignalWire ID of the LaML Application')
        list_parser.add_argument('-j', '--json', action='store_true', help='List LaML Applications in JSON format')
        list_parser.set_defaults(func=self.list_applications)

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create a LaML Application')
        create_parser.add_argument('-n', '--name', nargs='+', help='Friendly name for the LaML application', required=True)
        create_parser.add_argument('--status-callback', help='URL to pass status updates to the application')
        create_parser.add_argument('--status-callback-method', help='HTTP method for status_callback. Default is POST.', choices=["POST", "GET"], default="POST")
        create_parser.add_argument('--voice-caller-id-lookup', help='Look up a callers ID from the database. Possible values are true or false. Default is false.', choices=["true", "false"], default="false")
        create_parser.add_argument('--voice-url', help='URL to request when a voice or fax is received')
        create_parser.add_argument('--voice-method', help='HTTP method for voice_url. Default is POST.', choices=["POST", "GET"], default="POST")
        create_parser.add_argument('--voice-fallback-url', help='URL to request if there is an error at primary')
        create_parser.add_argument('--voice-fallback-method', help='HTTP method for voice_fallback_url. Default is POST.', choices=["POST", "GET"], default="POST")
        create_parser.add_argument('--message-status-callback', help='When a message receives a status change, a POST request to this URL with message details')
        create_parser.add_argument('--sms-url', help='URL to request when an SMS is received')
        create_parser.add_argument('--sms-method', help='HTTP method for sms_url. Default is POST.', choices=["POST", "GET"], default="POST")
        create_parser.add_argument('--sms-fallback-url', help='URL SignalWire will request if errors occur when fetching the sms_url')
        create_parser.add_argument('--sms-fallback-method', help='HTTP method for sms_fallback_url. Default is POST.', choices=["POST", "GET"], default="POST")
        create_parser.add_argument('--sms-status-callback', help='When a message receives a status change, a POST request to this URL with message details')
        create_parser.set_defaults(func=self.create_application)

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a LaML Application')
        update_parser.add_argument('-i', '--id', help='ID of the LaML Application to be updated', required=True)
        update_parser.add_argument('-n', '--name', nargs='+', help='Friendly name for the LaML application')
        update_parser.add_argument('--status-callback', help='URL to pass status updates to the application')
        update_parser.add_argument('--status-callback-method', help='HTTP method for status_callback. Default is POST.', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--voice-caller-id-lookup', help='Look up a callers ID from the database. Possible values are true or false. Default is false.', choices=["true", "false"], default="false")
        update_parser.add_argument('--voice-url', help='URL to request when a voice or fax is received')
        update_parser.add_argument('--voice-method', help='HTTP method for voice_url. Default is POST.', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--voice-fallback-url', help='URL to request if there is an error at primary')
        update_parser.add_argument('--voice-fallback-method', help='HTTP method for voice_fallback_url. Default is POST.', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--message-status-callback', help='When a message receives a status change, a POST request to this URL with message details')
        update_parser.add_argument('--sms-url', help='URL to request when an SMS is received')
        update_parser.add_argument('--sms-method', help='HTTP method for sms_url. Default is POST.', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--sms-fallback-url', help='URL SignalWire will request if errors occur when fetching the sms_url')
        update_parser.add_argument('--sms-fallback-method', help='HTTP method for sms_fallback_url. Default is POST.', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--sms-status-callback', help='When a message receives a status change, a POST request to this URL with message details')
        update_parser.set_defaults(func=self.update_application)

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete/Remove a LaML Application')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the LaML Application to be deleted', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force removal. Will not ask to confirm delete of LaML Application')
        delete_parser.set_defaults(func=self.delete_application)

        return base_parser

    def handle_command(self, args):
        """
        Handle laml_app command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func = getattr(args, 'func', None)
        if func is not None:
            func(args)
        else:
            self.shell.do_help('laml_app')

    def list_applications(self, args):
        """
        List LaML applications with optional filtering
        """

        query_params = "/Applications"
        if args.id:
            query_params = f"/Applications/{args.id}"

        output, status_code = self._application_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            if args.json:
                output_json = json.loads(output)
                if args.id:
                    # Single application - display as-is
                    self.display_output(output, json_format=True)
                else:
                    # Multiple applications - extract applications data
                    applications_data = output_json.get("applications", [])
                    self.display_output(json.dumps(applications_data), json_format=True)
            else:
                output_json = json.loads(output)
                if args.id:
                    # Single application - display formatted
                    self.display_output(output, json_format=False)
                else:
                    # Multiple applications - extract and format applications data only
                    applications_data = output_json.get("applications", [])
                    self.display_output(json.dumps({"data": applications_data}), json_format=False)
        else:
            print(f"Error: {output}")

    def create_application(self, args):
        """
        Create a new LaML application
        """

        if not args.name:
            print("Error: name is required for create\n")
            return

        payload_parts = []

        # Handle required friendly name
        friendly_name = ' '.join(args.name)
        payload_parts.append(f"FriendlyName={urllib.parse.quote(friendly_name)}")

        # Handle optional parameters
        if args.status_callback:
            payload_parts.append(f"StatusCallback={urllib.parse.quote(args.status_callback)}")
        if args.status_callback_method:
            payload_parts.append(f"StatusCallbackMethod={urllib.parse.quote(args.status_callback_method)}")
        if args.voice_caller_id_lookup:
            payload_parts.append(f"VoiceCallerIdLookup={urllib.parse.quote(args.voice_caller_id_lookup)}")
        if args.voice_url:
            payload_parts.append(f"VoiceUrl={urllib.parse.quote(args.voice_url)}")
        if args.voice_method:
            payload_parts.append(f"VoiceMethod={urllib.parse.quote(args.voice_method)}")
        if args.voice_fallback_url:
            payload_parts.append(f"VoiceFallbackUrl={urllib.parse.quote(args.voice_fallback_url)}")
        if args.voice_fallback_method:
            payload_parts.append(f"VoiceFallbackMethod={urllib.parse.quote(args.voice_fallback_method)}")
        if args.message_status_callback:
            payload_parts.append(f"MessageStatusCallback={urllib.parse.quote(args.message_status_callback)}")
        if args.sms_url:
            payload_parts.append(f"SmsUrl={urllib.parse.quote(args.sms_url)}")
        if args.sms_method:
            payload_parts.append(f"SmsMethod={urllib.parse.quote(args.sms_method)}")
        if args.sms_fallback_url:
            payload_parts.append(f"SmsFallbackUrl={urllib.parse.quote(args.sms_fallback_url)}")
        if args.sms_fallback_method:
            payload_parts.append(f"SmsFallbackMethod={urllib.parse.quote(args.sms_fallback_method)}")
        if args.sms_status_callback:
            payload_parts.append(f"SmsStatusCallback={urllib.parse.quote(args.sms_status_callback)}")

        payload = "&".join(payload_parts)

        output, status_code = self._application_func("/Applications", req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            app_sid = output_json.get("sid", "unknown")
            app_name = output_json.get("friendly_name", friendly_name)
            print(f"Success! LaML Application '{app_name}' created with SID: {app_sid}\n")

    def update_application(self, args):
        """
        Update an existing LaML application
        """

        if not args.id:
            print("Application SID is required to update an application\n")
            return

        # Check if at least one parameter is provided for update
        update_params = [args.name, args.status_callback, args.status_callback_method, args.voice_caller_id_lookup,
                        args.voice_url, args.voice_method, args.voice_fallback_url, args.voice_fallback_method,
                        args.message_status_callback, args.sms_url, args.sms_method, args.sms_fallback_url,
                        args.sms_fallback_method, args.sms_status_callback]

        if not any(param for param in update_params):
            print("At least one parameter is required to update an application\n")
            return

        query_params = f"/Applications/{args.id}"
        payload_parts = []

        # Handle optional parameters
        if args.name:
            friendly_name = ' '.join(args.name)
            payload_parts.append(f"FriendlyName={urllib.parse.quote(friendly_name)}")
        if args.status_callback:
            payload_parts.append(f"StatusCallback={urllib.parse.quote(args.status_callback)}")
        if args.status_callback_method:
            payload_parts.append(f"StatusCallbackMethod={urllib.parse.quote(args.status_callback_method)}")
        if args.voice_caller_id_lookup:
            payload_parts.append(f"VoiceCallerIdLookup={urllib.parse.quote(args.voice_caller_id_lookup)}")
        if args.voice_url:
            payload_parts.append(f"VoiceUrl={urllib.parse.quote(args.voice_url)}")
        if args.voice_method:
            payload_parts.append(f"VoiceMethod={urllib.parse.quote(args.voice_method)}")
        if args.voice_fallback_url:
            payload_parts.append(f"VoiceFallbackUrl={urllib.parse.quote(args.voice_fallback_url)}")
        if args.voice_fallback_method:
            payload_parts.append(f"VoiceFallbackMethod={urllib.parse.quote(args.voice_fallback_method)}")
        if args.message_status_callback:
            payload_parts.append(f"MessageStatusCallback={urllib.parse.quote(args.message_status_callback)}")
        if args.sms_url:
            payload_parts.append(f"SmsUrl={urllib.parse.quote(args.sms_url)}")
        if args.sms_method:
            payload_parts.append(f"SmsMethod={urllib.parse.quote(args.sms_method)}")
        if args.sms_fallback_url:
            payload_parts.append(f"SmsFallbackUrl={urllib.parse.quote(args.sms_fallback_url)}")
        if args.sms_fallback_method:
            payload_parts.append(f"SmsFallbackMethod={urllib.parse.quote(args.sms_fallback_method)}")
        if args.sms_status_callback:
            payload_parts.append(f"SmsStatusCallback={urllib.parse.quote(args.sms_status_callback)}")

        payload = "&".join(payload_parts)

        output, status_code = self._application_func(query_params, req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            app_name = output_json.get("friendly_name", "LaML Application")
            print(f"Complete. LaML Application '{app_name}' (SID: {args.id}) has been updated.\n")

    def delete_application(self, args):
        """
        Delete/remove a LaML application
        """

        if not args.id:
            print("Application SID is required to delete an application\n")
            return

        if self.confirm_deletion("LaML Application", args.id, args.force):
            query_params = f"/Applications/{args.id}"
            output, status_code = self._application_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success, which is valid
            if status_code == 204:
                print(f"Success! LaML Application {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
                if not valid:
                    print(f"Error deleting application: {output}")
        else:
            print("Delete operation cancelled\n")

    def _application_func(self, query_params="", req_type="GET", payload=""):
        """Get project ID from environment and construct API destination"""
        from functions import get_environment
        _, project_id, _ = get_environment()  # Need to get the project ID from the environment to hit the correct API endpoint.
        destination = f"{api_destination}/{project_id}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)