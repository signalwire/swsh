#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request, get_environment

# MESSAGE API LOCATION (Compatibility API)
api_destination = "api/laml/2010-04-01/Accounts"
#


class MessageCommand(BaseCommand):
    """Message (SMS/MMS) management commands"""

    def get_parser(self):
        """Create and return the argument parser for message commands"""
        # Create the top level parser for messages
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='MESSAGES', help='message help')

        # Send subcommand (create/send a message)
        send_parser = subparsers.add_parser('send', help='Send an SMS or MMS message')
        send_parser.add_argument('-t', '--to-num', help='Recipient phone number (E.164 format)', required=True)
        send_parser.add_argument('-f', '--from-num', help='Sender phone number or short code (must be a SignalWire number)')
        send_parser.add_argument('-b', '--body', nargs='+', help='Message body text (max 1600 characters)')
        send_parser.add_argument('-m', '--media-url', nargs='+', help='URL(s) of media to attach (MMS). Max 10 URLs, 5MB combined')
        send_parser.add_argument('--messaging-service-sid', help='Number Group ID for automatic sender selection (alternative to --from-num)')
        send_parser.add_argument('--status-callback', help='Webhook URL for message status updates')
        send_parser.add_argument('--application-sid', help='cXML Application SID for status callbacks')
        send_parser.add_argument('--max-price', help='Maximum acceptable message cost in USD (e.g., 0.0075)')
        send_parser.add_argument('--validity-period', type=int, help='Queue timeout in seconds (default: 14400)')
        send_parser.set_defaults(func='send_message')

        # List subcommand (retrieve message logs)
        list_parser = subparsers.add_parser('list', help='List messages for the project')
        list_parser.add_argument('-i', '--id', help='Retrieve a specific message by SignalWire ID')
        list_parser.add_argument('-j', '--json', action='store_true', help='Output messages in JSON format')
        list_parser.add_argument('--status', help='Filter messages by status',
                                choices=['queued', 'sending', 'sent', 'failed', 'delivered', 'undelivered', 'receiving', 'received'])
        list_parser.add_argument('--date-sent', help='Filter by date sent (YYYY-MM-DD). Use < or > prefix for ranges')
        list_parser.add_argument('--from-num', help='Filter messages from this phone number')
        list_parser.add_argument('--to-num', help='Filter messages to this phone number')
        list_parser.add_argument('--page-size', type=int, help='Number of results per page (default: 50, max: 1000)')
        list_parser.set_defaults(func='list_messages')

        # Get subcommand (alias for list with id)
        get_parser = subparsers.add_parser('get', help='Get a specific message by ID (alias for list --id)')
        get_parser.add_argument('-i', '--id', help='SignalWire ID of the message', required=True)
        get_parser.add_argument('-j', '--json', action='store_true', help='Output message in JSON format')
        get_parser.set_defaults(func='get_message')

        # Update subcommand (redact message body)
        update_parser = subparsers.add_parser('update', help='Update/redact a message body')
        update_parser.add_argument('-i', '--id', help='SignalWire ID of the message to update', required=True)
        update_parser.add_argument('-b', '--body', nargs='*', help='New message body. Leave empty to redact', default=None)
        update_parser.add_argument('--redact', action='store_true', help='Redact the message body (set to empty)')
        update_parser.set_defaults(func='update_message')

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete a message')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the message to delete', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force deletion. Will not ask to confirm')
        delete_parser.set_defaults(func='delete_message')

        # Media subcommand group
        media_parser = subparsers.add_parser('media', help='Manage message media files (MMS attachments)')
        media_subparsers = media_parser.add_subparsers(title='MESSAGE MEDIA', help='message media help')

        # Media list subcommand
        media_list_parser = media_subparsers.add_parser('list', help='List media files for a message')
        media_list_parser.add_argument('--message-id', help='SignalWire ID of the message', required=True)
        media_list_parser.add_argument('-j', '--json', action='store_true', help='Output media in JSON format')
        media_list_parser.set_defaults(func='list_message_media')

        # Media get subcommand
        media_get_parser = media_subparsers.add_parser('get', help='Get a specific media file')
        media_get_parser.add_argument('--message-id', help='SignalWire ID of the message', required=True)
        media_get_parser.add_argument('--media-id', help='SignalWire ID of the media', required=True)
        media_get_parser.add_argument('-j', '--json', action='store_true', help='Output media in JSON format')
        media_get_parser.set_defaults(func='get_message_media')

        # Media delete subcommand
        media_delete_parser = media_subparsers.add_parser('delete', help='Delete a media file')
        media_delete_parser.add_argument('--message-id', help='SignalWire ID of the message', required=True)
        media_delete_parser.add_argument('--media-id', help='SignalWire ID of the media to delete', required=True)
        media_delete_parser.add_argument('-f', '--force', action='store_true', help='Force deletion. Will not ask to confirm')
        media_delete_parser.set_defaults(func='delete_message_media')

        return base_parser

    def handle_command(self, args):
        """
        Handle message command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('message')

    def send_message(self, args):
        """
        Send an SMS or MMS message
        """

        # Validate mutual exclusivity and requirements
        has_body = args.body and len(args.body) > 0
        has_media = args.media_url and len(args.media_url) > 0

        if not has_body and not has_media:
            print("Error: Must specify either --body or --media-url (or both)\n")
            return

        # Validate sender - need either from-num or messaging-service-sid
        if not args.from_num and not args.messaging_service_sid:
            print("Error: Must specify either --from-num or --messaging-service-sid\n")
            return

        payload_parts = []

        # Required parameters
        payload_parts.append(f"To={urllib.parse.quote(args.to_num)}")

        # Sender - From or MessagingServiceSid
        if args.messaging_service_sid:
            payload_parts.append(f"MessagingServiceSid={urllib.parse.quote(args.messaging_service_sid)}")
        elif args.from_num:
            payload_parts.append(f"From={urllib.parse.quote(args.from_num)}")

        # Message body
        if has_body:
            body_text = ' '.join(args.body)
            if len(body_text) > 1600:
                print(f"Warning: Message body exceeds 1600 characters ({len(body_text)} chars). Message may be split.\n")
            payload_parts.append(f"Body={urllib.parse.quote(body_text)}")

        # Media URLs (for MMS)
        if has_media:
            if len(args.media_url) > 10:
                print("Error: Maximum 10 media URLs allowed per message\n")
                return
            for url in args.media_url:
                payload_parts.append(f"MediaUrl={urllib.parse.quote(url)}")

        # Optional parameters
        if args.status_callback:
            payload_parts.append(f"StatusCallback={urllib.parse.quote(args.status_callback)}")
        if args.application_sid:
            payload_parts.append(f"ApplicationSid={urllib.parse.quote(args.application_sid)}")
        if args.max_price:
            payload_parts.append(f"MaxPrice={urllib.parse.quote(args.max_price)}")
        if args.validity_period:
            payload_parts.append(f"ValidityPeriod={args.validity_period}")

        payload = "&".join(payload_parts)

        output, status_code = self._message_func("/Messages", req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            message_sid = output_json.get("sid", "unknown")
            message_status = output_json.get("status", "unknown")
            print(f"Message sent successfully! SID: {message_sid}, Status: {message_status}\n")

    def list_messages(self, args):
        """
        List messages with optional filtering
        """

        query_params = "/Messages"
        if args.id:
            query_params = f"/Messages/{args.id}"
        else:
            # Build query parameters for filtering
            filter_params = []
            if args.status:
                filter_params.append(f"Status={urllib.parse.quote(args.status)}")
            if args.date_sent:
                # Handle date range operators (< or >)
                if args.date_sent.startswith('<') or args.date_sent.startswith('>'):
                    operator = args.date_sent[0]
                    date_value = args.date_sent[1:]
                    if operator == '<':
                        filter_params.append(f"DateSent<{urllib.parse.quote(date_value)}")
                    else:
                        filter_params.append(f"DateSent>{urllib.parse.quote(date_value)}")
                else:
                    filter_params.append(f"DateSent={urllib.parse.quote(args.date_sent)}")
            if args.from_num:
                filter_params.append(f"From={urllib.parse.quote(args.from_num)}")
            if args.to_num:
                filter_params.append(f"To={urllib.parse.quote(args.to_num)}")
            if args.page_size:
                filter_params.append(f"PageSize={args.page_size}")

            if filter_params:
                query_params += "?" + "&".join(filter_params)

        output, status_code = self._message_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)

            if args.json:
                if args.id:
                    self.display_output(output, json_format=True)
                else:
                    messages_data = output_json.get("messages", [])
                    self.display_output(json.dumps(messages_data), json_format=True)
            else:
                if args.id:
                    self.display_output(output, json_format=False)
                else:
                    messages_data = output_json.get("messages", [])
                    if not messages_data:
                        print("No messages found\n")
                    else:
                        self.display_output(json.dumps({"data": messages_data}), json_format=False)
        else:
            print(f"Error retrieving messages: {output}")

    def get_message(self, args):
        """
        Get a specific message by ID (convenience wrapper for list with id)
        """

        if not args.id:
            print("Message SID is required\n")
            return

        query_params = f"/Messages/{args.id}"
        output, status_code = self._message_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                self.display_output(output, json_format=False)
        else:
            print(f"Error retrieving message: {output}")

    def update_message(self, args):
        """
        Update/redact a message body
        """

        if not args.id:
            print("Message SID is required to update a message\n")
            return

        # Determine the new body value
        if args.redact:
            new_body = ""
        elif args.body is not None:
            new_body = ' '.join(args.body) if args.body else ""
        else:
            print("Error: Must specify --body or --redact to update a message\n")
            return

        query_params = f"/Messages/{args.id}"
        payload = f"Body={urllib.parse.quote(new_body)}"

        output, status_code = self._message_func(query_params, req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            if args.redact or not new_body:
                print(f"Complete. Message {args.id} has been redacted.\n")
            else:
                print(f"Complete. Message {args.id} body has been updated.\n")

    def delete_message(self, args):
        """
        Delete a message
        """

        if not args.id:
            print("Message SID is required to delete a message\n")
            return

        if self.confirm_deletion("Message", args.id, args.force):
            query_params = f"/Messages/{args.id}"
            output, status_code = self._message_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success
            if status_code == 204:
                print(f"Success! Message {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
                if not valid:
                    # Check if message is in progress
                    if "in progress" in output.lower():
                        print(f"Error: Message {args.id} is in progress and cannot be deleted\n")
                    else:
                        print(f"Error deleting message: {output}")
        else:
            print("Delete operation cancelled\n")

    # Message Media operations
    def list_message_media(self, args):
        """
        List media files for a specific message
        """

        if not args.message_id:
            print("Message SID is required to list media\n")
            return

        query_params = f"/Messages/{args.message_id}/Media"
        output, status_code = self._message_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            media_data = output_json.get("media_list", [])

            if hasattr(args, 'json') and args.json:
                self.display_output(json.dumps(media_data), json_format=True)
            else:
                if not media_data:
                    print("No media found for this message\n")
                else:
                    self.display_output(json.dumps({"data": media_data}), json_format=False)
        else:
            print(f"Error retrieving message media: {output}")

    def get_message_media(self, args):
        """
        Get a specific media file for a message
        """

        if not args.message_id:
            print("Message SID is required\n")
            return

        if not args.media_id:
            print("Media SID is required\n")
            return

        query_params = f"/Messages/{args.message_id}/Media/{args.media_id}"
        output, status_code = self._message_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                self.display_output(output, json_format=False)
        else:
            print(f"Error retrieving message media: {output}")

    def delete_message_media(self, args):
        """
        Delete a media file for a message
        """

        if not args.message_id:
            print("Message SID is required\n")
            return

        if not args.media_id:
            print("Media SID is required to delete media\n")
            return

        if self.confirm_deletion("Message Media", args.media_id, args.force):
            query_params = f"/Messages/{args.message_id}/Media/{args.media_id}"
            output, status_code = self._message_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success
            if status_code == 204:
                print(f"Success! Media {args.media_id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
                if not valid:
                    print(f"Error deleting message media: {output}")
        else:
            print("Delete operation cancelled\n")

    def _message_func(self, query_params="", req_type="GET", payload=""):
        """Get project ID from environment and construct API destination"""
        _, project_id, _ = get_environment()
        destination = f"{api_destination}/{project_id}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)
