#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request

# CALL API LOCATION (Compatibility API)
api_destination = "api/laml/2010-04-01/Accounts"
#

class CallCommand(BaseCommand):
    """Call management commands"""

    def get_parser(self):
        """Create and return the argument parser for call commands"""
        # Create the top level parser for calls
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='CALLS', help='call help')

        # Send subcommand (create a call)
        send_parser = subparsers.add_parser('send', help='Send an outbound call')
        send_parser.add_argument('-f', '--from-num', help='Calling Party Number -- Must be a SignalWire Number', required=True)
        send_parser.add_argument('-t', '--to-num', help='Receiving Party Number', required=True)
        send_parser.add_argument('-u', '--url', help='URL of LaML document to execute when call connects')
        send_parser.add_argument('--laml-bin-id', help='SignalWire ID of a LaML Bin to execute when call connects')
        send_parser.add_argument('--method', help='HTTP method to use when requesting the URL', choices=['POST', 'GET'], default='POST')
        send_parser.add_argument('--fallback-url', help='URL to try if the URL fails')
        send_parser.add_argument('--fallback-method', help='HTTP method to use when requesting the fallback URL', choices=['POST', 'GET'], default='POST')
        send_parser.add_argument('--status-callback', help='URL to send status change notifications')
        send_parser.add_argument('--status-callback-method', help='HTTP method to use for status callbacks', choices=['POST', 'GET'], default='POST')
        send_parser.add_argument('--status-callback-event', nargs='+', help='Events that trigger status callbacks',
                               choices=['initiated', 'ringing', 'answered', 'completed'])
        send_parser.add_argument('--timeout', type=int, help='Time to wait for call to be answered (seconds)', default=60)
        send_parser.add_argument('--record', action='store_true', help='Record the call')
        send_parser.add_argument('--record-channels', help='Channels to record', choices=['mono', 'dual'], default='mono')
        send_parser.add_argument('--record-format', help='Format for call recording', choices=['mp3', 'wav'], default='mp3')
        send_parser.add_argument('--trim', help='Trim silence from recordings', choices=['trim-silence', 'do-not-trim'], default='trim-silence')
        send_parser.add_argument('--caller-id', help='Phone number to use as caller ID')
        send_parser.add_argument('--send-digits', help='DTMF digits to send when call connects')
        send_parser.add_argument('--if-machine', help='Action to take if answering machine detected', choices=['continue', 'hangup'])
        send_parser.add_argument('--if-machine-url', help='URL to request if answering machine detected')
        send_parser.add_argument('--machine-detection', help='Enable answering machine detection', choices=['enable', 'DetectMessageEnd'])
        send_parser.add_argument('--machine-detection-timeout', type=int, help='Time to wait for machine detection (seconds)')
        send_parser.add_argument('--machine-detection-speech-threshold', type=int, help='Milliseconds of speech before considering human')
        send_parser.add_argument('--machine-detection-speech-end-threshold', type=int, help='Milliseconds of silence to detect speech end')
        send_parser.add_argument('--machine-detection-silence-timeout', type=int, help='Milliseconds of silence before considering machine')
        send_parser.set_defaults(func=self.send_call)

        # Get subcommand (retrieve call details)
        get_parser = subparsers.add_parser('get', help='Retrieve call details and logs')
        get_parser.add_argument('-i', '--id', help='Retrieve call logs for the SignalWire ID')
        get_parser.add_argument('--all-active', action='store_true', help='Return all currently active calls for the project')
        get_parser.add_argument('-j', '--json', action='store_true', help='Output call details in JSON format')
        get_parser.add_argument('--status', help='Filter calls by status',
                              choices=['queued', 'ringing', 'in-progress', 'completed', 'failed', 'busy', 'no-answer', 'canceled'])
        get_parser.add_argument('--start-time', help='Filter calls started on or after this date (YYYY-MM-DD)')
        get_parser.add_argument('--end-time', help='Filter calls started on or before this date (YYYY-MM-DD)')
        get_parser.add_argument('--from-num', help='Filter calls from this phone number')
        get_parser.add_argument('--to-num', help='Filter calls to this phone number')
        get_parser.add_argument('--parent-call-sid', help='Filter calls that are children of this call')
        get_parser.set_defaults(func=self.get_call)

        # Lookup subcommand (alias for get)
        lookup_parser = subparsers.add_parser('lookup', help='Lookup call details (alias for get)')
        lookup_parser.add_argument('-i', '--id', help='Retrieve call logs for the SignalWire ID')
        lookup_parser.add_argument('--all-active', action='store_true', help='Return all currently active calls for the project')
        lookup_parser.add_argument('-j', '--json', action='store_true', help='Output call details in JSON format')
        lookup_parser.add_argument('--status', help='Filter calls by status',
                                 choices=['queued', 'ringing', 'in-progress', 'completed', 'failed', 'busy', 'no-answer', 'canceled'])
        lookup_parser.add_argument('--start-time', help='Filter calls started on or after this date (YYYY-MM-DD)')
        lookup_parser.add_argument('--end-time', help='Filter calls started on or before this date (YYYY-MM-DD)')
        lookup_parser.add_argument('--from-num', help='Filter calls from this phone number')
        lookup_parser.add_argument('--to-num', help='Filter calls to this phone number')
        lookup_parser.add_argument('--parent-call-sid', help='Filter calls that are children of this call')
        lookup_parser.set_defaults(func=self.get_call)  # Same function as get

        # Update subcommand (modify an active call)
        update_parser = subparsers.add_parser('update', help='Update an active call')
        update_parser.add_argument('-i', '--id', help='SignalWire ID of the call to update', required=True)
        update_parser.add_argument('--url', help='New URL to request for the call')
        update_parser.add_argument('--method', help='HTTP method to use when requesting the URL', choices=['POST', 'GET'])
        update_parser.add_argument('--status', help='New status for the call', choices=['canceled', 'completed'])
        update_parser.add_argument('--fallback-url', help='New fallback URL for the call')
        update_parser.add_argument('--fallback-method', help='HTTP method for fallback URL', choices=['POST', 'GET'])
        update_parser.add_argument('--status-callback', help='New status callback URL')
        update_parser.add_argument('--status-callback-method', help='HTTP method for status callbacks', choices=['POST', 'GET'])
        update_parser.set_defaults(func=self.update_call)

        # Delete subcommand (terminate/delete a call)
        delete_parser = subparsers.add_parser('delete', help='Delete/Terminate a call')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the call to delete', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force deletion. Will not ask to confirm delete of call')
        delete_parser.set_defaults(func=self.delete_call)

        return base_parser

    def handle_command(self, args):
        """
        Handle call command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func = getattr(args, 'func', None)
        if func is not None:
            func(args)
        else:
            self.shell.do_help('call')

    def send_call(self, args):
        """
        Send an outbound call
        """

        # Validate mutual exclusivity between url and laml-bin-id
        if args.url and args.laml_bin_id:
            print("Error: Cannot specify both --url and --laml-bin-id. Choose one.\n")
            return

        if not args.url and not args.laml_bin_id:
            print("Error: Must specify either --url or --laml-bin-id\n")
            return

        payload_parts = []

        # Required parameters
        payload_parts.append(f"From={urllib.parse.quote(args.from_num)}")
        payload_parts.append(f"To={urllib.parse.quote(args.to_num)}")

        # Handle URL or LaML Bin ID
        if args.laml_bin_id:
            # Get the URL from the LaML Bin ID
            laml_url = self._get_laml_bin_url(args.laml_bin_id)
            if not laml_url:
                return  # Error already printed in helper function
            payload_parts.append(f"Url={urllib.parse.quote(laml_url)}")
        elif args.url:
            payload_parts.append(f"Url={urllib.parse.quote(args.url)}")

        # Optional parameters
        if args.method:
            payload_parts.append(f"Method={urllib.parse.quote(args.method)}")
        if args.fallback_url:
            payload_parts.append(f"FallbackUrl={urllib.parse.quote(args.fallback_url)}")
        if args.fallback_method:
            payload_parts.append(f"FallbackMethod={urllib.parse.quote(args.fallback_method)}")
        if args.status_callback:
            payload_parts.append(f"StatusCallback={urllib.parse.quote(args.status_callback)}")
        if args.status_callback_method:
            payload_parts.append(f"StatusCallbackMethod={urllib.parse.quote(args.status_callback_method)}")
        if args.status_callback_event:
            events = ' '.join(args.status_callback_event)
            payload_parts.append(f"StatusCallbackEvent={urllib.parse.quote(events)}")
        if args.timeout:
            payload_parts.append(f"Timeout={args.timeout}")
        if args.record:
            payload_parts.append("Record=true")
        if args.record_channels:
            payload_parts.append(f"RecordChannels={urllib.parse.quote(args.record_channels)}")
        if args.record_format:
            payload_parts.append(f"RecordFormat={urllib.parse.quote(args.record_format)}")
        if args.trim:
            payload_parts.append(f"Trim={urllib.parse.quote(args.trim)}")
        if args.caller_id:
            payload_parts.append(f"CallerId={urllib.parse.quote(args.caller_id)}")
        if args.send_digits:
            payload_parts.append(f"SendDigits={urllib.parse.quote(args.send_digits)}")
        if args.if_machine:
            payload_parts.append(f"IfMachine={urllib.parse.quote(args.if_machine)}")
        if args.if_machine_url:
            payload_parts.append(f"IfMachineUrl={urllib.parse.quote(args.if_machine_url)}")
        if args.machine_detection:
            payload_parts.append(f"MachineDetection={urllib.parse.quote(args.machine_detection)}")
        if args.machine_detection_timeout:
            payload_parts.append(f"MachineDetectionTimeout={args.machine_detection_timeout}")
        if args.machine_detection_speech_threshold:
            payload_parts.append(f"MachineDetectionSpeechThreshold={args.machine_detection_speech_threshold}")
        if args.machine_detection_speech_end_threshold:
            payload_parts.append(f"MachineDetectionSpeechEndThreshold={args.machine_detection_speech_end_threshold}")
        if args.machine_detection_silence_timeout:
            payload_parts.append(f"MachineDetectionSilenceTimeout={args.machine_detection_silence_timeout}")

        payload = "&".join(payload_parts)

        output, status_code = self._call_func("/Calls", req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            call_sid = output_json.get("sid", "unknown")
            print(f"Call sent successfully! Call SID: {call_sid}\n")
        else:
            print(f"Error sending call: {output}")

    def get_call(self, args):
        """
        Retrieve call details and logs (also used by lookup command)
        """

        query_params = "/Calls"
        if args.id:
            query_params = f"/Calls/{args.id}"
        else:
            # Build query parameters for filtering
            filter_params = []
            if args.status:
                filter_params.append(f"Status={urllib.parse.quote(args.status)}")
            if args.start_time:
                filter_params.append(f"StartTime={urllib.parse.quote(args.start_time)}")
            if args.end_time:
                filter_params.append(f"EndTime={urllib.parse.quote(args.end_time)}")
            if args.from_num:
                filter_params.append(f"From={urllib.parse.quote(args.from_num)}")
            if args.to_num:
                filter_params.append(f"To={urllib.parse.quote(args.to_num)}")
            if args.parent_call_sid:
                filter_params.append(f"ParentCallSid={urllib.parse.quote(args.parent_call_sid)}")

            if filter_params:
                query_params += "?" + "&".join(filter_params)

        output, status_code = self._call_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)

            if args.all_active and not args.id:
                # Filter for active calls only
                all_calls = output_json.get("calls", [])
                active_calls = [call for call in all_calls if call.get("status") == "in-progress"]

                if not active_calls:
                    print("No active calls found\n")
                    return

                if args.json:
                    self.display_output(json.dumps(active_calls), json_format=True)
                else:
                    self.display_output(json.dumps({"data": active_calls}), json_format=False)

            elif args.json:
                if args.id:
                    self.display_output(output, json_format=True)
                else:
                    calls_data = output_json.get("calls", [])
                    self.display_output(json.dumps(calls_data), json_format=True)
            else:
                if args.id:
                    self.display_output(output, json_format=False)
                else:
                    calls_data = output_json.get("calls", [])
                    self.display_output(json.dumps({"data": calls_data}), json_format=False)
        else:
            print(f"Error retrieving call: {output}")

    def update_call(self, args):
        """
        Update an active call
        """

        if not args.id:
            print("Call SID is required to update a call\n")
            return

        # Check if at least one parameter is provided for update
        update_params = [args.url, args.method, args.status, args.fallback_url,
                        args.fallback_method, args.status_callback, args.status_callback_method]

        if not any(param for param in update_params):
            print("At least one parameter is required to update a call\n")
            return

        query_params = f"/Calls/{args.id}"
        payload_parts = []

        # Handle optional parameters
        if args.url:
            payload_parts.append(f"Url={urllib.parse.quote(args.url)}")
        if args.method:
            payload_parts.append(f"Method={urllib.parse.quote(args.method)}")
        if args.status:
            payload_parts.append(f"Status={urllib.parse.quote(args.status)}")
        if args.fallback_url:
            payload_parts.append(f"FallbackUrl={urllib.parse.quote(args.fallback_url)}")
        if args.fallback_method:
            payload_parts.append(f"FallbackMethod={urllib.parse.quote(args.fallback_method)}")
        if args.status_callback:
            payload_parts.append(f"StatusCallback={urllib.parse.quote(args.status_callback)}")
        if args.status_callback_method:
            payload_parts.append(f"StatusCallbackMethod={urllib.parse.quote(args.status_callback_method)}")

        payload = "&".join(payload_parts)

        output, status_code = self._call_func(query_params, req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            call_status = output_json.get("status", "unknown")
            print(f"Complete. Call {args.id} has been updated. Status: {call_status}\n")

    def delete_call(self, args):
        """
        Delete/terminate a call
        """

        if not args.id:
            print("Call SID is required to delete a call\n")
            return

        if self.confirm_deletion("Call", args.id, args.force):
            query_params = f"/Calls/{args.id}"
            output, status_code = self._call_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success, which is valid
            if status_code == 204:
                print(f"Success! Call {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
                if not valid:
                    print(f"Error deleting call: {output}")
        else:
            print("Delete operation cancelled\n")

    def _get_laml_bin_url(self, laml_bin_id):
        """
        Get the URL from a LaML Bin ID
        """

        query_params = f"/LamlBins/{laml_bin_id}"
        output, status_code = self._call_func(query_params, req_type="GET")

        if status_code == 200:
            try:
                output_json = json.loads(output)
                return output_json.get("uri", None)
            except json.JSONDecodeError:
                print("Error: Invalid JSON response from LaML Bin lookup\n")
                return None
        else:
            print(f"Error: Could not retrieve LaML Bin {laml_bin_id}. Status: {status_code}\n")
            return None

    def _call_func(self, query_params="", req_type="GET", payload=""):
        """Get project ID from environment and construct API destination"""
        from functions import get_environment
        _, project_id, _ = get_environment()  # Need to get the project ID from the environment to hit the correct API endpoint.
        destination = f"{api_destination}/{project_id}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)