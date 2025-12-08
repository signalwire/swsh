#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request

# DOMAIN APPLICATION API LOCATION
api_destination = "api/relay/rest/domain_applications"
#

class DomainApplicationCommand(BaseCommand):
    """Domain Application management commands"""

    def get_parser(self):
        """Create and return the argument parser for domain_application commands"""
        # Create the top level parser for domain applications
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='DOMAIN APPLICATION', help='domain_application help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List Domain Applications for the Project')
        list_parser.add_argument('-d', '--domain', nargs='+', help='Return all values for given domain of Domain App')
        list_parser.add_argument('-n', '--name', nargs='+', help='Return all values for the given name of Domain App')
        list_parser.add_argument('-i', '--id', help='SignalWire ID of the Domain Application')
        list_parser.add_argument('-j', '--json', action='store_true', help='List Domain Applications in JSON Format')
        list_parser.set_defaults(func='list_domain_applications')

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create a Domain Application')
        create_parser.add_argument('-n', '--name', nargs='+', help='Friendly name for the domain application', required=True)
        create_parser.add_argument('--identifier', help='Identifier of the domain. Must be unique across the project.', required=True)
        create_parser.add_argument('--ip-auth-enabled', help='Whether the domain application will enforce IP authentication (Boolean)', choices=['true', 'false'])
        create_parser.add_argument('--ip-auth', nargs='+', help='A list of whitelisted / allowed IPs when --ip-auth-enabled is true')
        create_parser.add_argument('--call-handler', help='How the domain Application handles calls',
                                 choices=['relay_context', 'laml_webhooks', 'laml_application', 'video_room'], required=True)
        create_parser.add_argument('--call-request-url', help='The LaML URL to access when a call is received. This is only used with laml_webhooks call handler')
        create_parser.add_argument('--call-request-method', help='The HTTP method to use with call_request_url', choices=["POST", "GET"], default="POST")
        create_parser.add_argument('--call-fallback-url', help='The LaML URL to access when call_request_url fails')
        create_parser.add_argument('--call-fallback-method', help='The HTTP method to use with call_fallback_url', choices=["POST", "GET"], default="POST")
        create_parser.add_argument('--call-status-callback-url', help='The URL to send status change messages to. This is only used when call_handler is set to laml_webhooks')
        create_parser.add_argument('--call-status-callback-method', help='The HTTP method to use with call_status_callback_url', choices=["POST", "GET"], default="POST")
        create_parser.add_argument('--call-relay-context', help='Relay context to forward incoming calls to. This is only used when call_handler is set to relay_context')
        create_parser.add_argument('--call-laml-application-id', help='The ID of the LaML application to forward incoming calls to. This is only used when call_handler is set to laml_application')
        create_parser.add_argument('--call-video-room-id', help='The ID of the Video Room to forward incoming calls to. This is only used when call_handler is set to video_room')
        create_parser.add_argument('-e', '--encryption', help='Encryption setting', choices=['default', 'required', 'optional'])
        create_parser.add_argument('--codecs', nargs='+', help='Supported codecs', choices=['OPUS', 'G722', 'PCMU', 'PCMA', 'VP8', 'H264'])
        create_parser.add_argument('--ciphers', nargs='+', help='Supported ciphers',
                                 choices=['AEAD_AES_256_GCM_8', 'AES_256_CM_HMAC_SHA1_80', 'AES_CM_128_HMAC_SHA1_80', 'AES_256_CM_HMAC_SHA1_32', 'AES_CM_128_HMAC_SHA1_32'])
        create_parser.set_defaults(func='create_domain_application')

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a Domain Application')
        update_parser.add_argument('-i', '--id', help='ID of the Domain Application to be updated', required=True)
        update_parser.add_argument('-n', '--name', nargs='+', help='Friendly name for the domain application')
        update_parser.add_argument('--identifier', help='Identifier of the domain. Must be unique across the project.')
        update_parser.add_argument('--ip-auth-enabled', help='Whether the domain application will enforce IP authentication (Boolean)', choices=['true', 'false'])
        update_parser.add_argument('--ip-auth', nargs='+', help='A list of whitelisted / allowed IPs when --ip-auth-enabled is true')
        update_parser.add_argument('--call-handler', help='How the domain Application handles calls',
                                 choices=['relay_context', 'laml_webhooks', 'laml_application', 'video_room'])
        update_parser.add_argument('--call-request-url', help='The LaML URL to access when a call is received. This is only used with laml_webhooks call handler')
        update_parser.add_argument('--call-request-method', help='The HTTP method to use with call_request_url', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--call-fallback-url', help='The LaML URL to access when call_request_url fails')
        update_parser.add_argument('--call-fallback-method', help='The HTTP method to use with call_fallback_url', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--call-status-callback-url', help='The URL to send status change messages to. This is only used when call_handler is set to laml_webhooks')
        update_parser.add_argument('--call-status-callback-method', help='The HTTP method to use with call_status_callback_url', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--call-relay-context', help='Relay context to forward incoming calls to. This is only used when call_handler is set to relay_context')
        update_parser.add_argument('--call-laml-application-id', help='The ID of the LaML application to forward incoming calls to. This is only used when call_handler is set to laml_application')
        update_parser.add_argument('--call-video-room-id', help='The ID of the Video Room to forward incoming calls to. This is only used when call_handler is set to video_room')
        update_parser.add_argument('-e', '--encryption', help='Encryption setting', choices=['default', 'required', 'optional'])
        update_parser.add_argument('--codecs', nargs='+', help='Supported codecs', choices=['OPUS', 'G722', 'PCMU', 'PCMA', 'VP8', 'H264'])
        update_parser.add_argument('--ciphers', nargs='+', help='Supported ciphers',
                                 choices=['AEAD_AES_256_GCM_8', 'AES_256_CM_HMAC_SHA1_80', 'AES_CM_128_HMAC_SHA1_80', 'AES_256_CM_HMAC_SHA1_32', 'AES_CM_128_HMAC_SHA1_32'])
        update_parser.set_defaults(func='update_domain_application')

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete/Remove a Domain Application')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the Domain Application to be deleted', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force removal. Will not ask to confirm delete of Domain Application')
        delete_parser.set_defaults(func='delete_domain_application')

        return base_parser

    def handle_command(self, args):
        """
        Handle domain_application command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('domain_application')

    def list_domain_applications(self, args):
        """
        List domain applications with optional filtering
        """

        query_params = ""
        if args.id:
            query_params = f"/{args.id}"
        elif args.domain or args.name:
            filters = {}
            if args.domain:
                filters['filter_domain'] = ' '.join(args.domain)
            if args.name:
                filters['filter_name'] = ' '.join(args.name)
            query_params = self.build_query_params_with_filters(**filters)

        output, status_code = self._domain_application_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            if args.json:
                output_json = json.loads(output)
                if args.id:
                    self.display_output(output, json_format=True)
                else:
                    data = output_json.get("data", [])
                    self.display_output(json.dumps({"data": data}), json_format=True)
            else:
                if args.id:
                    self.display_output(output, json_format=False)
                else:
                    output_json = json.loads(output)
                    data = output_json.get("data", [])
                    self.display_output(json.dumps({"data": data}), json_format=False)
        else:
            print(f"Error: {output}")

    def create_domain_application(self, args):
        """
        Create a new domain application
        """

        if not self.validate_conditional_requirements(args):
            return

        payload = self._build_payload(args)
        if not payload:
            print("Error: Required parameters are missing\n")
            return

        output, status_code = self._domain_application_func("", req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code)

        if valid:
            output_json = json.loads(output)
            app_id = output_json.get("id", "unknown")
            app_name = output_json.get("name", ' '.join(args.name))
            print(f"Success! Domain Application '{app_name}' created with ID: {app_id}\n")

    def update_domain_application(self, args):
        """
        Update an existing domain application
        """

        if not args.id:
            print("Domain Application ID is required to update a domain application\n")
            return

        if not self.validate_conditional_requirements(args):
            return

        query_params = f"/{args.id}"
        payload = self._build_payload(args)
        if not payload:
            print("No update parameters provided\n")
            return

        output, status_code = self._domain_application_func(query_params, req_type="PUT", payload=payload)
        valid = self.handle_standard_response(output, status_code)

        if valid:
            output_json = json.loads(output)
            app_name = output_json.get("name", "Domain Application")
            print(f"Complete. Domain Application '{app_name}' (ID: {args.id}) has been updated.\n")

    def delete_domain_application(self, args):
        """
        Delete/remove a domain application
        """

        if not args.id:
            print("Domain Application ID is required to delete a domain application\n")
            return

        if self.confirm_deletion("Domain Application", args.id, args.force):
            query_params = f"/{args.id}"
            output, status_code = self._domain_application_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success, which is valid
            if status_code == 204:
                print(f"Success! Domain Application {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code)
                if not valid:
                    print(f"Error deleting domain application: {output}")
        else:
            print("Delete operation cancelled\n")

    def validate_conditional_requirements(self, args):
        """
        Validate conditional argument dependencies based on call handler type

        Returns:
            bool: True if all requirements are met, False otherwise
        """
        errors = []

        # Call handler validation
        if hasattr(args, 'call_handler') and args.call_handler:
            if args.call_handler == 'relay_context':
                if not getattr(args, 'call_relay_context', None):
                    errors.append("--call-relay-context is required when using --call-handler relay_context")
            elif args.call_handler == 'laml_webhooks':
                if not getattr(args, 'call_request_url', None):
                    errors.append("--call-request-url is required when using --call-handler laml_webhooks")
            elif args.call_handler == 'laml_application':
                if not getattr(args, 'call_laml_application_id', None):
                    errors.append("--call-laml-application-id is required when using --call-handler laml_application")
            elif args.call_handler == 'video_room':
                if not getattr(args, 'call_video_room_id', None):
                    errors.append("--call-video-room-id is required when using --call-handler video_room")

        # IP authentication validation
        if hasattr(args, 'ip_auth_enabled') and getattr(args, 'ip_auth_enabled') == 'true':
            if not getattr(args, 'ip_auth', None):
                errors.append("--ip-auth is required when --ip-auth-enabled is set to true")

        # Print errors if any
        if errors:
            print("Validation Error(s):")
            for error in errors:
                print(f"  • {error}")
            print(f"\nExample usage:")
            if hasattr(args, 'call_handler') and args.call_handler:
                if args.call_handler == 'relay_context':
                    print("  domain_application create --name 'My App' --identifier myapp --call-handler relay_context --call-relay-context my_context")
                elif args.call_handler == 'laml_webhooks':
                    print("  domain_application create --name 'My App' --identifier myapp --call-handler laml_webhooks --call-request-url https://example.com/webhook")
            print()
            return False

        return True

    def _build_payload(self, args):
        """Build payload for domain application operations"""
        # List of all possible parameters
        keys = [
            "name", "identifier", "ip_auth_enabled", "ip_auth", "call_handler",
            "call_request_url", "call_request_method", "call_fallback_url", "call_fallback_method",
            "call_status_callback_url", "call_status_callback_method", "call_relay_context",
            "call_laml_application_id", "call_video_room_id", "encryption", "codecs", "ciphers"
        ]

        payload_data = {}
        for k, v in vars(args).items():
            # Convert argument names with dashes to underscores for API
            api_key = k.replace('-', '_')
            if api_key in keys and v is not None:
                if isinstance(v, list):
                    if api_key == 'name':
                        payload_data[api_key] = ' '.join(v)
                    else:
                        payload_data[api_key] = v
                else:
                    payload_data[api_key] = v

        return json.dumps(payload_data) if payload_data else None

    def _domain_application_func(self, query_params="", req_type="GET", payload={}):
        destination = f"{api_destination}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)