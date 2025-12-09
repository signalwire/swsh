#!/usr/bin/env python3
import cmd2
import json
import os
import urllib.parse
from .base import BaseCommand
from functions import http_request, get_environment

# DATASPHERE API LOCATION
# Endpoint: /api/datasphere/documents
# Reference: https://developer.signalwire.com/rest/signalwire-rest/endpoints/datasphere/datasphere-api
api_destination = "api/datasphere/documents"


class DatasphereCommand(BaseCommand):
    """Datasphere document management commands - AI-powered document search"""

    def __init__(self, shell_instance):
        super().__init__(shell_instance)

    def get_parser(self):
        """Create and return the argument parser for datasphere commands"""
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='DATASPHERE', help='datasphere help')

        # List subcommand
        list_parser = subparsers.add_parser('list', help='List Datasphere Documents')
        list_parser.add_argument('-i', '--id', help='Retrieve a specific document by ID')
        list_parser.add_argument('-j', '--json', action='store_true', help='Output documents in JSON format')
        list_parser.set_defaults(func='list_documents')

        # Create subcommand
        create_parser = subparsers.add_parser('create', help='Create a Datasphere Document')
        create_parser.add_argument('-n', '--name', nargs='+', help='Name of the document', required=True)
        create_parser.add_argument('-d', '--description', nargs='+', help='Description of the document')
        create_parser.add_argument('--url', help='URL to fetch document content from')
        create_parser.add_argument('--text', nargs='+', help='Text content of the document')
        create_parser.set_defaults(func='create_document')

        # Search subcommand
        search_parser = subparsers.add_parser('search', help='Search Datasphere Documents')
        search_parser.add_argument('-q', '--query', nargs='+', help='Search query string', required=True)
        search_parser.add_argument('--document-id', help='Limit search to specific document ID')
        search_parser.add_argument('--count', type=int, help='Number of results to return')
        search_parser.add_argument('--tags', nargs='+', help='Filter by tags')
        search_parser.add_argument('--distance', type=float, help='Maximum distance for semantic search')
        search_parser.add_argument('-j', '--json', action='store_true', help='Output results in JSON format')
        search_parser.set_defaults(func='search_documents')

        # Update subcommand
        update_parser = subparsers.add_parser('update', help='Update a Datasphere Document')
        update_parser.add_argument('-i', '--id', help='Document ID to update', required=True)
        update_parser.add_argument('-n', '--name', nargs='+', help='Update the name of the document')
        update_parser.add_argument('-d', '--description', nargs='+', help='Update the description')
        update_parser.set_defaults(func='update_document')

        # Delete subcommand
        delete_parser = subparsers.add_parser('delete', help='Delete a Datasphere Document')
        delete_parser.add_argument('-i', '--id', help='Document ID to delete', required=True)
        delete_parser.add_argument('-f', '--force', action='store_true', help='Force deletion without confirmation')
        delete_parser.set_defaults(func='delete_document')

        # Chunks subcommand group
        chunks_parser = subparsers.add_parser('chunks', help='Manage document chunks')
        chunks_subparsers = chunks_parser.add_subparsers(title='CHUNKS', help='chunks help')

        # Chunks list subcommand
        chunks_list_parser = chunks_subparsers.add_parser('list', help='List chunks for a document')
        chunks_list_parser.add_argument('--document-id', help='Document ID to list chunks for', required=True)
        chunks_list_parser.add_argument('-j', '--json', action='store_true', help='Output chunks in JSON format')
        chunks_list_parser.set_defaults(func='list_chunks')

        # Chunks get subcommand
        chunks_get_parser = chunks_subparsers.add_parser('get', help='Get a specific chunk')
        chunks_get_parser.add_argument('--document-id', help='Document ID', required=True)
        chunks_get_parser.add_argument('--chunk-id', help='Chunk ID to retrieve', required=True)
        chunks_get_parser.add_argument('-j', '--json', action='store_true', help='Output chunk in JSON format')
        chunks_get_parser.set_defaults(func='get_chunk')

        # Chunks delete subcommand
        chunks_delete_parser = chunks_subparsers.add_parser('delete', help='Delete a specific chunk')
        chunks_delete_parser.add_argument('--document-id', help='Document ID', required=True)
        chunks_delete_parser.add_argument('--chunk-id', help='Chunk ID to delete', required=True)
        chunks_delete_parser.add_argument('-f', '--force', action='store_true', help='Force deletion without confirmation')
        chunks_delete_parser.set_defaults(func='delete_chunk')

        return base_parser

    def handle_command(self, args):
        """Handle datasphere command routing"""
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('datasphere')

    # Document operations
    def list_documents(self, args):
        """List Datasphere Documents"""

        query_params = ""
        if args.id:
            query_params = f"/{args.id}"

        output, status_code = self._datasphere_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=False)

        if valid:
            if args.json:
                output_json = json.loads(output)
                if args.id:
                    self.display_output(output, json_format=True)
                else:
                    docs_data = output_json.get("data", output_json)
                    self.display_output(json.dumps(docs_data), json_format=True)
            else:
                output_json = json.loads(output)
                if args.id:
                    self.display_output(output, json_format=False)
                else:
                    docs_data = output_json.get("data", output_json)
                    if not docs_data:
                        print("No Datasphere Documents found\n")
                    else:
                        self.display_output(json.dumps({"data": docs_data}), json_format=False)
        else:
            print(f"Error: {output}")

    def create_document(self, args):
        """Create a new Datasphere Document"""

        if not args.name:
            print("Error: name is required for create\n")
            return

        name = ' '.join(args.name)
        payload = {"name": name}

        if args.description:
            payload["description"] = ' '.join(args.description)

        if args.url:
            payload["url"] = args.url

        if args.text:
            payload["text"] = ' '.join(args.text)

        output, status_code = self._datasphere_func("", req_type="POST", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code, compatibility_mode=False)

        if valid:
            output_json = json.loads(output)
            doc_id = output_json.get("id", "unknown")
            doc_name = output_json.get("name", name)
            print(f"Success! Datasphere Document '{doc_name}' created with ID: {doc_id}\n")

    def search_documents(self, args):
        """Search Datasphere Documents"""

        if not args.query:
            print("Error: query is required for search\n")
            return

        query_string = ' '.join(args.query)
        payload = {"query_string": query_string}

        if args.document_id:
            payload["document_id"] = args.document_id

        if args.count:
            payload["count"] = args.count

        if args.tags:
            payload["tags"] = args.tags

        if args.distance:
            payload["distance"] = args.distance

        output, status_code = self._datasphere_func("/search", req_type="POST", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code, compatibility_mode=False)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                output_json = json.loads(output)
                results = output_json.get("data", output_json.get("results", output_json))
                if not results:
                    print("No search results found\n")
                else:
                    self.display_output(json.dumps({"data": results}), json_format=False)
        else:
            print(f"Error: {output}")

    def update_document(self, args):
        """Update a Datasphere Document"""

        if not args.id:
            print("Document ID is required to update\n")
            return

        payload = {}

        if args.name:
            payload["name"] = ' '.join(args.name)

        if args.description:
            payload["description"] = ' '.join(args.description)

        if not payload:
            print("No update parameters provided\n")
            return

        query_params = f"/{args.id}"
        output, status_code = self._datasphere_func(query_params, req_type="PATCH", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code, compatibility_mode=False)

        if valid:
            output_json = json.loads(output)
            doc_name = output_json.get("name", "Document")
            print(f"Complete. Datasphere Document '{doc_name}' (ID: {args.id}) has been updated.\n")

    def delete_document(self, args):
        """Delete a Datasphere Document"""

        if not args.id:
            print("Document ID is required to delete\n")
            return

        if self.confirm_deletion("Datasphere Document", args.id, args.force):
            query_params = f"/{args.id}"
            output, status_code = self._datasphere_func(query_params, req_type="DELETE")

            if status_code == 204:
                print(f"Success! Datasphere Document {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=False)
                if not valid:
                    print(f"Error deleting document: {output}")
        else:
            print("Delete operation cancelled\n")

    # Chunks operations
    def list_chunks(self, args):
        """List chunks for a Datasphere Document"""

        if not args.document_id:
            print("Document ID is required to list chunks\n")
            return

        query_params = f"/{args.document_id}/chunks"
        output, status_code = self._datasphere_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=False)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                output_json = json.loads(output)
                chunks_data = output_json.get("data", output_json)
                if not chunks_data:
                    print("No chunks found for this document\n")
                else:
                    self.display_output(json.dumps({"data": chunks_data}), json_format=False)
        else:
            print(f"Error: {output}")

    def get_chunk(self, args):
        """Get a specific chunk"""

        if not args.document_id:
            print("Document ID is required\n")
            return

        if not args.chunk_id:
            print("Chunk ID is required\n")
            return

        query_params = f"/{args.document_id}/chunks/{args.chunk_id}"
        output, status_code = self._datasphere_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code, compatibility_mode=False)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                self.display_output(output, json_format=False)
        else:
            print(f"Error: {output}")

    def delete_chunk(self, args):
        """Delete a specific chunk"""

        if not args.document_id:
            print("Document ID is required\n")
            return

        if not args.chunk_id:
            print("Chunk ID is required to delete\n")
            return

        if self.confirm_deletion("Chunk", args.chunk_id, args.force):
            query_params = f"/{args.document_id}/chunks/{args.chunk_id}"
            output, status_code = self._datasphere_func(query_params, req_type="DELETE")

            if status_code == 204:
                print(f"Success! Chunk {args.chunk_id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code, compatibility_mode=False)
                if not valid:
                    print(f"Error deleting chunk: {output}")
        else:
            print("Delete operation cancelled\n")

    def _datasphere_func(self, query_params="", req_type="GET", payload=""):
        """Construct API destination and make request"""
        destination = f"{api_destination}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)
