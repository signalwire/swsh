#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request, get_environment

# FIFO QUEUE API LOCATION (Compatibility API)
api_destination = f"api/laml/2010-04-01/Accounts"
#

class FifoQueueCommand(BaseCommand):
    """FIFO Queue management commands"""

    def get_parser(self):
        """Create and return the argument parser for fifo_queue commands"""
        # Create the top level parser for FIFO queues
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='FIFO QUEUES', help='fifo_queue help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List FIFO Queues for a Project')
        list_parser.add_argument('-i', '--id', help='List a Single FIFO Queue by SignalWire ID')
        list_parser.add_argument('-j', '--json', action='store_true', help='Output FIFO Queue(s) in JSON format')
        list_parser.set_defaults(func='list_queues')

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create a FIFO Queue')
        create_parser.add_argument('-n', '--name', nargs='+', help='Friendly name of the FIFO Queue', required=True)
        create_parser.add_argument('-m', '--maxsize', help='The maximum number of calls that are allowed to wait in a queue. Default is 5.', default='5')
        create_parser.set_defaults(func='create_queue')

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a FIFO Queue')
        update_parser.add_argument('-i', '--id', help='SignalWire ID of the FIFO Queue', required=True)
        update_parser.add_argument('-n', '--name', nargs='+', help='Friendly name of the FIFO Queue')
        update_parser.add_argument('-m', '--maxsize', help='The maximum number of calls that are allowed to wait in a queue.')
        update_parser.set_defaults(func='update_queue')

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete/Remove a FIFO Queue')
        delete_parser.add_argument('-i', '--id', help='SignalWire ID of the FIFO Queue to be deleted', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force removal. Will not ask to confirm delete of FIFO Queue')
        delete_parser.set_defaults(func='delete_queue')

        return base_parser

    def handle_command(self, args):
        """
        Handle fifo_queue command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('fifo_queue')

    def list_queues(self, args):
        """
        List FIFO queues with optional filtering
        """

        query_params = f"/Queues"
        if args.id:
            query_params = f"/Queues/{args.id}"

        output, status_code = self._queue_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            if args.json:
                output_json = json.loads(output)
                if args.id:
                    # Single queue - display as-is
                    self.display_output(output, json_format=True)
                else:
                    # Multiple queues - extract queues data
                    queues_data = output_json.get("queues", [])
                    self.display_output(json.dumps(queues_data), json_format=True)
            else:
                output_json = json.loads(output)
                if args.id:
                    # Single queue - display formatted
                    self.display_output(output, json_format=False)
                else:
                    # Multiple queues - extract and format queues data only
                    queues_data = output_json.get("queues", [])
                    self.display_output(json.dumps({"data": queues_data}), json_format=False)
        else:
            print(f"Error: {output}")

    def create_queue(self, args):
        """
        Create a new FIFO queue
        """

        if not args.name:
            print("Error: name is required for create\n")
            return

        friendly_name = ' '.join(args.name)
        payload = f"FriendlyName={urllib.parse.quote(friendly_name)}"

        if args.maxsize:
            payload += f"&MaxSize={urllib.parse.quote(args.maxsize)}"

        output, status_code = self._queue_func("/Queues", req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            queue_sid = output_json.get("sid", "unknown")
            queue_name = output_json.get("friendly_name", friendly_name)
            print(f"Success! FIFO Queue '{queue_name}' created with SID: {queue_sid}\n")

    def update_queue(self, args):
        """
        Update an existing FIFO queue
        """

        if not args.id:
            print("Queue SID is required to update a queue\n")
            return

        if not args.name and not args.maxsize:
            print("At least one parameter (name or maxsize) is required to update a queue\n")
            return

        query_params = f"/Queues/{args.id}"
        payload_parts = []

        if args.name:
            friendly_name = ' '.join(args.name)
            payload_parts.append(f"FriendlyName={urllib.parse.quote(friendly_name)}")

        if args.maxsize:
            payload_parts.append(f"MaxSize={urllib.parse.quote(args.maxsize)}")

        payload = "&".join(payload_parts)

        output, status_code = self._queue_func(query_params, req_type="POST", payload=payload)
        valid = self.handle_standard_response(output, status_code, compatibility_mode=True)

        if valid:
            output_json = json.loads(output)
            queue_name = output_json.get("friendly_name", "Queue")
            print(f"Complete. FIFO Queue '{queue_name}' (SID: {args.id}) has been updated.\n")

    def delete_queue(self, args):
        """
        Delete/remove a FIFO queue
        """

        if not args.id:
            print("Queue SID is required to delete a queue\n")
            return

        if self.confirm_deletion("FIFO Queue", args.id, args.force):
            query_params = f"/Queues/{args.id}"
            output, status_code = self._queue_func(query_params, req_type="DELETE")

            # DELETE returns 204 No Content on success, which is valid
            if status_code == 204:
                print(f"Success! FIFO Queue {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=True)
                if not valid:
                    print(f"Error deleting queue: {output}")
        else:
            print("Delete operation cancelled\n")

    def _queue_func(self, query_params="", req_type="GET", payload=""):
        _, project_id, _ = get_environment() # Need to get the project ID from the environment to hit the correct API endpoint.
        destination = f"{api_destination}/{project_id}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)