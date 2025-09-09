#!/usr/bin/env python3
import cmd2
import json

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

            # Handle lists differently, so they print nice
            if isinstance(value, list):
                formatted_value = ', '.join(map(str, value))
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
            
            for k, v in enumerate(items, start=1):
                if isinstance(v, dict):
                    if 'number' in v:
                        print(f"{v.get('number', 'No Number Available!')}")
                    else:
                        print(f"{k})")
                        self.print_formatted_output(v)
                elif isinstance(v, str):
                    print(f"{k}) {v}")
                else:
                    print(f"{k}) ERROR: Unexpected data format")
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


