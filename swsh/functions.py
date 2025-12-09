#!/usr/bin/env python3
import base64
import requests
import os
import json
from dotenv import load_dotenv

####

env_var_dict = {}

########################################
############# ENVIRONMENT ##############
########################################
def get_environment():
    """
    Get SignalWire credentials from .env file or environment variables.

    Checks in order:
    1. .env file in current working directory
    2. .env file in ~/.swsh/ directory
    3. System environment variables
    """
    # Try to load .env from current directory first
    if os.path.exists('.env'):
        load_dotenv('.env')
    # Then try ~/.swsh/.env
    elif os.path.exists(os.path.expanduser('~/.swsh/.env')):
        load_dotenv(os.path.expanduser('~/.swsh/.env'))

    # Now get values (dotenv loads into os.environ, so os.getenv works for both)
    signalwire_space = os.getenv('SIGNALWIRE_SPACE')
    project_id = os.getenv('PROJECT_ID')
    rest_api_token = os.getenv('REST_API_TOKEN')
    return (signalwire_space, project_id, rest_api_token)

########################################
########## SHELL ENVIRONMENT ###########
########################################
def set_shell_env(var):
    global env_var_dict
    env_var_split = var.split("=")
    key = env_var_split[0]
    val = env_var_split[1]

    env_var_dict[key] = val

def get_shell_env(var):
    key = var
    if key:
        val = env_var_dict[key]
        if val:
            return (env_var_dict[key])
        else:
            print ("")
    else:
        print("")

def get_shell_env_all():
    if len(env_var_dict.items()) == 0:
        return
    else:
        for k, v in env_var_dict.items():
            print(k + "=" + v)
        print("")

def is_env_var(args):
    for arg in vars(args):
        arg_value = getattr(args, arg)

        # NOTE:  Lists need to be treated differently than strings
        # This affects commands were nargs=+
        # This does currently only account for the first entry in a list, but the env only supports 1=1 in this iteration.
        # Eventually this should change to allow vars to equal any number of strings inside quotes.
        if type(arg_value) == list:
            val = arg_value[0]
            v = str(val)
            if v and v.startswith("$"):
                v = v.strip("$")
                new_arg = [ get_shell_env(v) ]
                setattr(args, arg, new_arg)
        else:
            arg_value = str(arg_value)
            if arg_value and arg_value.startswith("$"):
                val = arg_value.strip("$")
                new_arg = get_shell_env(val)
                setattr(args, arg, new_arg)

    return (args)

########################################
############# UTILITIES ################
########################################
def json_nice_print(j):
    if len(j) == 0:
        print("No Results Found!")
    else:
        json_formatted_response = json.dumps(j, indent=4)
        print(json_formatted_response)

def encode_auth(project_id, rest_api_token):
    auth = str(project_id + ":" + rest_api_token)
    auth_bytes = auth.encode('ascii')
    base64_auth_bytes = base64.b64encode(auth_bytes)
    base64_auth = base64_auth_bytes.decode('ascii')

    return base64_auth

########################################
############ VALIDATION ################
########################################
def validate_http(status_code):
    """Validate an API response status code"""
    if status_code == 200 or status_code == 201 or status_code == 204:
        return True
    else:
        return False

def validate_json(output):
    """Validate whether or not a string is valid JSON"""
    try:
        json.loads(output)
        return True
    except ValueError:
        return False

def print_error_json(error_json):
    """Print error from REST API response - handles multiple formats"""
    print(error_json)
    try:
        error_data = json.loads(error_json)

        # Format 1: REST API - {"errors": [{"detail": "...", "code": "..."}]}
        if "errors" in error_data and isinstance(error_data["errors"], list):
            detail = str(error_data["errors"][0].get("detail", "Unknown error"))
            code = str(error_data["errors"][0].get("code", "Unknown"))
            print(f"API ERROR -- {code}: {detail}\n")

        # Format 2: Fabric API - {"status": 404, "error": "Not Found"}
        elif "status" in error_data and "error" in error_data:
            status = str(error_data["status"])
            error = str(error_data["error"])
            print(f"API ERROR -- {status}: {error}\n")

        # Format 3: Simple message
        elif "message" in error_data:
            message = str(error_data["message"])
            status = str(error_data.get("status", "Error"))
            print(f"API ERROR -- {status}: {message}\n")

        else:
            print("API ERROR -- Unknown error format\n")

    except json.JSONDecodeError:
        print(f"API ERROR -- Could not parse response: {error_json}\n")

def print_error_json_compatibility(error_json):
    """Print error from Compatibility API response"""
    # EXAMPLE: {'code': 20404, 'message': 'The requested resource was not found.', 'more_info': 'https://developer.signalwire.com/compatibility-api/reference/error-codes', 'status': 404}
    error_json = json.loads(error_json)
    message = str(error_json["message"])
    status = str(error_json["status"])

    print("API ERROR -- " + status + ": " + message + "\n")

########################################
############ HTTP REQUEST ##############
########################################
def http_request(destination, req_type, payload={}):
    """
    Make HTTP request to SignalWire API.

    Automatically handles:
    - Authentication via environment variables
    - Content-Type detection (JSON vs form-encoded)
    - Request method routing
    """
    signalwire_space, project_id, rest_api_token = get_environment()
    if not signalwire_space or not project_id or not rest_api_token:
        return (f"Error: SignalWire Space, Project ID, and REST API Token must be set in the environment variables", 400)

    url = f'https://{signalwire_space}.signalwire.com/{destination}'
    http_basic_auth = str(encode_auth(project_id, rest_api_token))

    # Handle different payload types first to determine content-type
    is_form_encoded = False
    if payload:
        if isinstance(payload, str):
            # Try to detect if it's JSON or form-encoded data
            try:
                # If it parses as JSON, treat it as JSON
                payload = json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                # If it doesn't parse as JSON, treat it as form-encoded data (keep as string)
                is_form_encoded = True

    # Determine the type of headers to send based on Request Type and payload format
    if req_type in ["POST", "PUT", "PATCH", "DELETE"]:
        if is_form_encoded:
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'Authorization': 'Basic %s' % http_basic_auth
            }
        else:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': 'Basic %s' % http_basic_auth
            }
    else:
        headers = {
            'Accept': 'application/json',
            'Authorization': 'Basic %s' % http_basic_auth
        }

    # Use appropriate request parameter based on payload type
    if payload and isinstance(payload, dict):
        response = requests.request(req_type, url=url, headers=headers, json=payload)
    else:
        response = requests.request(req_type, url=url, headers=headers, data=payload)

    return (response)
