#!/usr/bin/env python3
import cmd2
import json
from .base import BaseCommand
from functions import http_request

# SIP PROFILE API LOCATION
api_destination = "api/relay/rest/sip_profile"

class SipProfileCommand(BaseCommand):
    """SIP Profile management commands"""
    
    def get_parser(self):
        """Create and return the argument parser for sip_profile commands"""
        # Create the top level parser for sip profiles
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='SIP PROFILE', help='sip_profile help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List SIP Profiles')
        list_parser.add_argument('-j', '--json', action='store_true', help='Output SIP Profile(s) in JSON format')
        list_parser.set_defaults(func='list_sip_profiles')

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a SIP Profile')
        update_parser.add_argument('-d', '--domain-identifier', help='Domain Identifier of the SIP profile')
        update_parser.add_argument('-s', '--send-as', help='Default Caller ID for SIP Endpoints')
        update_parser.add_argument('-e', '--encryption', type=str, help='Set Default encryption option for SIP Profile [required|optional]', 
                                 choices=['required', 'optional'])
        update_parser.add_argument('--default-codecs', type=str, nargs='+', help='Set Default Codecs for SIP Profile', 
                                 choices=['OPUS', 'G722', 'PCMU', 'PCMA', 'VP8', 'H264'])
        update_parser.add_argument('--default-ciphers', type=str, nargs='+', help='Set Default Ciphers for SIP Profile', 
                                 choices=['AEAD_AES_256_GCM_8','AES_256_CM_HMAC_SHA1_80','AES_CM_128_HMAC_SHA1_80',
                                         'AES_256_CM_HMAC_SHA1_32','AES_CM_128_HMAC_SHA1_32'])
        update_parser.set_defaults(func='update_sip_profile')

        return base_parser
    
    def handle_command(self, args):
        """Handle sip_profile command routing"""
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('sip_profile')

    def list_sip_profiles(self, args):
        """List SIP Profiles"""
        
        output, status_code = self._sip_profile_func()
        valid = self.handle_standard_response(output, status_code)
        
        if valid:
            self.display_output(output, json_format=args.json)
        else:
            print(f"Error: {output}")

    def update_sip_profile(self, args):
        """Update a SIP Profile"""
        
        # There is only one SIP Profile, this doesn't actually matter and is not required.
        # if not args.domain_identifier:
        #     print("Domain identifier is required to update the SIP Profile\n")
        #     return
            
        payload = self._build_payload(args)

        output, status_code = self._sip_profile_func(req_type="PUT", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)
        
        if valid:
            print(f"Complete. SIP Profile {args.domain_identifier} has been updated.\n")

    def _build_payload(self, args):
        """Build payload for SIP Profile operations"""
        keys = ["domain_identifier", "send_as", "encryption", "default_codecs", "default_ciphers"]
        
        payload_data = {}
        for k, v in vars(args).items():
            if k in keys and v is not None:
                if k in ["default_codecs", "default_ciphers"]:
                    # codecs and ciphers are always lists
                    payload_data[k] = v if isinstance(v, list) else [v]
                elif isinstance(v, list):
                    payload_data[k] = ' '.join(v)
                else:
                    payload_data[k] = v

        return (payload_data)

    def _sip_profile_func(self, query_params="", req_type="GET", payload={}):
        """SIP Profile API wrapper"""
        destination = f"{api_destination}{query_params}"
        response = http_request(destination, req_type, payload)        
        return (response.text, response.status_code)