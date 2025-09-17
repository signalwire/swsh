#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request

# PHONE NUMBER API LOCATION
api_destination = "api/relay/rest/phone_numbers"
#

class PhoneNumberCommand(BaseCommand):
    """Phone Number management commands"""

    def get_parser(self):
        """Create and return the argument parser for phone_number commands"""
        # Create the top level parser for phone numbers
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='PHONE NUMBER', help='phone_number help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List Phone Numbers for a Project')
        list_parser.add_argument('-j', '--json', action='store_true', help='List Phone Numbers for project in JSON Format')
        list_parser.add_argument('-s', '--short', action='store_true', help='Show only phone numbers (short format)')
        list_parser.add_argument('-n', '--name', nargs='+', help='Find a phone number by object Name')
        list_parser.add_argument('-i', '--id', help='Find a phone number by SignalWire ID')
        list_parser.add_argument('-N', '--number', help='Return a phone number by number in E164 format')
        list_parser.set_defaults(func=self.list_phone_numbers)

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a Phone Number')
        update_parser.add_argument('-i', '--id', help='ID of the SignalWire Phone Number')
        update_parser.add_argument('-N', '--number', help='The phone number being updated')
        update_parser.add_argument('-n', '--name', nargs='+', help='Update the Friendly Name of a Phone Number')

        # Call handling options (updated to match official API documentation)
        update_parser.add_argument('--call-handler', help='What type of handler you want to run on inbound calls',
                                 choices=["relay_script", "relay_context", "relay_topic", "relay_application", "laml_webhooks", "laml_application", "dialogflow", "relay_connector", "relay_sip_endpoint", "relay_verto_endpoint", "video_room"])
        update_parser.add_argument('--call-receive-mode', help='How do you want to receive the incoming call. Possible values are: voice or fax. Default is voice', choices=["voice", "fax"])
        update_parser.add_argument('--call-request-url', help='The URL to make a request to when using the laml_webhooks call handler')
        update_parser.add_argument('--call-request-method', help='The HTTP method to use when making a request to the call_request_url. Possible values are: POST or GET. Default is POST', choices=["POST", "GET"])
        update_parser.add_argument('--call-fallback-url', help='The fallback URL to make a request to when using the laml_webhooks call handler and the call_request_url fails')
        update_parser.add_argument('--call-fallback-method', help='The HTTP method to use when making a request to the call_fallback_url. Possible values are: POST or GET. Default is POST', choices=["POST", "GET"])
        update_parser.add_argument('--call-status-callback-url', help='The URL to make status callbacks to when using the laml_webhooks call handler')
        update_parser.add_argument('--call-status-callback-method', help='The HTTP method to use when making a request to the call_status_callback_url. Possible values are: POST or GET. Default is POST', choices=["POST", "GET"])
        update_parser.add_argument('--call-laml-application-id', help='The ID of the LaML Application to use when using the laml_application call handler')
        update_parser.add_argument('--call-dialogflow-agent-id', help='The ID of the Dialogflow Agent to start when using the dialogflow call handler')
        update_parser.add_argument('--call-relay-topic', help='A string representing the Relay topic to forward incoming calls to. This is only used (and required) when call_handler is set to relay_topic')
        update_parser.add_argument('--call-relay-topic-status-callback-url', help='A string representing a URL to send status change messages to. This is only used (and required) when call_handler is set to relay_topic')
        update_parser.add_argument('--call-relay-script-url', help='The URL to make a request to when using the relay_script call handler. The URL must respond with a valid SWML script')
        update_parser.add_argument('--call-relay-context', help='[DEPRECATED] The name of the Relay Context to send this call to when using the relay_context call handler. Use --call-relay-application instead')
        update_parser.add_argument('--call-relay-context-status-callback-url', help='[DEPRECATED] A string representing a URL to send status change messages to. This is only used when call_handler is set to relay_context')
        update_parser.add_argument('--call-relay-application', help='The name of the Relay Application to send this call to when using the relay_application call handler. Alias of call_relay_context. If both are sent, call_relay_application takes precedence')
        update_parser.add_argument('--call-relay-connector-id', help='The ID of the Relay Connector to send this call to when using the relay_connector call handler')
        update_parser.add_argument('--call-sip-endpoint-id', help='The ID of the Relay SIP Endpoint to send this call to when using the relay_sip_endpoint call handler')
        update_parser.add_argument('--call-verto-resource', help='The name of the Verto Relay Endpoint to send this call to when using the relay_verto_endpoint call handler')
        update_parser.add_argument('--call-video-room-id', help='The ID of the Video Room to send this call to when using the video_room call handler')

        # Message handling options (updated to match official API documentation)
        update_parser.add_argument('--message-handler', help='What type of handler you want to run on inbound messages. Possible values are: relay_context, relay_topic, relay_application, laml_webhooks, laml_application', choices=["relay_context", "relay_topic", "relay_application", "laml_webhooks", "laml_application"])
        update_parser.add_argument('--message-request-url', help='The URL to make a request to when using the laml_webhooks message handler')
        update_parser.add_argument('--message-request-method', help='The HTTP method to use when making a request to the message_request_url. Possible values are: POST or GET. Default is POST', choices=["POST", "GET"])
        update_parser.add_argument('--message-fallback-url', help='The fallback URL to make a request to when using the laml_webhooks message handler and the message_request_url fails')
        update_parser.add_argument('--message-fallback-method', help='The HTTP method to use when making a request to the message_fallback_url. Possible values are: POST or GET. Default is POST', choices=["POST", "GET"])
        update_parser.add_argument('--message-laml-application-id', help='The ID of the LaML Application to use when using the laml_application message handler')
        update_parser.add_argument('--message-relay-topic', help='The name of the Relay Topic to send this message to when using the relay_topic message handler. Alias of message_relay_application. If both are sent, message_relay_application takes precedence')
        update_parser.add_argument('--message-relay-context', help='[DEPRECATED] The name of the Relay Context to send this message to when using the relay_context message handler. Use --message-relay-application instead')
        update_parser.add_argument('--message-relay-application', help='The name of the Relay Application to send this message to when using the relay_application message handler. Alias of message_relay_context. If both are sent, message_relay_application takes precedence')
        update_parser.set_defaults(func=self.update_phone_number)

        # Release subcommand
        release_parser = subparsers.add_parser('release', help='Release/Remove a Phone Number')
        release_parser.add_argument('-i', '--id', help='The SignalWire ID of the number that is being Released (Removed)')
        release_parser.add_argument('-n', '--number', help='Number to be Released (Removed)')
        release_parser.add_argument('-f', '--force', action='store_true', help='Force release. Will not ask to confirm release of Phone Number')
        release_parser.set_defaults(func=self.release_phone_number)

        # Lookup subcommand
        lookup_parser = subparsers.add_parser('lookup', help='Lookup a Phone Number (in E.164 format)')
        lookup_parser.add_argument('--number', help='Number you want to lookup (in E.164 format)', required=True)
        lookup_parser.add_argument('--cnam', action='store_true', help='Include CNAM lookup')
        lookup_parser.add_argument('--carrier', action='store_true', help='Include carrier lookup')
        lookup_parser.add_argument('-j', '--json', action='store_true', help='Output lookup results in JSON format')
        lookup_parser.set_defaults(func=self.lookup_phone_number)

        # Buy subcommand
        buy_parser = subparsers.add_parser('buy', help='Purchase Phone numbers for the Project')
        buy_parser.add_argument('--starts-with', help='Filter numbers that start with these digits')
        buy_parser.add_argument('--contains', help='Filter numbers that contain these digits')
        buy_parser.add_argument('--ends-with', help='Filter numbers that end with these digits')
        buy_parser.add_argument('--max-results', type=int, default=10, help='Maximum number of results to show (default: 10)')
        buy_parser.set_defaults(func=self.buy_phone_number)

        return base_parser

    def handle_command(self, args):
        """
        Handle phone_number command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func = getattr(args, 'func', None)
        if func is not None:
            func(args)
        else:
            self.shell.do_help('phone_number')

    def list_phone_numbers(self, args):
        """
        List phone numbers with optional filtering
        """

        query_params = ""
        if args.id:
            query_params = f"/{args.id}"
        elif args.name or args.number:
            filters = {}
            if args.name:
                filters['filter_name'] = ' '.join(args.name)
            if args.number:
                filters['filter_number'] = args.number
            query_params = self.build_query_params_with_filters(**filters)

        output, status_code = self._phone_number_func(query_params, req_type="GET")
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
                    if hasattr(args, 'short') and args.short:
                        # Use short format (just phone numbers)
                        self._print_phone_number_list(data)
                    else:
                        # Use detailed format (like other commands)
                        self.display_output(json.dumps({"data": data}), json_format=False)
        else:
            print(f"Error: {output}")

    def update_phone_number(self, args):
        """
        Update a phone number configuration
        """

        # Validate conditional requirements first
        if not self.validate_conditional_requirements(args):
            return

        # Get the SID either from ID or by looking up the number
        sid, display_name = self._get_phone_number_sid(args.id, args.number)
        if not sid:
            return

        query_params = f"/{sid}"

        payload = self._build_payload(args)
        if not payload:
            print("No update parameters provided\n")
            return
        output, status_code = self._phone_number_func(query_params, req_type="PUT", payload=payload)
        valid = self.handle_standard_response(output, status_code)

        if valid:
            output_json = json.loads(output)
            phone_number = output_json.get("number", sid)
            print(f"Complete. Phone Number {phone_number} has been updated.\n")

    def release_phone_number(self, args):
        """
        Release/remove a phone number
        """

        sid, number_display = self._get_phone_number_sid(args.id, args.number)
        if not sid:
            return

        if self.confirm_deletion("Phone Number", number_display, args.force):
            query_params = f"/{sid}"
            output, status_code = self._phone_number_func(query_params, req_type="DELETE")
            valid = self.handle_standard_response(output, status_code)

            if valid:
                print(f"Success! Phone Number {number_display} Released\n")
        else:
            print("Release operation cancelled\n")

    def lookup_phone_number(self, args):
        """
        Lookup phone number information
        """

        # Validate E.164 format
        if not self.validate_e164_or_error(args.number):
            return

        query_params = args.number
        if args.cnam or args.carrier:
            lookup_type = []
            if args.cnam:
                lookup_type.append("cnam")
            if args.carrier:
                lookup_type.append("carrier")
            query_params += f"?type={','.join(lookup_type)}"

        lookup_destination = "api/relay/rest/lookup/phone_number/"
        output, status_code = self._phone_number_func(query_params=query_params, destination_override=lookup_destination)
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    def buy_phone_number(self, args):
        """
        Purchase a new phone number with improved interface
        """
        # TODO: Revist this.  It works, but it can be improved.

        # Determine search filters
        filter_type = None
        filter_value = None

        if args.starts_with:
            filter_type = "starts_with"
            filter_value = args.starts_with
        elif args.contains:
            filter_type = "contains"
            filter_value = args.contains
        elif args.ends_with:
            filter_type = "ends_with"
            filter_value = args.ends_with
        else:
            # Interactive mode - ask user for filter
            print("How would you like to filter available numbers?")
            print("1) Begins With")
            print("2) Contains")
            print("3) Ends With")
            print("4) No Filter")

            selection = input("\nPlease make a selection: ").strip()

            if selection == "1":
                filter_type = "starts_with"
                filter_value = input("Number begins with: ").strip()
            elif selection == "2":
                filter_type = "contains"
                filter_value = input("Number contains: ").strip()
            elif selection == "3":
                filter_type = "ends_with"
                filter_value = input("Number ends with: ").strip()
            elif selection == "4":
                filter_type = None
                filter_value = None
            else:
                print("ERROR: That is not a valid selection\n")
                return

        # Search for available numbers
        available_numbers = self._search_available_numbers(filter_type, filter_value, args.max_results)
        if not available_numbers:
            print("No available numbers found with the specified criteria\n")
            return

        # Display available numbers
        print(f"\nFound {len(available_numbers)} available numbers:\n")
        self.display_output(json.dumps({"data": available_numbers}), json_format=False)

        # Get user selection
        try:
            selection_input = input(f"Enter a number (1-{len(available_numbers)}) to select, or 'q' to quit: ").strip()

            # Check for quit option
            if selection_input.lower() in ['q', 'quit', 'exit']:
                print("Number selection cancelled\n")
                return

            selection = int(selection_input)
            if selection < 1 or selection > len(available_numbers):
                print(f"ERROR: Please enter a number between 1 and {len(available_numbers)}\n")
                return

            selected_number = available_numbers[selection - 1]["e164"]
        except ValueError:
            print("ERROR: Please enter a valid number or 'q' to quit\n")
            return
        except IndexError:
            print("ERROR: Invalid selection\n")
            return

        # Confirm purchase
        confirm = input(f"\nPlease confirm the purchase of {selected_number}. This will charge your account (Y/n): ")
        if confirm.lower() not in ['y', 'yes']:
            print("Purchase cancelled\n")
            return

        # Purchase the number
        success, number_id = self._purchase_number(selected_number)
        if success:
            print(f"Congratulations! You have just added {selected_number} to your SignalWire project!")
            print(f"The SignalWire ID of that number is {number_id}. Use it to start building cool stuff!\n")
        else:
            print(f"Failed to purchase number {selected_number}\n")

    def _search_available_numbers(self, filter_type, filter_value, max_results):
        """
        Search for available phone numbers
        """

        query_params = f"search?max_results={max_results}"
        if filter_type and filter_value:
            query_params += f"&{filter_type}={urllib.parse.quote(filter_value)}"

        output, status_code = self._phone_number_func(f"/{query_params}", req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            output_json = json.loads(output)
            return output_json.get("data", [])
        return []

    def _purchase_number(self, phone_number):
        """
        Purchase a phone number and set initial name
        """

        # Purchase the number
        payload = json.dumps({"number": phone_number})
        output, status_code = self._phone_number_func("", req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code)

        if not valid:
            return False, None

        response_json = json.loads(output)
        number_id = response_json.get("id")

        if not number_id:
            return False, None

        # Set initial name to the phone number (workaround for API requirement)
        name_payload = json.dumps({"name": phone_number})
        update_output, update_status = self._phone_number_func(f"/{number_id}", req_type="PUT", payload=name_payload)
        self.handle_standard_response(update_output, update_status)

        return True, number_id

    def _print_phone_number_list(self, numbers_data):
        """
        Print phone numbers in simple list format
        """

        if not numbers_data:
            print("No Phone Numbers found\n")
            return

        for number in numbers_data:
            print(number.get("number", "N/A"))
        print("")

    def validate_conditional_requirements(self, args):
        """
        Validate conditional argument dependencies based on API documentation

        Returns:
            bool: True if all requirements are met, False otherwise
        """
        errors = []

        # Message handler validation
        if hasattr(args, 'message_handler') and args.message_handler:
            if args.message_handler == 'relay_context':
                if not getattr(args, 'message_relay_context', None):
                    errors.append("--message-relay-context is required when using --message-handler relay_context")
            elif args.message_handler == 'relay_topic':
                if not getattr(args, 'message_relay_topic', None):
                    errors.append("--message-relay-topic is required when using --message-handler relay_topic")
            elif args.message_handler == 'relay_application':
                if not getattr(args, 'message_relay_application', None):
                    errors.append("--message-relay-application is required when using --message-handler relay_application")
            elif args.message_handler == 'laml_webhooks':
                if not getattr(args, 'message_request_url', None):
                    errors.append("--message-request-url is required when using --message-handler laml_webhooks")
            elif args.message_handler == 'laml_application':
                if not getattr(args, 'message_laml_application_id', None):
                    errors.append("--message-laml-application-id is required when using --message-handler laml_application")

        # Call handler validation
        if hasattr(args, 'call_handler') and args.call_handler:
            if args.call_handler == 'relay_context':
                if not getattr(args, 'call_relay_context', None):
                    errors.append("--call-relay-context is required when using --call-handler relay_context")
            elif args.call_handler == 'relay_topic':
                if not getattr(args, 'call_relay_topic', None):
                    errors.append("--call-relay-topic is required when using --call-handler relay_topic")
                # Note: call_relay_topic_status_callback_url is also required but not enforcing for now
            elif args.call_handler == 'relay_application':
                if not getattr(args, 'call_relay_application', None):
                    errors.append("--call-relay-application is required when using --call-handler relay_application")
            elif args.call_handler == 'laml_webhooks':
                if not getattr(args, 'call_request_url', None):
                    errors.append("--call-request-url is required when using --call-handler laml_webhooks")
            elif args.call_handler == 'laml_application':
                if not getattr(args, 'call_laml_application_id', None):
                    errors.append("--call-laml-application-id is required when using --call-handler laml_application")
            elif args.call_handler == 'dialogflow':
                if not getattr(args, 'call_dialogflow_agent_id', None):
                    errors.append("--call-dialogflow-agent-id is required when using --call-handler dialogflow")
            elif args.call_handler == 'relay_connector':
                if not getattr(args, 'call_relay_connector_id', None):
                    errors.append("--call-relay-connector-id is required when using --call-handler relay_connector")
            elif args.call_handler == 'relay_sip_endpoint':
                if not getattr(args, 'call_sip_endpoint_id', None):
                    errors.append("--call-sip-endpoint-id is required when using --call-handler relay_sip_endpoint")
            elif args.call_handler == 'relay_script':
                if not getattr(args, 'call_relay_script_url', None):
                    errors.append("--call-relay-script-url is required when using --call-handler relay_script")
            elif args.call_handler == 'relay_verto_endpoint':
                if not getattr(args, 'call_verto_resource', None):
                    errors.append("--call-verto-resource is required when using --call-handler relay_verto_endpoint")
            elif args.call_handler == 'video_room':
                if not getattr(args, 'call_video_room_id', None):
                    errors.append("--call-video-room-id is required when using --call-handler video_room")

        # Print errors if any
        if errors:
            print("Validation Error(s):")
            for error in errors:
                print(f"  • {error}")
            print(f"\nExample usage:")
            if hasattr(args, 'message_handler') and args.message_handler:
                if args.message_handler == 'relay_context':
                    print("  phone_number update --number +1234567890 --message-handler relay_context --message-relay-context my_app")
                elif args.message_handler == 'laml_webhooks':
                    print("  phone_number update --number +1234567890 --message-handler laml_webhooks --message-request-url https://example.com/webhook")
            if hasattr(args, 'call_handler') and args.call_handler:
                if args.call_handler == 'relay_context':
                    print("  phone_number update --number +1234567890 --call-handler relay_context --call-relay-context my_app")
                elif args.call_handler == 'laml_webhooks':
                    print("  phone_number update --number +1234567890 --call-handler laml_webhooks --call-request-url https://example.com/webhook")
            print()
            return False

        return True

    def _get_phone_number_sid(self, id_arg, number_arg):
        """
        Get SID from either ID or phone number lookup

        Args:
            id_arg: Phone number ID argument (could be None)
            number_arg: Phone number argument (could be None)

        Returns:
            tuple: (sid, display_name) or (None, None) if error/not found
        """
        if id_arg:
            return id_arg, id_arg  # sid, display_name
        elif number_arg:
            query_params = f"?filter_number={urllib.parse.quote(number_arg)}"
            output, status_code = self._phone_number_func(query_params, req_type="GET")
            valid = self.handle_standard_response(output, status_code)
            if not valid:
                print("An error has occurred. Please check number and retry\n")
                return None, None
            else:
                output_json = json.loads(output)
                data = output_json.get("data", [])
                if data:
                    return data[0].get("id"), number_arg
                else:
                    print("Phone number not found\n")
                    return None, None
        else:
            print("A valid SignalWire ID or Phone Number is required.\n")
            return None, None

    def _build_payload(self, args):
        """Build payload for phone number operations based on official API documentation"""
        keys = [
            "name", "call_handler", "call_receive_mode", "call_request_url", "call_request_method",
            "call_fallback_url", "call_fallback_method", "call_status_callback_url", "call_status_callback_method",
            "call_laml_application_id", "call_dialogflow_agent_id", "call_relay_topic", "call_relay_topic_status_callback_url",
            "call_relay_script_url", "call_relay_context", "call_relay_context_status_callback_url", "call_relay_application",
            "call_relay_connector_id", "call_sip_endpoint_id", "call_verto_resource", "call_video_room_id",
            "message_handler", "message_request_url", "message_request_method", "message_fallback_url",
            "message_fallback_method", "message_laml_application_id", "message_relay_topic", "message_relay_context",
            "message_relay_application"
        ]

        payload_data = {}
        for k, v in vars(args).items():
            if k in keys and v is not None:
                if isinstance(v, list):
                    payload_data[k] = ' '.join(v)
                else:
                    payload_data[k] = v

        return json.dumps(payload_data) if payload_data else None

    def _phone_number_func(self, query_params="", req_type="GET", payload={}, destination_override=None):
        if destination_override:
            destination = f"{destination_override}{query_params}"
        else:
            destination = f"{api_destination}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)