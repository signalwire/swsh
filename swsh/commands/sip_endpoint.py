#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request

# SIP ENDPOINT API LOCATION
api_destination = "api/relay/rest/endpoints/sip"
#

class SipEndpointCommand(BaseCommand):
    """SIP Endpoint management commands"""

    def get_parser(self):
        """Create and return the argument parser for sip_endpoint commands"""
        # Create the top level parser for sip endpoints
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='SIP ENDPOINT', help='sip_endpoint help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List SIP Endpoints')
        list_parser.add_argument('-i', '--id', help='List SIP Endpoint by SignalWire ID')
        list_parser.add_argument('-j', '--json', action='store_true', help='Output SIP Endpoint(s) in JSON format')
        list_parser.add_argument('-n', '--name', type=str, nargs='+', help='Search for SIP Endpoint by username')
        list_parser.set_defaults(func=self.list_sip_endpoints)

        # Update / Create Common Arguments
        def add_common_arguments(parser):
            parser.add_argument('-u', '--username', help='Username of the SIP Endpoint')
            parser.add_argument('-p', '--password', help='Password of the SIP Endpoint')
            parser.add_argument('-s', '--send-as',  help='Default Caller ID for SIP Endpoint (Note: Must belong to the Project!)')
            parser.add_argument('-c', '--caller-id', nargs='+', help='Friendly Caller ID Name (Note: SIP to SIP only)')
            parser.add_argument('-e', '--encryption', type=str, help='Default Codecs', choices=['default', 'required', 'optional'])
            parser.add_argument('--codecs', type=str, nargs='+', help='Default Codecs', choices=['OPUS', 'G722', 'PCMU', 'PCMA', 'VP8', 'H264'])
            parser.add_argument('--ciphers', type=str, nargs='+',  help='Default Ciphers', choices=['AEAD_AES_256_GCM_8','AES_256_CM_HMAC_SHA1_80','AES_CM_128_HMAC_SHA1_80','AES_256_CM_HMAC_SHA1_32','AES_CM_128_HMAC_SHA1_32'])

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a SIP Endpoint')
        add_common_arguments(update_parser)
        update_parser.add_argument('-i', '--id', help='SignalWire ID of the SIP Endpoint to be updated')
        update_parser.set_defaults(func=self.manage_sip_endpoint, update=True)

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create a SIP Endpoint')
        add_common_arguments(create_parser)
        create_parser.set_defaults(func=self.manage_sip_endpoint, create=True)

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete a SIP Endpoint')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the SIP Endpoint to be deleted', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force delete.  Will not ask to confirm delete of SIP Endpoint')
        delete_parser.set_defaults(func=self.manage_sip_endpoint, delete=True)

        return base_parser
    
    def handle_command(self, args):
        """
        Handle sip_endpoint command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)
        
        func = getattr(args, 'func', None)
        if func is not None:
            func(args)
        else:
            self.shell.do_help('sip_endpoint')

    def list_sip_endpoints(self, args):
        """
        List SIP Endpoints with optional filtering
        """
        
        query_params = ""
        if args.id:
            query_params = f"/{args.id}"
        elif args.name:
            name = ' '.join(args.name)
            name = urllib.parse.quote(name)
            query_params = f"?filter_username={name}"

        output, status_code = self._sip_endpoint_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)
        
        if valid:
            self.display_output(output, json_format=args.json)
        else:
            print(f"Error: {output}")

    def manage_sip_endpoint(self, args):
        """
        Create / Update / Delete a SIP Endpoint
        """

        if 'delete' in args and args.delete:
            return self._delete_sip_endpoint(args)
        elif 'create' in args and args.create:
            return self._create_sip_endpoint(args)
        else:
            # Assume an update
            return self._update_sip_endpoint(args)

    def _create_sip_endpoint(self, args):
        """
        Create a new SIP Endpoint
        """
        
        required_args = ['username', 'password', 'send_as', 'caller_id']
        for arg in required_args:
            if not getattr(args, arg, None):
                print(f"Error: {arg} is required for create\n")
                return

        payload = self._build_payload(args)
        
        output, status_code = self._sip_endpoint_func(req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code)
        
        if valid:
            output_json = json.loads(output)
            endpoint_id = output_json.get("id", "unknown")
            print(f"Success! SIP Endpoint {endpoint_id} created\n")

    def _update_sip_endpoint(self, args):
        """
        Update an existing SIP Endpoint
        """
        
        if not args.id:
            print("SIP Endpoint ID is required to update a SIP Endpoint\n")
            return
            
        query_params = f"/{args.id}"

        payload = self._build_payload(args)

        output, status_code = self._sip_endpoint_func(query_params, req_type="PUT", payload=payload)
        valid = self.handle_standard_response(output, status_code)
        
        if valid:
            print(f"Complete. SIP Endpoint {args.id} has been updated.\n")

    def _delete_sip_endpoint(self, args):
        """
        Delete a SIP endpoint
        """
        
        if not args.id:
            print("SIP Endpoint ID is required for deletion\n")
            return
            
        if self.confirm_deletion("SIP Endpoint", args.id, args.force):
            query_params = f"/{args.id}"
            output, status_code = self._sip_endpoint_func(query_params, req_type="DELETE")
            valid = self.handle_standard_response(output, status_code)
            
            if valid:
                print(f"Success! SIP Endpoint {args.id} Removed\n")
        else:
            print("Delete operation cancelled\n")

    def _build_payload(self, args):
        keys = ["username", "password", "send_as", "caller_id", "encryption", "codecs", "ciphers"]
        
        payload_data = {}
        for k, v in vars(args).items():
            if k in keys and v is not None:
                if k in ["codecs", "ciphers"]:
                    # codecs and ciphers are always lists
                    payload_data[k] = v if isinstance(v, list) else [v]
                elif isinstance(v, list):
                    payload_data[k] = ' '.join(v)
                else:
                    payload_data[k] = v

        return (json.dumps(payload_data))

    def _sip_endpoint_func(self, query_params="", req_type="GET", headers={}, payload={}):
        destination = f"{api_destination}{query_params}"
        response = http_request(destination, req_type, headers, payload)
        return (response.text, response.status_code)