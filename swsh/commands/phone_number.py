#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import phone_number_func, phone_number_lookup
#from buy_a_phone_number import buy_a_phone_number


class PhoneNumberCommand(BaseCommand):
    """Phone Number management commands"""
    
    def get_parser(self):
        """Create and return the argument parser for phone_number commands"""
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='PHONE NUMBER', help='phone_number help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List Phone Numbers for a Project')
        list_parser.add_argument('-j', '--json', action='store_true', help='List Phone Numbers for project in JSON Format')
        list_parser.add_argument('-n', '--name', nargs='+', help='Find a phone number by object Name')
        list_parser.add_argument('-i', '--id', help='Find a phone number by SignalWire ID')
        list_parser.add_argument('-N', '--number', help='Return a phone number by number in E164 format')
        list_parser.set_defaults(func=self.list_numbers)

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a Phone Number')
        update_parser.add_argument('-i', '--id', help='ID of the SignalWire Phone Number')
        update_parser.add_argument('-N', '--number', help='The phone number being updated')
        update_parser.add_argument('-n', '--name', nargs='+', help='Update the Friendly Name of a Phone Number')
        
        # Call handling options
        update_parser.add_argument('--call-handler', help='Type of handlers to use when processing calls to the Number', 
                                 choices=["relay_context", "laml_webhooks", "laml_application", "dialogflow", "relay_connector", "relay_sip_endpoint", "relay_script", "relay_verto_endpoint", "video_room"])
        update_parser.add_argument('--call-receive-mode', help='How to receive the incoming call: Voice or Fax', choices=["voice", "fax"], default="voice")
        update_parser.add_argument('--call-request-url', help='URL to make a request when using the laml_webhooks call handler')
        update_parser.add_argument('--call-request-method', help='HTTP method type when using laml_webhook call handler', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--call-fallback-url', help='Secondary URL for laml_webhook call handler, in the instance the Primary webhook fails')
        update_parser.add_argument('--call-fallback-method', help='HTTP method type when using a fallback laml_webhook message handler', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--call-status-callback-url', help='URL to make status callbacks when using the laml_webhooks call handler')
        update_parser.add_argument('--call-status-callback-method', help='HTTP method type when using the call_status_callback_url', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--call-laml-application-id', help='ID of the LaML Webhook Application when using the laml_application call handler')
        update_parser.add_argument('--call-dialogflow-id', help='ID of the Dialogflow Agent to start when using the dialogflow call handler')
        update_parser.add_argument('--call-relay-context', help='The name of the Relay Context to send this call to when using the relay_context call handler')
        update_parser.add_argument('--call-relay-connector-id', help='ID of the Relay Connector to send this call to when using the relay_connector call handler')
        update_parser.add_argument('--call-relay-script-url', help='URL of the Relay Bin / SWML script')
        update_parser.add_argument('--call-sip-endpoint-id', help='ID of the SIP Endpoint to send this call to when using the sip_endpoint call handler')
        update_parser.add_argument('--call-verto-resource', help='The name of the Verto Relay endpoint to send this call to when using the relay_verto_endpoint handler')
        update_parser.add_argument('--call-video-room-id', help='The ID of the Video Room to send this call to when using the video_room call handler')
        
        # Message handling options
        update_parser.add_argument('--message-handler', help='Type of handler to use on inbound text messages', choices=["relay_context", "laml_webhook", "laml_application"])
        update_parser.add_argument('--message-request-url', help='URL used to make requests using the laml_webhook message handler')
        update_parser.add_argument('--message-request-method', help='HTTP method type when using laml_webhook message handler', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--message-fallback-url', help='Secondary URL for laml_webhook, in the instance the Primary fails')
        update_parser.add_argument('--message-fallback-method', help='HTTP method type when using laml_webhook message handler', choices=["POST", "GET"], default="POST")
        update_parser.add_argument('--message-laml-application-id', help='The ID of the LaML Application to use when using the laml_application message handler')
        update_parser.add_argument('--message-relay-context', help='The name of the relay context to send this message when using the relay_context message handler')
        update_parser.set_defaults(func=self.update_number)

        # Release subcommand
        release_parser = subparsers.add_parser('release', help='Release/Remove a Phone Number')
        release_parser.add_argument('-i', '--id', help='The SignalWire ID of the number that is being Released (Removed)')
        release_parser.add_argument('-n', '--number', help='Number to be Released (Removed)')
        release_parser.add_argument('-f', '--force', action='store_true', help='Force release. Will not ask to confirm release of Phone Number')
        release_parser.set_defaults(func=self.release_number)

        # Lookup subcommand
        lookup_parser = subparsers.add_parser('lookup', help='Lookup a Phone Number (in E.164 format)')
        lookup_parser.add_argument('--number', help='Number you want to lookup (in E.164 format)', required=True)
        lookup_parser.add_argument('--cnam', action='store_true', help='Include CNAM lookup')
        lookup_parser.add_argument('--carrier', action='store_true', help='Include carrier lookup')
        lookup_parser.set_defaults(func=self.lookup_number)

        # Buy subcommand
        buy_parser = subparsers.add_parser('buy', help='Purchase Phone numbers for the Project')
        buy_parser.set_defaults(func=self.buy_number)

        return base_parser
    
    def handle_command(self, args):
        """Handle phone_number command routing"""
        func = getattr(args, 'func', None)
        if func is not None:
            func(args)
        else:
            self.shell.do_help('phone_number')

    def list_numbers(self, args):
        """List phone numbers with optional filtering"""
        args = self.is_env_var(args)
        
        if args.json:
            output, status_code = phone_number_func()
            valid = self.handle_standard_response(output, status_code)
            if valid:
                output_json = json.loads(output)
                data_json = output_json.get("data", [])
                self.print_json_response(data_json)
                
        elif args.id:
            query_params = f"/{args.id}"
            output, status_code = phone_number_func(query_params)
            valid = self.handle_standard_response(output, status_code)
            if valid:
                output_json = json.loads(output)
                self.print_json_response(output_json)
                
        elif args.name or args.number:
            filters = {}
            if args.name:
                filters['filter_name'] = ' '.join(args.name)
            if args.number:
                filters['filter_number'] = args.number
                
            query_params = self.build_query_params_with_filters(**filters)
            output, status_code = phone_number_func(query_params)
            valid = self.handle_standard_response(output, status_code)
            if valid:
                output_json = json.loads(output)
                data_json = output_json.get("data", [])
                self.print_json_response(data_json)
        else:
            # List all phone numbers
            output, status_code = phone_number_func()
            valid = self.handle_standard_response(output, status_code)
            if valid:
                output_json = json.loads(output)
                data = output_json.get("data", [])
                self._print_multiple_phone_numbers(data)

    def update_number(self, args):
        """Update a phone number configuration"""
        args = self.is_env_var(args)
        
        # Get the SID either from ID or by looking up the number
        sid = None
        if args.id:
            sid = args.id
        elif args.number:
            query_params = f"?filter_number={urllib.parse.quote(args.number)}"
            output, status_code = phone_number_func(query_params=query_params)
            valid = self.handle_standard_response(output, status_code)
            if not valid:
                print("An error has occurred. Please check number and retry\n")
                return
            else:
                output_json = json.loads(output)
                data = output_json.get("data", [])
                if data:
                    sid = data[0].get("id")
                else:
                    print("Phone number not found\n")
                    return
        else:
            print("A valid SignalWire ID or Phone Number is required.\n")
            return
            
        query_params = f"/{sid}"
        
        # Build update data from arguments
        update_data = {
            "name": ' '.join(args.name) if args.name else None,
            "call_handler": args.call_handler,
            "call_receive_mode": args.call_receive_mode,
            "call_request_url": args.call_request_url,
            "call_request_method": args.call_request_method,
            "call_fallback_url": args.call_fallback_url,
            "call_fallback_method": args.call_fallback_method,
            "call_status_callback_url": args.call_status_callback_url,
            "call_status_callback_method": args.call_status_callback_method,
            "call_laml_application_id": args.call_laml_application_id,
            "call_dialogflow_id": args.call_dialogflow_id,
            "call_relay_context": args.call_relay_context,
            "call_relay_connector_id": args.call_relay_connector_id,
            "call_relay_script_url": args.call_relay_script_url,
            "call_sip_endpoint_id": args.call_sip_endpoint_id,
            "call_verto_resource": getattr(args, 'call_verto_resource', None),
            "call_video_room_id": args.call_video_room_id,
            "message_handler": args.message_handler,
            "message_request_url": args.message_request_url,
            "message_request_method": args.message_request_method,
            "message_fallback_url": args.message_fallback_url,
            "message_fallback_method": args.message_fallback_method,
            "message_laml_application_id": args.message_laml_application_id,
            "message_relay_context": args.message_relay_context
        }
        
        filtered_data = self.filter_none_dict(update_data)
        if not filtered_data:
            print("No update parameters provided\n")
            return
            
        payload = json.dumps(filtered_data)
        output, status_code = phone_number_func(query_params, req_type="PUT", payload=payload)
        valid = self.handle_standard_response(output, status_code)
        
        if valid:
            print(f"Complete. Phone Number {sid} has been updated.\n")

    def release_number(self, args):
        """Release/remove a phone number"""
        args = self.is_env_var(args)
        
        sid = None
        number_display = ""
        
        if args.id:
            sid = args.id
            number_display = sid
        elif args.number:
            query_params = f"?filter_number={urllib.parse.quote(args.number)}"
            output, status_code = phone_number_func(query_params=query_params)
            valid = self.handle_standard_response(output, status_code)
            if not valid:
                print("An error has occurred. Please check number and retry\n")
                return
            else:
                output_json = json.loads(output)
                data = output_json.get("data", [])
                if data:
                    sid = data[0].get("id")
                    number_display = args.number
                else:
                    print("Phone number not found\n")
                    return
        else:
            print("A valid SignalWire ID or Phone Number is required.\n")
            return
            
        if self.confirm_deletion("Phone Number", number_display, args.force):
            query_params = f"/{sid}"
            output, status_code = phone_number_func(query_params, "DELETE")
            valid = self.handle_standard_response(output, status_code)
            
            if valid:
                print(f"Success! Phone Number {number_display} Released\n")
        else:
            print("Release operation cancelled\n")

    def lookup_number(self, args):
        """Lookup phone number information"""
        args = self.is_env_var(args)
        
        query_params = args.number
        if args.cnam or args.carrier:
            lookup_type = []
            if args.cnam:
                lookup_type.append("cnam")
            if args.carrier:
                lookup_type.append("carrier")
            query_params += f"?type={','.join(lookup_type)}"
            
        phone_number_lookup(query_params)

    def buy_number(self, args):
        """Purchase a new phone number interactively"""
        args = self.is_env_var(args)
        buy_a_phone_number()

    def _print_multiple_phone_numbers(self, numbers_data):
        """Print multiple phone numbers in formatted output"""
        if not numbers_data:
            print("No Phone Numbers found\n")
            return
            
        for i, number in enumerate(numbers_data, 1):
            self._print_single_phone_number(number, str(i))

    def _print_single_phone_number(self, number_data, index):
        """Print a single phone number in formatted output"""
        print(f"{index})")
        print(f"  Phone Number ID:\t\t{number_data.get('id', 'N/A')}")
        print(f"  Phone Number:\t\t\t{number_data.get('number', 'N/A')}")
        print(f"  Friendly Name:\t\t{number_data.get('name', 'N/A')}")
        print(f"  Call Handler:\t\t\t{number_data.get('call_handler', 'N/A')}")
        print(f"  Message Handler:\t\t{number_data.get('message_handler', 'N/A')}")
        print("")
