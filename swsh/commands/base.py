#!/usr/bin/env python3
import cmd2
import json
import re

# Syntax Highlighting
from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import Terminal256Formatter
import urllib.parse
from functions import *


class BaseCommand:
    """
    Base class for all SWSH commands with common functionality
    """
    
    def __init__(self, shell_instance):
        self.shell = shell_instance
    
    def is_env_var(self, args):
        """Replace environment variables in arguments - wrapper for existing function"""
        return is_env_var(args)
    
    def validate_http_response(self, status_code):
        """Validate HTTP response status code"""
        return validate_http(status_code)
    
    def validate_json_response(self, output):
        """Validate if output is valid JSON"""
        return validate_json(output)
    
    def print_json_response(self, data):
        """Print formatted JSON response"""
        json_nice_print(data)
    
    def print_error_json(self, output):
        """Print formatted JSON error response"""
        print_error_json(output)
    
    def print_error_json_compatibility(self, output):
        """Print formatted JSON error response for compatibility API"""
        print_error_json_compatibility(output)
    
    def handle_standard_response(self, output, status_code, compatibility_mode=False):
        """Standard response handling pattern used across commands"""
        valid = self.validate_http_response(status_code)
        if not valid:
            is_json = self.validate_json_response(output)
            if is_json:
                if compatibility_mode:
                    self.print_error_json_compatibility(output)
                else:
                    self.print_error_json(output)
            else:
                print(f"{status_code}: {output}\n")
        return valid
    
    def filter_none_dict(self, data_dict):
        """Filter out None values from dictionary - common pattern in create/update commands"""
        filtered_dict = {}
        for key, value in data_dict.items():
            if value is not None:
                filtered_dict[key] = value
        return filtered_dict
    
    def confirm_deletion(self, resource_type, resource_id, force=False):
        """Standard deletion confirmation pattern"""
        if not force:
            confirm = input(f"Remove {resource_type} {resource_id}? This cannot be undone! (y/n): ")
        else:
            confirm = 'y'
        return confirm.lower() in ['yes', 'y']
    
    def build_query_params_with_filters(self, **filters):
        """Build query parameters string from filters, handling URL encoding"""
        if not any(filters.values()):
            return ""
        
        params = []
        for key, value in filters.items():
            if value is not None:
                if isinstance(value, list):
                    value = ' '.join(value)
                encoded_value = urllib.parse.quote(str(value))
                params.append(f"{key}={encoded_value}")
        
        return "?" + "&".join(params)
    
    def handle_list_by_id_or_filters(self, func, args, id_field='id', json_data_key=None):
        """Common pattern for list commands that can filter by ID or other fields"""
        if hasattr(args, id_field) and getattr(args, id_field):
            # List by ID
            sid = getattr(args, id_field)
            query_params = f"/{sid}"
            output, status_code = func(query_params)
            valid = self.handle_standard_response(output, status_code)
            if valid:
                output_json = json.loads(output)
                if hasattr(args, 'json') and args.json:
                    self.print_json_response(output_json)
                else:
                    return output_json
        else:
            # List all or with filters
            output, status_code = func()
            valid = self.handle_standard_response(output, status_code)
            if valid:
                output_json = json.loads(output)
                data = output_json.get(json_data_key, output_json) if json_data_key else output_json
                if hasattr(args, 'json') and args.json:
                    self.print_json_response(data)
                else:
                    return data
        return None

    def colorize_json(self, json_str):
        """Add syntax highlighting to JSON string"""
        return highlight(json_str, JsonLexer(), Terminal256Formatter(style='solarized-light'))

    def print_formatted_output(self, json_output, indent=2):
        # Capitalize common abbreviations from the API
        capitalize_abbreviations = ['url', 'id', 'ip', 'uri', 'url', 'ai']

        def capitalize_special_keys(key):
            return key.upper() if key.lower() in capitalize_abbreviations else key.capitalize()

        max_key_length = max(len('_'.join(capitalize_special_keys(k) for k in key.split('_'))) for key in json_output.keys())

        for key, value in json_output.items():
            formatted_key = ' '.join(capitalize_special_keys(k) for k in key.split('_'))

            # Handle Subresource Uris as a special case for better formatting
            if key.lower() == 'subresource_uris' and isinstance(value, dict):
                print(f"{' ' * indent}{formatted_key:{max_key_length}} :")
                # Filter out None values and format each URI nicely
                available_uris = {k: v for k, v in value.items() if v is not None}
                if available_uris:
                    for uri_key, uri_value in available_uris.items():
                        uri_formatted_key = ' '.join(capitalize_special_keys(k) for k in uri_key.split('_'))
                        print(f"{' ' * (indent + 2)}{uri_formatted_key:<25} : {uri_value}")
                else:
                    print(f"{' ' * (indent + 2)}No available subresources")
            # Handle lists differently, so they print nice
            elif isinstance(value, list):
                formatted_value = ', '.join(map(str, value))
                print(f"{' ' * indent}{formatted_key:{max_key_length}} : {formatted_value}")
            else:
                formatted_value = str(value)
                print(f"{' ' * indent}{formatted_key:{max_key_length}} : {formatted_value}")

        print ("")

    def format_output(self, output):
        """Format and display output in a structured way"""
        try:
            if isinstance(output, str):
                output = json.loads(output)
            if isinstance(output, dict) and 'data' in output:
                items = output['data']
            elif 'number' in output:
                # Handle phone number show output
                items = output['number'].split() if isinstance(output['number'], str) else output['number']
            else:
                items = [output]
            if not items:
                error_message = 'No data found'
                return (error_message, 404)
            
            # Use visual separators instead of numbered lists for better readability
            for k, v in enumerate(items):
                if isinstance(v, dict):
                    # Use a clean separator line with intelligent title detection
                    separator_line = "─" * 80
                    title_info = self._get_resource_title_info(v)

                    if title_info and len(items) > 1:
                        print(f"\n{separator_line}")
                        print(f"{title_info}")
                        print(f"{separator_line}")
                    elif len(items) > 1:
                        # Just show separator without title for multiple items
                        print(f"\n{separator_line}")

                    self.print_formatted_output(v)
                elif isinstance(v, str):
                    if len(items) > 1:
                        print(f"\n• {v}")
                    else:
                        print(v)
                else:
                    print(f"ERROR: Unexpected data format")
        except json.JSONDecodeError:
            print('ERROR: Invalid JSON data')

    def display_output(self, output, json_format=False):
        """
        Reusable method to display command output in either JSON or formatted view

        Args:
            output: API response string or dict
            json_format: Boolean to determine if output should be in JSON format
        """
        if not output:
            print("No data available")
            return

        try:
            # Parse output if it's a string
            if isinstance(output, str):
                json_data = json.loads(output)
            else:
                json_data = output

            if json_format:
                # Handle JSON output format
                data = json_data.get('data') if isinstance(json_data, dict) else json_data

                if data is not None:
                    if data:
                        print(self.colorize_json(json.dumps(data, indent=2)))
                    else:
                        print("No data found")
                else:
                    print(self.colorize_json(json.dumps(json_data, indent=2)))
            else:
                # Handle formatted output
                self.format_output(output)

        except json.JSONDecodeError:
            print("Error: Invalid JSON")
        except Exception as e:
            print(f"ERROR: {str(e)}")

    def validate_e164_format(self, phone_number, country_code="+1"):
        """
        Validate phone number format (E.164)

        Args:
            phone_number: Phone number string to validate
            country_code: Expected country code (default: "+1" for US/Canada)

        Returns:
            bool: True if valid E.164 format, False otherwise
        """
        if country_code == "+1":
            # US/Canada: +1 followed by 10 digits
            pattern = r'^\+1\d{10}$'
        else:
            # Generic E.164: + followed by country code and up to 15 total digits
            pattern = r'^\+\d{1,15}$'

        phone_regex = re.compile(pattern)
        return bool(phone_regex.search(phone_number))

    def validate_e164_or_error(self, phone_number, country_code="+1"):
        """
        Validate E.164 format and print error if invalid

        Args:
            phone_number: Phone number string to validate
            country_code: Expected country code (default: "+1" for US/Canada)

        Returns:
            bool: True if valid, False if invalid (error already printed)
        """
        if not self.validate_e164_format(phone_number, country_code):
            if country_code == "+1":
                print(f'ERROR: "{phone_number}" is not in valid E.164 format (expected: +1XXXXXXXXXX)\n')
            else:
                print(f'ERROR: "{phone_number}" is not in valid E.164 format\n')
            return False
        return True

    def _get_resource_title_info(self, resource_data):
        """
        Intelligently detect and format resource title information

        Args:
            resource_data: Dictionary containing resource information

        Returns:
            str: Formatted title string or None if no suitable title found
        """
        if not isinstance(resource_data, dict):
            return None

        # Priority-ordered list of potential title fields with their resource type mappings
        title_mapping = [
            # Projects/Accounts
            ('friendly_name', 'Project'),
            # SIP Endpoints, Number Groups, etc.
            ('name', 'SIP Endpoint'),
            ('username', 'SIP Endpoint'),
            # Phone Numbers
            ('number', 'Phone Number'),
            # Domain Applications
            ('domain_name', 'Domain Application'),
            # Applications
            ('application_name', 'Application'),
            # Queues
            ('queue_name', 'Queue'),
            # Generic fallbacks
            ('label', 'Resource'),
            ('title', 'Resource'),
            ('identifier', 'Resource'),
        ]

        # Auto-detect resource type based on available fields
        resource_type = self._detect_resource_type(resource_data)

        # Try to find the best title field
        for field_name, default_type in title_mapping:
            if field_name in resource_data and resource_data[field_name]:
                value = resource_data[field_name]
                # Use detected resource type or fallback to mapping
                type_name = resource_type if resource_type else default_type
                return f"{type_name}: {value}"

        # If no title field found but we detected a resource type, use generic title
        if resource_type:
            return f"{resource_type}"

        return None

    def _detect_resource_type(self, resource_data):
        """
        Detect resource type based on field patterns

        Args:
            resource_data: Dictionary containing resource information

        Returns:
            str: Detected resource type or None
        """
        # Define field patterns that indicate specific resource types
        type_patterns = {
            'Project': ['friendly_name', 'subproject', 'owner_account_sid'],
            'SIP Endpoint': ['username', 'sip_profile_id', 'endpoint_id'],
            'Phone Number': ['number', 'call_handler', 'message_handler'],
            'Number Group': ['name', 'numbers', 'group_id'],
            'Domain Application': ['domain_name', 'call_handler', 'message_handler'],
            'LAML Bin': ['friendly_name', 'laml_bin_sid'],
            'Queue': ['queue_name', 'max_size', 'current_size'],
            'SIP Profile': ['name', 'profile_id'],
        }

        # Check which resource type has the most matching fields
        best_match = None
        max_matches = 0

        for resource_type, required_fields in type_patterns.items():
            matches = sum(1 for field in required_fields if field in resource_data)
            if matches > max_matches and matches > 0:
                max_matches = matches
                best_match = resource_type

        return best_match


