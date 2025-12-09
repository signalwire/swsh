#!/usr/bin/env python3
import cmd2
import json
import time
import urllib.parse
from .base import BaseCommand
from functions import http_request, get_environment

# FAX API LOCATION (Compatibility API)
# Endpoint: /api/laml/2010-04-01/Accounts/{AccountSid}/Faxes
api_destination = "api/laml/2010-04-01/Accounts"
#


class FaxCommand(BaseCommand):
    """Fax management commands"""

    def get_parser(self):
        """Create and return the argument parser for fax commands"""
        # Create the top level parser for fax
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='FAX', help='fax help')

        # Send subcommand (create/send a fax)
        send_parser = subparsers.add_parser('send', help='Send a fax')
        send_parser.add_argument('-t', '--to-num', help='Destination phone number (E.164 format)', required=True)
        send_parser.add_argument('-f', '--from-num', help='Sender phone number (must be a SignalWire number)', required=True)
        send_parser.add_argument('-m', '--media-url', help='URL of the PDF file to fax', required=True)
        send_parser.add_argument('-q', '--quality', help='Fax quality', choices=['standard', 'fine', 'superfine'], default='fine')
        send_parser.add_argument('--status-callback', help='Webhook URL for fax status updates')
        send_parser.add_argument('--ttl', type=int, help='Time-to-live in minutes before attempting to send')
        send_parser.add_argument('-b', '--background', action='store_true', help='Send fax in background without waiting for completion')
        send_parser.set_defaults(func='send_fax')

        # List subcommand (retrieve fax logs)
        list_parser = subparsers.add_parser('list', help='List faxes for the project')
        list_parser.add_argument('-i', '--id', help='Retrieve a specific fax by SignalWire ID')
        list_parser.add_argument('-j', '--json', action='store_true', help='Output faxes in JSON format')
        list_parser.add_argument('--sent', action='store_true', help='Show only sent (outbound) faxes')
        list_parser.add_argument('--received', action='store_true', help='Show only received (inbound) faxes')
        list_parser.add_argument('--from-num', help='Filter faxes from this phone number')
        list_parser.add_argument('--to-num', help='Filter faxes to this phone number')
        list_parser.add_argument('--date-created-after', help='Filter faxes created after this date (YYYY-MM-DD)')
        list_parser.add_argument('--date-created-before', help='Filter faxes created on or before this date (YYYY-MM-DD)')
        list_parser.add_argument('--page-size', type=int, help='Number of results per page (default: 50)')
        list_parser.set_defaults(func='list_faxes')

        # Get subcommand (alias for list with id)
        get_parser = subparsers.add_parser('get', help='Get a specific fax by ID (alias for list --id)')
        get_parser.add_argument('-i', '--id', help='SignalWire ID of the fax', required=True)
        get_parser.add_argument('-j', '--json', action='store_true', help='Output fax in JSON format')
        get_parser.set_defaults(func='get_fax')

        # Update subcommand (cancel a fax)
        update_parser = subparsers.add_parser('update', help='Update/cancel a fax')
        update_parser.add_argument('-i', '--id', help='SignalWire ID of the fax to update', required=True)
        update_parser.add_argument('-s', '--status', help='New status (only "canceled" is supported)', choices=['canceled'], required=True)
        update_parser.set_defaults(func='update_fax')

        # Cancel subcommand (alias for update --status canceled)
        cancel_parser = subparsers.add_parser('cancel', help='Cancel a fax (alias for update --status canceled)')
        cancel_parser.add_argument('-i', '--id', help='SignalWire ID of the fax to cancel', required=True)
        cancel_parser.set_defaults(func='cancel_fax')

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete a fax record')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the fax to delete', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force deletion. Will not ask to confirm')
        delete_parser.set_defaults(func='delete_fax')

        # Media subcommand group
        media_parser = subparsers.add_parser('media', help='Manage fax media files')
        media_subparsers = media_parser.add_subparsers(title='FAX MEDIA', help='fax media help')

        # Media list subcommand
        media_list_parser = media_subparsers.add_parser('list', help='List media files for a fax')
        media_list_parser.add_argument('--fax-id', help='SignalWire ID of the fax', required=True)
        media_list_parser.add_argument('-j', '--json', action='store_true', help='Output media in JSON format')
        media_list_parser.set_defaults(func='list_fax_media')

        # Media get subcommand
        media_get_parser = media_subparsers.add_parser('get', help='Get a specific media file')
        media_get_parser.add_argument('--fax-id', help='SignalWire ID of the fax', required=True)
        media_get_parser.add_argument('--media-id', help='SignalWire ID of the media', required=True)
        media_get_parser.add_argument('-j', '--json', action='store_true', help='Output media in JSON format')
        media_get_parser.set_defaults(func='get_fax_media')

        # Media delete subcommand
        media_delete_parser = media_subparsers.add_parser('delete', help='Delete a media file')
        media_delete_parser.add_argument('--fax-id', help='SignalWire ID of the fax', required=True)
        media_delete_parser.add_argument('--media-id', help='SignalWire ID of the media to delete', required=True)
        media_delete_parser.add_argument('-f', '--force', action='store_true', help='Force deletion. Will not ask to confirm')
        media_delete_parser.set_defaults(func='delete_fax_media')

        media_parser.set_defaults(func='media_help')

        # Logs subcommand group
        logs_parser = subparsers.add_parser('logs', help='View fax logs')
        logs_subparsers = logs_parser.add_subparsers(title='FAX LOGS', help='fax logs help')

        # Logs list subcommand
        logs_list_parser = logs_subparsers.add_parser('list', help='List fax logs')
        logs_list_parser.add_argument('-j', '--json', action='store_true', help='Output logs in JSON format')
        logs_list_parser.set_defaults(func='list_fax_logs')

        # Logs get subcommand
        logs_get_parser = logs_subparsers.add_parser('get', help='Get a specific fax log by ID')
        logs_get_parser.add_argument('-i', '--id', help='Log ID to retrieve', required=True)
        logs_get_parser.add_argument('-j', '--json', action='store_true', help='Output log in JSON format')
        logs_get_parser.set_defaults(func='get_fax_log')

        logs_parser.set_defaults(func='logs_help')

        return base_parser

    def handle_command(self, args):
        """
        Handle fax command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('fax')

    def send_fax(self, args):
        """
        Send a fax
        """

        payload_parts = []

        # Required parameters
        payload_parts.append(f"To={urllib.parse.quote(args.to_num)}")
        payload_parts.append(f"From={urllib.parse.quote(args.from_num)}")
        payload_parts.append(f"MediaUrl={urllib.parse.quote(args.media_url)}")

        # Optional parameters
        if args.quality:
            payload_parts.append(f"Quality={urllib.parse.quote(args.quality)}")
        if args.status_callback:
            payload_parts.append(f"StatusCallback={urllib.parse.quote(args.status_callback)}")
        if args.ttl:
            payload_parts.append(f"Ttl={args.ttl}")

        payload = "&".join(payload_parts)

        print(f"Sending a fax from {args.from_num} to {args.to_num}")

        output, status_code = self._fax_func("/Faxes", req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            fax_sid = output_json.get("sid", "unknown")

            if args.background:
                print(f"Fax queued successfully! SID: {fax_sid}\n")
                print("Backgrounding...\n")
            else:
                # Poll for status updates
                self._poll_fax_status(fax_sid)

    def _poll_fax_status(self, fax_sid, max_iterations=200):
        """
        Poll for fax status until completion or timeout
        """
        terminal_statuses = ['delivered', 'busy', 'failed', 'no-answer', 'canceled']
        status_messages = {
            'delivered': "Delivered Successfully!",
            'busy': "ERROR: The fax machine was busy. Please try again.",
            'failed': "ERROR: The fax failed to send. Please try again.",
            'no-answer': "ERROR: The fax machine did not answer. Please try again.",
            'canceled': "Fax was canceled."
        }

        for _ in range(max_iterations):
            query_params = f"/Faxes/{fax_sid}"
            output, status_code = self._fax_func(query_params, req_type="GET")

            if status_code == 200:
                output_json = json.loads(output)
                status = output_json.get("status", "unknown")
                duration = output_json.get("duration", "0")

                print(f"| Status: {status} | | Duration: {duration}|", end='\r')

                if status in terminal_statuses:
                    print()  # New line after progress
                    print(f"{status_messages.get(status, f'Fax completed with status: {status}')}\n")
                    return status == 'delivered'
            else:
                print("\nError checking fax status\n")
                return False

            time.sleep(3)

        print("\nTimeout waiting for fax completion\n")
        return False

    def list_faxes(self, args):
        """
        List faxes with optional filtering
        """

        query_params = "/Faxes"
        if args.id:
            query_params = f"/Faxes/{args.id}"
        else:
            # Build query parameters for filtering
            filter_params = []
            if args.from_num:
                filter_params.append(f"From={urllib.parse.quote(args.from_num)}")
            if args.to_num:
                filter_params.append(f"To={urllib.parse.quote(args.to_num)}")
            if args.date_created_after:
                filter_params.append(f"DateCreatedAfter={urllib.parse.quote(args.date_created_after)}")
            if args.date_created_before:
                filter_params.append(f"DateCreatedOnOrBefore={urllib.parse.quote(args.date_created_before)}")
            if args.page_size:
                filter_params.append(f"PageSize={args.page_size}")

            if filter_params:
                query_params += "?" + "&".join(filter_params)

        output, status_code = self._fax_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)

            if args.id:
                # Single fax
                if hasattr(args, 'json') and args.json:
                    self.display_output(output, json_format=True)
                else:
                    self.display_output(output, json_format=False)
            else:
                # Multiple faxes - filter by direction if requested
                faxes_data = output_json.get("faxes", [])

                if args.sent:
                    faxes_data = [f for f in faxes_data if f.get("direction") == "outbound"]
                    if not faxes_data:
                        print("No sent faxes found\n")
                        return
                elif args.received:
                    faxes_data = [f for f in faxes_data if f.get("direction") == "inbound"]
                    if not faxes_data:
                        print("No received faxes found\n")
                        return

                if hasattr(args, 'json') and args.json:
                    self.display_output(json.dumps(faxes_data), json_format=True)
                else:
                    if not faxes_data:
                        print("No faxes found\n")
                    else:
                        self.display_output(json.dumps({"data": faxes_data}), json_format=False)
        else:
            print(f"Error retrieving faxes: {output}")

    def get_fax(self, args):
        """
        Get a specific fax by ID (convenience wrapper for list with id)
        """

        if not args.id:
            print("Fax SID is required\n")
            return

        query_params = f"/Faxes/{args.id}"
        output, status_code = self._fax_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                self.display_output(output, json_format=False)
        else:
            print(f"Error retrieving fax: {output}")

    def update_fax(self, args):
        """
        Update/cancel a fax
        """

        if not args.id:
            print("Fax SID is required to update a fax\n")
            return

        query_params = f"/Faxes/{args.id}"
        payload = f"Status={urllib.parse.quote(args.status)}"

        output, status_code = self._fax_func(query_params, req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            print(f"Complete. Fax {args.id} status has been updated to: {args.status}\n")

    def cancel_fax(self, args):
        """
        Cancel a fax (convenience wrapper for update --status canceled)
        """

        if not args.id:
            print("Fax SID is required to cancel a fax\n")
            return

        query_params = f"/Faxes/{args.id}"
        payload = "Status=canceled"

        output, status_code = self._fax_func(query_params, req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            print(f"Complete. Fax {args.id} has been canceled.\n")

    def delete_fax(self, args):
        """
        Delete a fax record
        """

        if not args.id:
            print("Fax SID is required to delete a fax\n")
            return

        if self.confirm_deletion("Fax", args.id, args.force):
            query_params = f"/Faxes/{args.id}"
            output, status_code = self._fax_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success
            if status_code == 204:
                print(f"Success! Fax {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
                if not valid:
                    print(f"Error deleting fax: {output}")
        else:
            print("Delete operation cancelled\n")

    # Fax Media operations
    def list_fax_media(self, args):
        """
        List media files for a specific fax
        """

        if not args.fax_id:
            print("Fax SID is required to list media\n")
            return

        query_params = f"/Faxes/{args.fax_id}/Media"
        output, status_code = self._fax_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            media_data = output_json.get("media", [])

            if hasattr(args, 'json') and args.json:
                self.display_output(json.dumps(media_data), json_format=True)
            else:
                if not media_data:
                    print("No media found for this fax\n")
                else:
                    self.display_output(json.dumps({"data": media_data}), json_format=False)
        else:
            print(f"Error retrieving fax media: {output}")

    def get_fax_media(self, args):
        """
        Get a specific media file for a fax
        """

        if not args.fax_id:
            print("Fax SID is required\n")
            return

        if not args.media_id:
            print("Media SID is required\n")
            return

        query_params = f"/Faxes/{args.fax_id}/Media/{args.media_id}"
        output, status_code = self._fax_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                self.display_output(output, json_format=False)
        else:
            print(f"Error retrieving fax media: {output}")

    def delete_fax_media(self, args):
        """
        Delete a media file for a fax
        """

        if not args.fax_id:
            print("Fax SID is required\n")
            return

        if not args.media_id:
            print("Media SID is required to delete media\n")
            return

        if self.confirm_deletion("Fax Media", args.media_id, args.force):
            query_params = f"/Faxes/{args.fax_id}/Media/{args.media_id}"
            output, status_code = self._fax_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success
            if status_code == 204:
                print(f"Success! Media {args.media_id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
                if not valid:
                    print(f"Error deleting fax media: {output}")
        else:
            print("Delete operation cancelled\n")

    # Fax Logs operations
    def media_help(self, args):
        """Show media subcommand help"""
        print("Usage: fax media {list,get,delete} [options]")
        print("\nMedia subcommands:")
        print("  list     List media files for a fax")
        print("  get      Get a specific media file")
        print("  delete   Delete a media file")
        print("\nUse 'fax media <subcommand> -h' for more information.\n")

    def logs_help(self, args):
        """Show logs subcommand help"""
        print("Usage: fax logs {list,get} [options]")
        print("\nLogs subcommands:")
        print("  list     List fax logs")
        print("  get      Get a specific fax log by ID")
        print("\nUse 'fax logs <subcommand> -h' for more information.\n")

    def list_fax_logs(self, args):
        """
        List fax logs
        """
        output, status_code = self._fax_logs_func("/logs", req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                self.display_output(output, json_format=False)

    def get_fax_log(self, args):
        """
        Get a specific fax log by ID
        """
        if not args.id:
            print("Log ID is required\n")
            return

        query_params = f"/logs/{args.id}"
        output, status_code = self._fax_logs_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                self.display_output(output, json_format=False)

    def _fax_func(self, query_params="", req_type="GET", payload=""):
        """Get project ID from environment and construct API destination"""
        _, project_id, _ = get_environment()
        destination = f"{api_destination}/{project_id}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)

    def _fax_logs_func(self, query_params="", req_type="GET", payload=""):
        """Make HTTP request to fax logs API (different base path)"""
        destination = f"api/fax{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)
