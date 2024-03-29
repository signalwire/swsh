#!/usr/bin/env python3
import cmd2
import os
import argparse
from swsh.functions import *
from swsh.buy_a_phone_number import *
import json
import time
import re
import urllib.parse
from signalwire.rest import Client as signalwire_client


###########################################################################
class MyPrompt(cmd2.Cmd):

    global noninteractive_flag
    global swish_version
    global EDITOR

    noninteractive_flag = 0
    swish_version = "1.0"
    EDITOR = os.environ.get('EDITOR', 'pyvim')

    # Verify the OS env is set.  Ask for input if not.
    # TODO/NOTE: This does not export the vars for future use.  This may be something to push into a .swsh file at some point
    # TODO/NOTE pt 2: we can add switches like --signalwire-space <spacename> to this as well
    signalwire_space, project_id, rest_api_token = get_environment()
    if signalwire_space == "" or signalwire_space is None or project_id == "" or project_id is None or rest_api_token == "" or rest_api_token is None:
        if len(sys.argv) > 1:
            sys.exit("""ERROR:  ENV vars not set!\n
Run the following commands at the terminal to add to system env for non-interactive mode:
Windows:
  setx SIGNALWIRE_SPACE=<space_name>
  setx PROJECT_ID=<project_id>
  setx REST_API_TOKEN=<api_token>"

Linux / MacOS
  export SIGNALWIRE_SPACE=<space_name>
  export PROJECT_ID=<project_id>
  export REST_API_TOKEN=<api_token>"       
""")
        print("""No environment detected!\n  
Run the following commands at the terminal to add env vars to speed up start time:
Windows:
  setx SIGNALWIRE_SPACE=<space_name>
  setx PROJECT_ID=<project_id>
  setx REST_API_TOKEN=<api_token>"

Linux / MacOS
  export SIGNALWIRE_SPACE=<space_name>
  export PROJECT_ID=<project_id>
  export REST_API_TOKEN=<api_token>\n\n
""")
        if signalwire_space == "" or signalwire_space is None:
            signalwire_space = input ("\nEnter Signalwire Space: ")
        if project_id == "" or project_id is None:
            project_id = input ("Enter Project ID: ")
        if rest_api_token == "" or rest_api_token is None:
            rest_api_token = input ("Enter Rest API Token: ")
        
        # validate what was entered and then put them into the environment
        valid_creds = validate_signalwire_creds(signalwire_space, project_id, rest_api_token)
        if valid_creds:
            os.environ['SIGNALWIRE_SPACE'] = signalwire_space
            os.environ['PROJECT_ID'] = project_id
            os.environ['REST_API_TOKEN'] = rest_api_token
        else:
            print ("ERROR: This are not valid SignalWire API Credentials\n")

    if len(sys.argv) > 1:
        # Sets up non-interactive mode
        # when passing arguments into cmd2, it requires 'quit' as the last command to exit
        # Appending quit here to make it more user friendly

        # Looking for sys.argv also allows us to expand to pass in additional switches at a later time
        # Commenting out code to require -x for non-interactive per GH swish #1.  Leaving in case we decide to use it at a later time, or ever add other switches
        # if sys.argv[1] == '-x':
        if sys.argv[1]:
            # sys.argv.remove('-x')   # Remove the -x switch
            # Group all arguments as a single command, otherwise all arguments are processes as separate commands.  Delete every element in the list after 1.
            sys.argv[1] = ' '.join(sys.argv[1::])
            del sys.argv[2:]
            sys.argv.append('quit')   # Append the required 'quit' at the end
            noninteractive_flag = 1

            if sys.argv[1] == '-v' or sys.argv[1] == '--version':
                print ("Version: " + swish_version)
                sys.exit()
            elif sys.argv[1] == '-h' or sys.argv[1] == '--help':
                print ('''SWiSH Help Menu:
================
SignalWire interactive SHell
Cross platform command line utility and shell for administering a Space or Spaces in Signalwire

-h | --help       view this help menu
-v | --version    SWiSH version
''')
                sys.exit()

    else:
        def __init__(self):
            super().__init__(
            completekey='tab',
            persistent_history_file='~/.swsh_history'
            )

            self.hidden_commands.append('macro')
            self.hidden_commands.append('alias')
            self.hidden_commands.append('set')
            self.hidden_commands.append('exit')

            del cmd2.Cmd.do_shell
            del cmd2.Cmd.do_shortcuts
            del cmd2.Cmd.do_run_script
            del cmd2.Cmd.do_run_pyscript
            del cmd2.Cmd.do_edit    # this may be something to add back in later to allow users to edit files.
            #del cmd2.Cmd.do_set    # Eventually I'd like to remove this, but for now leaving on, because it can toggle debug mode on.
            del cmd2.Cmd.do_ipy
            del cmd2.Cmd.do_py

        prompt = 'swsh> '
        intro = '''
##################################################################
#                                                                #
#         _______.____    __    ____   _______. __    __         #
#        /       |\   \  /  \  /   /  /       ||  |  |  |        #
#       |   (----` \   \/    \/   /  |   (----`|  |__|  |        #
#        \   \      \            /    \   \    |   __   |        #
#    .----)   |      \    /\    / .----)   |   |  |  |  |        #
#    |_______/        \__/  \__/  |_______/    |__|  |__|        #
#                                                                #
#                                                                #
#      Welcome to swsh: The SignalWire interactive Shell         #
##################################################################
'''

    def default(self, line):
        # Am I setting a Shell var?
        if "=" in line.command:

            set_shell_env(line.command)
            return

    def do_exit(self, inp):
        # Thank user on exit, unless noninteractive_flag is true
        if noninteractive_flag == 1:
            return True
        else:
            print("Thanks for using SignalWire")
            return True

    def help_exit(self):
        print('exit the application. Shorthand: Ctrl-D.')

    do_quit = do_exit
    help_quit = help_exit

    def do_clear(self, inp):
        '''Clear the Screen'''
        os.system("clear")

    def do_echo(self, inp):
        '''echo something'''
        inp = inp.split()
        if inp[0].startswith("$"):
            key = inp[0].strip("$")
            shell_var = get_shell_env(key)
            print (shell_var)
        else:
            print (' '.join(inp))
    
    def do_env(self, args):
        '''Return the SWiSH Environment Variables'''
        get_shell_env_all()

## SIP ENDPOINT COMMAND ##
    # Create the top level parser for sip endpoints: sip_endpoint
    base_sip_endpoint_parser = cmd2.Cmd2ArgumentParser()
    base_sip_endpoint_subparsers = base_sip_endpoint_parser.add_subparsers(title='SIP ENDPOINT',help='sip_endpoint help')

    # create the sip_endpoint list subcommand
    sip_endpoint_parser_list = base_sip_endpoint_subparsers.add_parser('list', help='List SIP Endpoints')
    sip_endpoint_parser_list.add_argument('-i', '--id', help='List SIP Endpoint by unique SignalWire ID')
    sip_endpoint_parser_list.add_argument('-j', '--json', action='store_true', help='Output SIP Endpoint(s) in JSON format')
    sip_endpoint_parser_list.add_argument('-n', '--name', type=str, nargs='+', help='Search for SIP Endpoint by username')

    # create the sip_endpoint update subcommand
    sip_endpoint_parser_update = base_sip_endpoint_subparsers.add_parser('update', help='Update a SIP Endpoint')
    sip_endpoint_parser_update.add_argument('-u', '--username', help='update username of the sip endpoint')
    sip_endpoint_parser_update.add_argument('-p', '--password', help='update password of the sip endpoint')
    sip_endpoint_parser_update.add_argument('-s', '--send-as',  help='default caller id for sip endpoint (Must belong to the Project!)')
    sip_endpoint_parser_update.add_argument('-c', '--caller-id', nargs='+', help='Friendly Caller ID Name (SIP to SIP only)' )
    sip_endpoint_parser_update.add_argument('-i', '--id', help='Unique id of the SIP Endpoint to be updated')
    sip_endpoint_parser_update.add_argument('-e', '--encryption', type=str, help='Default Codecs', choices=['default', 'required', 'optional'])
    sip_endpoint_parser_update.add_argument('--codecs', type=str, nargs='+', help='Default Codecs', choices=['OPUS', 'G722', 'PCMU', 'PCMA', 'VP8', 'H264'])
    sip_endpoint_parser_update.add_argument('--ciphers', type=str, nargs='+',  help='Default Ciphers', choices=['AEAD_AES_256_GCM_8','AES_256_CM_HMAC_SHA1_80','AES_CM_128_HMAC_SHA1_80','AES_256_CM_HMAC_SHA1_32','AES_CM_128_HMAC_SHA1_32'])

    # create the sip_endpoint create subcommand
    sip_endpoint_parser_create = base_sip_endpoint_subparsers.add_parser('create', help='Create a SIP Endpoint')
    sip_endpoint_parser_create.add_argument('-u', '--username', help='username of the sip endpoint', required=True)
    sip_endpoint_parser_create.add_argument('-p', '--password', help='password of the sip endpoint', required=True)
    sip_endpoint_parser_create.add_argument('-s', '--send-as',  help='default caller id for sip endpoint (Must belong to the Project!)', required=True )
    sip_endpoint_parser_create.add_argument('-n', '--caller-id', nargs='+', help='Friendly Caller ID Name (SIP to SIP only)', required=True )
    sip_endpoint_parser_create.add_argument('-e', '--encryption', type=str, help='Default Codecs', choices=['default', 'required', 'optional'])
    sip_endpoint_parser_create.add_argument('--codecs', type=str, nargs='+', help='Default Codecs', choices=['OPUS', 'G722', 'PCMU', 'PCMA', 'VP8', 'H264'])
    sip_endpoint_parser_create.add_argument('--ciphers', type=str, nargs='+',  help='Default Ciphers', choices=['AEAD_AES_256_GCM_8','AES_256_CM_HMAC_SHA1_80','AES_CM_128_HMAC_SHA1_80','AES_256_CM_HMAC_SHA1_32','AES_CM_128_HMAC_SHA1_32'])

    # create the sip_endpoint delete subcommand
    sip_endpoint_parser_delete = base_sip_endpoint_subparsers.add_parser('delete', help='Delete a SIP Endpoint')
    # API takes the ID, Would be nice to do this by looking up by friendly name and return the ID,
    # but that may return multiple results.  Would need to write some guardrails around that.
    # For now just leaving with having provide the SID.
    sip_endpoint_parser_delete.add_argument('-i', '--id', help='Unique id of the SIP Endpoint', required=True)
    sip_endpoint_parser_delete.add_argument('-f', '--force', action='store_true', help='Force removal.  Will not ask to confirm delete of SIP Endpoint')

    ## subcommand functions for sip_endpoint
    def sip_endpoint_list(self, args):
        '''list subcommand of sip_endpoint'''
        args = is_env_var(args)  # Replace any env vars in the command string

        query_params = ""
        if args.id:
            sid = args.id
            query_params="/" + sid
        elif args.name:
            query_params = "?"
            if args.name:
                name = ' '.join(args.name)
                name = urllib.parse.quote(name)
                query_params = query_params + "filter_username=%s&" % name

        output, status_code =  sip_endpoint_func(query_params)
        valid = validate_http(status_code)
        if valid:
            # Format the output depending on user args
            output = json.loads(output)
            if args.id and args.json:
                json_nice_print(output)

            elif args.id:
                k_val = str("1")

                for k, v in output.items():
                    key = k.upper()
                    if isinstance(v, list):
                        value = str(', '.join(v))
                    else:
                        value = str(v)

                    #set_shell_env(key + "=" + value)

                print(k_val + ")")
                print("  SignalWire ID:\t" + str(output["id"]))
                print("  Username:\t\t" + str(output["username"]))
                print("  Caller Name:\t\t" + str(output["caller_id"]))
                print("  Caller Number:\t" + str(output["send_as"]))
                print("  Codecs:\t\t" + str(', '.join((list(filter(None, output["codecs"]))))))
                print("  Encryption Ciphers:\t" +str(', '.join((list(filter(None, output["ciphers"]))))))
                print("  Encrytion Enabled:\t" + str(output["encryption"]))
                print("")

            elif args.json:
                json_nice_print(output["data"])

            else:
                for k, v in enumerate(output["data"]):
                    k_num = str(k + 1)

                    print(k_num + ")")
                    print(" SignalWire ID:\t\t" + str(output["data"][k]["id"]))
                    print(" Username:\t\t" + str(output["data"][k]["username"]))
                    print(" Caller ID Name:\t" + str(output["data"][k]["caller_id"]))
                    print(" Caller ID Number:\t" + str(output["data"][k]["send_as"]))
                    print(" Codecs:\t\t" + str(', '.join((list(filter(None, output["data"][k]["codecs"]))))))
                    print(" Encryption Ciphers:\t" + str(', '.join((list(filter(None, output["data"][k]["ciphers"]))))))
                    print(" Encrytion Enabled:\t" + str(output["data"][k]["encryption"]))
                    print("")
   
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print ("Error: " + output + "\n")

    def sip_endpoint_create(self, args):
        '''create subcommand of sip_endpoint'''
        args = is_env_var(args)  # Replace any env vars in the command string

        query_params = ""
        sip_endpoint_dictionary = {
          "username": args.username,
          "password": args.password,
          "caller_id": ' '.join(args.caller_id),
          "send_as": args.send_as,
          "codecs": args.codecs,
          "ciphers": args.ciphers,
          "encryption": args.encryption
        }

        create_sip_endpoint_dictionary = {}
        for x, y in sip_endpoint_dictionary.items():
            if y is not None:
              create_sip_endpoint_dictionary[x] = y

        payload = json.dumps( create_sip_endpoint_dictionary )
        output, status_code = sip_endpoint_func(query_params, "POST",  payload=payload)
        valid = validate_http(status_code)
        if valid:
            # Grab the New ID and print for the user
            output_json = json.loads(output)
            endpoint_id = output_json["id"]
            print("SIP Endpoint created with ID: " + endpoint_id + "\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print (status_code + ": " + output + "\n" )

    def sip_endpoint_update(self, args):
        '''update subcommand of sip_endpoint'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/" + sid
        if args.caller_id:
            # Can only join multiple words if part of the update.  Fix that here. I guess.
            args.caller_id = ' '.join(args.caller_id)
        sip_endpoint_dictionary = {
          "username": args.username,
          "password": args.password,
          "caller_id": args.caller_id,
          "send_as": args.send_as,
          "codecs": args.codecs,
          "ciphers": args.ciphers,
          "encryption": args.encryption
        }

        update_sip_endpoint_dictionary = {}
        for x, y in sip_endpoint_dictionary.items():
            if y is not None:
              update_sip_endpoint_dictionary[x] = y

        payload = json.dumps ( update_sip_endpoint_dictionary )
        output, status_code = sip_endpoint_func(query_params, "PUT",  payload=payload)
        valid = validate_http(status_code)
        if valid:
            # TODO: Output the sip endpoint after updated.  Maybe?
            print("SIP Endpoint " + sid + " updated.\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print (status_code + ": " + output + "\n" )

    def sip_endpoint_delete(self, args):
        '''delete subcommand of sip_endpoint'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/" + sid
        if sid is not None:
            if not args.force:
                confirm = input("Remove SIP Endpoint " + sid + "? This cannot be undone! (y/n): " )
            else:
                confirm = 'y'

            if confirm.lower() == "yes" or confirm.lower() == "y":
                output, status_code = sip_endpoint_func(query_params, "DELETE")
                valid = validate_http(status_code)
                if valid:
                    print("Success! SIP Endpoint " + sid + " Removed\n")
                else:
                    is_json = validate_json(output)
                    if is_json:
                        print_error_json(output)
                    else:
                        status_code = str(status_code)
                        print ( status_code + ": " + output + "\n" )
            else:
                print ("OK.  Cancelling...\n")
        else:
            print ("ERROR: Please enter a valid SID\n")

    # Set default handlers for each sub command
    sip_endpoint_parser_list.set_defaults(func=sip_endpoint_list)
    sip_endpoint_parser_create.set_defaults(func=sip_endpoint_create)
    sip_endpoint_parser_update.set_defaults(func=sip_endpoint_update)
    sip_endpoint_parser_delete.set_defaults(func=sip_endpoint_delete)

    @cmd2.with_argparser(base_sip_endpoint_parser)
    def do_sip_endpoint(self, args: argparse.Namespace):
        '''List, Update, and Create SIP Endpoint configurations'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('sip_endpoint')


## SIP PROFILE COMMAND ##
    # Create the top level parser for sip profiles: sip_profile
    base_sip_profile_parser = cmd2.Cmd2ArgumentParser()
    base_sip_profile_subparsers = base_sip_profile_parser.add_subparsers(title='SIP PROFILE',help='sip_profile help')

    # create the sip_profile list subcommand
    sip_profile_parser_list = base_sip_profile_subparsers.add_parser('list', help='List SIP Profiles')
    sip_profile_parser_list.add_argument('-j', '--json', action='store_true', help='List SIP Profiles in JSON')

    # create the sip_profile update subcommand
    sip_profile_parser_update = base_sip_profile_subparsers.add_parser('update', help='Update a SIP profile')
    sip_profile_parser_update.add_argument('-d', '--domain-identifier', help='Domain Identifier of the SIP profile')
    sip_profile_parser_update.add_argument('-s', '--send-as',  help='Default sendas for SIP Endpoints ')
    sip_profile_parser_update.add_argument('-e', '--encryption', type=str, help='Set Default encryption option for SIP Profiles', choices=['required', 'optional'])
    sip_profile_parser_update.add_argument('--codecs', type=str, nargs='+', help='Set Default Codecs for SIP Endpoints', choices=['OPUS', 'G722', 'PCMU', 'PCMA', 'VP8', 'H264'])
    sip_profile_parser_update.add_argument('--ciphers', type=str, nargs='+',  help='Set Default Ciphers for SIP Endpoints', choices=['AEAD_AES_256_GCM_8','AES_256_CM_HMAC_SHA1_80','AES_CM_128_HMAC_SHA1_80','AES_256_CM_HMAC_SHA1_32','AES_CM_128_HMAC_SHA1_32'])

    ## subcommand functions for sip_profile
    def sip_profile_list(self, args):
        '''list subcommand of sip_profile'''
        args = is_env_var(args)  # Replace any env vars in the command string

        output, status_code = sip_profile_func()
        valid = validate_http(status_code)
        if valid:
            output =  json.loads(output)
            if args.json:
                json_nice_print(output)
            else:
                k_num = str("1")  # There is only one sip profile.  May make sense someday to make this a loop.

                print(k_num + ")")
                print("  Domain:\t\t\t" + str(output["domain"]))
                print("  Domain Identefier:\t\t" + str(output["domain_identifier"]))
                print("  Default Codecs:\t\t" + str(' '.join(output["default_codecs"])))
                print("  Default Encryption Ciphers:\t" + str(' '.join(output["default_ciphers"])))
                print("  Default Encryption Enabled:\t" + str(output["default_encryption"]))
                print("  Default Caller Number:\t" + str(output["default_send_as"]))
                print("")

        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print (status_code + ": " + output + "\n" )

    def sip_profile_update(self, args):
        '''update subcommand of sip_profile'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sip_profile_dictionary = {
          "domain_identifier": args.domain_identifier,
          "default_send_asas": args.send_as,
          "default_codecs": args.codecs,
          "default_ciphers": args.ciphers,
          "default_encryption": args.encryption
        }

        update_sip_profile_dictionary = {}
        for x, y in sip_profile_dictionary.items():
            if y is not None:
              update_sip_profile_dictionary[x] = y

        payload = json.dumps(update_sip_profile_dictionary)
        output, status_code = sip_profile_func(req_type="PUT", payload=payload)
        valid = validate_http(status_code)
        if valid:
            print("Complete.  The SIP Profile has been updated.\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print (status_code + ": " + output + "\n" )

    # Set default handlers for each sub command
    sip_profile_parser_list.set_defaults(func=sip_profile_list)
    sip_profile_parser_update.set_defaults(func=sip_profile_update)

    @cmd2.with_argparser(base_sip_profile_parser)
    def do_sip_profile(self, args: argparse.Namespace):
        '''List, Update, SIP profile configurations'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('sip_profile')


## PHONE NUMBER COMMAND ##
    # Create the top level parser for phone numbers: phone_number
    base_phone_number_parser = cmd2.Cmd2ArgumentParser()
    base_phone_number_subparsers = base_phone_number_parser.add_subparsers(title='PHONE NUMBER',help='phone_number help')

    # create the phone_number list subcommand
    phone_number_parser_list = base_phone_number_subparsers.add_parser('list', help='List Phone Numbers for a Projects')
    phone_number_parser_list.add_argument('-j', '--json', action='store_true', help='List Phone Numbers for project in JSON Format')
    phone_number_parser_list.add_argument('-n', '--name', nargs='+', help='Find a phone number by object Name')
    phone_number_parser_list.add_argument('-i', '--id', help='Find a phone number by SignalWire ID')
    phone_number_parser_list.add_argument('-N', '--number', help='Return a phone number by number in E164 format')

    # create the phone_number update subcommand
    phone_number_parser_update = base_phone_number_subparsers.add_parser('update', help='Update a Phone Number')
    phone_number_parser_update.add_argument('-i', '--id', help='ID of the SignalWire Phone Number')
    phone_number_parser_update.add_argument('-N', '--number', help='The phone number being updated')
    phone_number_parser_update.add_argument('-n', '--name', nargs='+', help='Update the Friendly Name of a Phone Number')
    phone_number_parser_update.add_argument('--call-handler', help='Type of handlers to use when processing calls to the Number', choices=["relay_context", "laml_webhooks", "laml_application", "dialogflow", "relay_connector", "relay_sip_endpoint", "relay_script", "relay_verto_endpoint", "video_room"])
    phone_number_parser_update.add_argument('--call-receive-mode', help='How to receive the incoming call: Voice or Fax', choices=["voice", "fax"], default="voice")
    phone_number_parser_update.add_argument('--call-request-url', help='URL to make a request when using the laml_webhooks call handler')
    phone_number_parser_update.add_argument('--call-request-method', help='HTTP method type when using laml_webhook call handler', choices=["POST", "GET"], default="POST")
    phone_number_parser_update.add_argument('--call-fallback-url', help='Secondary URL for laml_webhook call handler, in the instance the Primary webhook fails')
    phone_number_parser_update.add_argument('--call-fallback-method', help='HTTP method type when using a fallback laml_webhook message handler', choices=["POST", "GET"], default="POST")
    phone_number_parser_update.add_argument('--call-status-callback-url', help='URL to make status callbacks when using the laml_webhooks call handler')
    phone_number_parser_update.add_argument('--call-status-callback-method', help='HTTP method type when using the call_status_callback_url', choices=["POST", "GET"], default="POST")
    phone_number_parser_update.add_argument('--call-laml-application-id', help='ID of the LaML Webhook Application when using the laml_application call handler')
    phone_number_parser_update.add_argument('--call-dialogflow-id', help='ID of the Dialogflow Agent to start when using the dialogflow call handler')
    phone_number_parser_update.add_argument('--call-relay-context', help='The name of the Relay Context to send this call to when using the relay_context call handler')
    phone_number_parser_update.add_argument('--call-relay-connector-id', help='ID of the Relay Connector to send this call to when using the relay_connector call hanlder')
    phone_number_parser_update.add_argument('--call-relay-script-url', help='URL of the Relay Bin / SWML script')
    phone_number_parser_update.add_argument('--call-sip-endpoint-id', help='ID of the SIP Endpoint to send this call to when using the sip_endpoint call handler')
    phone_number_parser_update.add_argument('--call-verto-resourece', help='The name of the Verto Relay endpoint to send this call to when using the relay_verto_endpoint handler')
    phone_number_parser_update.add_argument('--call-video-room-id', help='The OD of the Video Room to send this call to when using the video_room call handler')
    phone_number_parser_update.add_argument('--message-handler', help='Type of handler to use on inbound text messages', choices=["relay_context", "laml_webhook", "laml_application"])
    phone_number_parser_update.add_argument('--message-request-url', help='URL used to make requests using the laml_webhook message handler')
    phone_number_parser_update.add_argument('--message-request-method', help='HTTP method type when using laml_webhook message handler', choices=["POST", "GET"], default="POST")
    phone_number_parser_update.add_argument('--message-fallback-url', help='Secondary URL for laml_webhook, in the instance the Primary fails')
    phone_number_parser_update.add_argument('--message-fallback-method', help='HTTP method type when using laml_webhook message handler', choices=["POST", "GET"], default="POST")
    phone_number_parser_update.add_argument('--message-laml-application-id', help='The ID of the LamL Application to use when using the laml_application message handler')
    phone_number_parser_update.add_argument('--message-relay-context', help='The name of the relay context to send this message when using the relay_context message handler')

    # create the phone_number release subcommand
    phone_number_parser_release = base_phone_number_subparsers.add_parser('release', help='Release/Remove a Phone Number')
    phone_number_parser_release.add_argument('-i', '--id', help='The SignalWire ID of the number that is being Released (Removed)')
    phone_number_parser_release.add_argument('-n', '--number', help='Number to be Released (Removed)')
    phone_number_parser_release.add_argument('-f', '--force', action='store_true', help='Force release.  Will not ask to confirm release of Phone Number')

    # create the phone_number lookup sub
    phone_number_parser_lookup = base_phone_number_subparsers.add_parser('lookup', help='Lookup a Phone Number (in E.164 format)')
    phone_number_parser_lookup.add_argument('--number', help='Number you want to lookup (in E.164 format)', required=True)
    phone_number_parser_lookup.add_argument('--cnam', action='store_true', help='Include carrier lookup')
    phone_number_parser_lookup.add_argument('--carrier', action='store_true', help='Include carrier lookup')

    # create the phone numbers buy command
    phone_number_parser_buy = base_phone_number_subparsers.add_parser('buy', help='Purchase Phone numbers for the Proect')

    ## subcommand functions for phone numbers
    def phone_number_list(self, args):
        '''list subcommand of phone_number'''
        args = is_env_var(args)  # Replace any env vars in the command string

        if args.json:
            output, status_code = phone_number_func()
            valid = validate_http(status_code)
            if valid:
                output_json = json.loads(output)
                data_json = output_json["data"]
                json_nice_print(data_json)
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json(output)
                else:
                    print (status_code + ": " + output + "\n" )
        elif args.id:
            sid = args.id
            query_params = "/" + sid
            output, status_code = phone_number_func(query_params)
            valid = validate_http(status_code)
            if valid:
                output_json = json.loads(output)
                json_nice_print(output_json)
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json(output)
                else:
                    print (status_code + ": " + output + "\n" )
        elif args.name or args.number:
            query_params = "?"
            if args.name:
                name = ' '.join(args.name)
                name = urllib.parse.quote(name)
                query_params = query_params + "filter_name=%s&" % name
            if args.number:
                number = urllib.parse.quote(args.number)
                query_params = query_params + "filter_number=%s&" % number

            query_params = query_params[:-1] # Removing the final character to clean up dangling &
            output, status_code = phone_number_func(query_params)
            valid = validate_http(status_code)
            if valid:
                output_json = json.loads(output)
                data_json = output_json["data"]
                json_nice_print(data_json)
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json(output)
                else:
                    print (status_code + ": " + output + "\n" )
        else:
            output, status_code = phone_number_func()
            valid = validate_http(status_code)
            if valid:
                json_data = json.loads(output)
                tn_data = json_data["data"]
                for index, value in enumerate(tn_data):
                    # Create a temporary dictionary for each number then only return the number value
                    # NOTE: Someday this could be expanded to return the number and the ID or something like that
                    temp_d = value
                    print (temp_d["number"])
                print ("") # End with a blank line.
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json(output)
                else:
                    print (status_code + ": " + output + "\n" )


    def phone_number_update(self, args):
        '''Update subcommand of phone_number'''
        args = is_env_var(args)  # Replace any env vars in the command string

        # NOTE: I found that if the number DOES NOT have a name, the API won't allow it to be udpated and will require a name.  After that, it is no longer needed.
        # An ID or Number are required.
        if args.id:
            sid = args.id
        elif args.number:
            # Lookup the number in the API and get the SID.
            query_params = "?filter_number=" + urllib.parse.quote(args.number)
            output, status_code = phone_number_func(query_params=query_params)
            valid = validate_http(status_code)
            if not valid:
                print("An error has occured.  Please check number and retry\n")
            else:
                output = json.loads(output)
                sid = (output["data"][0]["id"])
        else:
            print("A valid SignalWire ID or Phone Number is required.\n")

        query_params = "/" + sid
        if args.name:
            # Can only join if argument exists.  Doing that here.
            args.name = ' '.join(args.name)
        phone_number_dictionary = {
          "name": args.name,
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
          "call_verto_resourece": args.call_verto_resourece,
          "call_video_room_id": args.call_video_room_id,
          "message_handler": args.message_handler,
          "message_request_url": args.message_request_url,
          "message_request_method": args.message_request_method,
          "message_fallback_url": args.message_fallback_url,
          "message_fallback_method": args.message_fallback_method,
          "message_laml_application_id": args.message_laml_application_id,
          "message_relay_context": args.message_relay_context
        }

        update_phone_number_dictionary = {}
        for x, y in phone_number_dictionary.items():
            if y is not None:
                update_phone_number_dictionary[x] = y

        payload = json.dumps(update_phone_number_dictionary)
        output, status_code = phone_number_func(query_params, "PUT",  payload=payload)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            phone_number = output_json["number"]
            print(phone_number + " has been updated successfully\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json(output)
                else:
                    print (status_code + ": " + output + "\n" )


    def phone_number_release(self, args):
        '''Release subcommand of phone_number'''
        args = is_env_var(args)  # Replace any env vars in the command string

        if args.id:
            sid = args.id
        elif args.number:
            # Lookup the number in the API and get the SID.
            query_params = "?filter_number=" + urllib.parse.quote(args.number)
            output, status_code = phone_number_func(query_params=query_params)
            valid = validate_http(status_code)
            if not valid:
                print("An error has occured.  Please check number and retry\n")
            else:
                output = json.loads(output)
                sid = (output["data"][0]["id"])
        else:
            print("A valid SignalWire ID or Phone Number is required.\n")

        query_params = "/" + sid
        if not args.force:
            confirm = str(input("Are you sure you want to proceed removing id " + sid + "?  This cannot be undone! (Y/n): " ))
        else:
            confirm = "y"

        # TODO: There are times when the number is too new to be released.
        # It Would be nice to be able to relay that to the user
        if confirm.lower() == "yes" or confirm.lower() == "y":
            output, status_code = phone_number_func(query_params, "DELETE")
            valid = validate_http(status_code)
            if valid:
                # TODO: Pull the number from the API first, that way we have all the data here and can output the number correctly, rather than the SID.
                print("Phone number with SID, " + sid + ", has been successfully Removed\n")
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json(output)
                else:
                    is_json = validate_json(output)
                    if is_json:
                        print_error_json(output)
                    else:
                        print (status_code + ": " + output + "\n" )
        else:
            print("Cancelling...\n")

    def phone_number_lookup(self, args):
        '''lookup subcommand of phone_number'''
        args = is_env_var(args)  # Replace any env vars in the command string

        # TODO: Refactor this command using new(er) functions
        # Verify its a 10 digit US number in e.164 format.
        number = args.number
        phone_num_regex = re.compile(r'^\+1\d{10}$')
        good_num = phone_num_regex.search(number)

        if good_num is not None:
            if args.cnam and args.carrier:
                include = "?include=cnam,carrier"
            elif args.cnam:
                include = "?include=cnam"
            elif args.carrier:
                include = "?include=carrier"
            else:
                include = ""

            query_params = number + include
            phone_number_lookup(query_params=query_params)
        else:
            print('ERROR: That number is not in a valid e.164 format')

    def phone_number_buy(self, args):
        '''buy subcommand of phone_number'''
        # TODO: Make this much more robust.
        # TODO: Add switches to pass in from command line
        # TODO: Buy multiple numbers / bulk numbers
        buy_a_phone_number()

    # Set default handlers for each sub command
    phone_number_parser_list.set_defaults(func=phone_number_list)
    phone_number_parser_update.set_defaults(func=phone_number_update)
    phone_number_parser_release.set_defaults(func=phone_number_release)
    phone_number_parser_lookup.set_defaults(func=phone_number_lookup)
    phone_number_parser_buy.set_defaults(func=phone_number_buy)

    @cmd2.with_argparser(base_phone_number_parser)
    def do_phone_number(self, args: argparse.Namespace):
        '''List, Update, and Buy Phone numbers'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('phone_number')


## LaML BINS ##
    # Create the top level parser for laml bins: laml_bin
    base_laml_bin_parser = cmd2.Cmd2ArgumentParser()
    base_laml_bin_subparsers = base_laml_bin_parser.add_subparsers(title='LaML BINS',help='laml_bin help')

    # create the laml_bin list subcommand
    laml_bin_parser_list = base_laml_bin_subparsers.add_parser('list', help='List LaML Bins for a Projects')
    laml_bin_parser_list.add_argument('-n', '--name', type=str, nargs='+', help='List Single LaML Bin by name')
    laml_bin_parser_list.add_argument('-i', '--id', help='List Single LaML Bin by SignalWire ID')
    laml_bin_parser_list.add_argument('-j', '--json', action='store_true', help='List LaML Bins in JSON format')

    # create the laml_bin create subcommand
    laml_bin_parser_create = base_laml_bin_subparsers.add_parser('create', help='Create a LaML Bins')
    laml_bin_parser_create.add_argument('-n', '--name', nargs='+', help='Identifiable name of the LaML Bin', required=True)
    laml_bin_parser_create.add_argument('--contents',  nargs='+', help='XML contents of the LaML Bin.  Put formatted XML in single quotes, or leave blank to use an editor')

    # create the laml_bin update subcommand
    laml_bin_parser_update = base_laml_bin_subparsers.add_parser('update', help='Update a LaML Bins')
    laml_bin_parser_update.add_argument('-i', '--id', help='SignalWire ID of the LaML Bin', required=True)
    laml_bin_parser_update.add_argument('-n', '--name', nargs='+', help='Identifiable name of the LaML Bin')
    laml_bin_parser_update.add_argument('--contents', nargs='+', help='XML contents of the LaML Bin.  Put formatted XML in single quotes, or leave blank to use an editor')

    # create the laml_bin delete subcommand
    laml_bin_parser_delete = base_laml_bin_subparsers.add_parser('delete', help='Delete/Remove a LaML Bin')
    laml_bin_parser_delete.add_argument('-i', '--id', help='SignalWire ID of the LaML Bin to be deleted')
    laml_bin_parser_delete.add_argument('-f', '--force', action='store_true', help='Force removal.  Will not ask to confirm delete of LaML Bin')

    # Note: Adding contents on the command line via create and update isn't quite working right
    # because of character escaping it does on  newlines and tabs.
    # It works, just the formatting is a little strange.  Need to come back to this and clean it up

    ## subcommand functions for laml bins
    def laml_bin_list(self, args):
        '''list subcommand of laml_bin'''
        args = is_env_var(args)  # Replace any env vars in the command string

        query_params = ""
        if args.name:
            if len(args.name) == 1:
                name = args.name[0]
            elif len(args.name) > 1:
                name = "%20".join(args.name)
            else:
                print ("ERROR: Not valid arguments")
            query_params="?Name=%s" % name
        if args.id:
            sid = args.id
            query_params="/" + sid

        output, status_code = laml_bin_func(query_params)
        valid = validate_http(status_code)
        if valid:
            output = json.loads(output)
            if args.id and args.json:
                json_nice_print(output)
            
            elif args.id:
                k_num = str("1")

                print(k_num + ")")
                print("  SignalWire ID:\t" + str(output["sid"]))
                print("  LaML Bin Name:\t" + str(output["name"]))
                print("  Request URL:\t\t" + str(output["request_url"]))
                print("  Date Created:\t\t" + str(output["date_created"]))
                print("  Date Updated:\t\t" + str(output["date_updated"]))
                print("  Date Last Accessed\t" + str(output["date_last_accessed"]))
                print("  Number of Requests:\t" + str(output["num_requests"]))
                print("  Contents:\n\n  " + str(output["contents"]))
                print("")

            elif args.json:
                json_nice_print(output["laml_bins"])

            else:
                for k, v in enumerate(output["laml_bins"]):
                    k_num = str(k + 1)
                
                    print(k_num + ")")
                    print("  SignalWire ID:\t" + str(output["laml_bins"][k]["sid"]))
                    print("  LaML Bin Name:\t" + str(output["laml_bins"][k]["name"]))
                    print("  Request URL:\t\t" + str(output["laml_bins"][k]["request_url"]))
                    print("  Date Created:\t\t" + str(output["laml_bins"][k]["date_created"]))
                    print("  Date Updated:\t\t" + str(output["laml_bins"][k]["date_updated"]))
                    print("  Date Last Accessed\t" + str(output["laml_bins"][k]["date_last_accessed"]))
                    print("  Number of Requests:\t" + str(output["laml_bins"][k]["num_requests"]))
                    print("  Contents:\n\n  " + str(output["laml_bins"][k]["contents"]))
                    print("")

        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json_compatibility(output)
            else:
                print ("Error: " + output + "\n")

    def laml_bin_create(self, args):
        '''create subcommand of laml_bin'''
        args = is_env_var(args)  # Replace any env vars in the command string

        # Arg lists Needs to be converted into strings before they can be url encoded.
        if args.contents is None:
            template = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
</Response>"""

            with open('laml.xml', 'w') as lb:
                lb.write(template)
                lb.close()

            os.system("%s laml.xml" % EDITOR)

            with open('laml.xml', 'r') as lb:
                lines = lb.readlines()
                changed = change_verify(template, lines)

                if changed == 0:
                    #Nothing changed.  Exit gracefully and don't create the laml_bin
                    print("Exited.  Nothing to create.\n")
                    return
                else:
                    args.contents = lines

                lb.close()
                os.remove('laml.xml')

        # if contents is still blank, then nothing has changed, and exit gracefully
        if args.contents == "":
            print("LaML Bin XML contents are required!")
        else:
            name = ' '.join(args.name)
            contents = ' '.join(args.contents)
            name_url_encode = urllib.parse.quote(name)
            contents_url_encode = urllib.parse.quote(contents, safe='/')
            payload = "Contents=%s&Name=%s" % (contents_url_encode, name_url_encode)
            output, status_code = laml_bin_func(req_type="POST", payload=payload)
            valid = validate_http(status_code)
            if valid:
                output_json = json.loads(output)
                sid = str(output_json["sid"])
                print ("LaML Bin, " + sid + " has been created successfully\n")
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json_compatibility(output)
                else:
                    print ("Error: " + output + "\n")

    def laml_bin_update(self, args):
        '''create subcommand of laml_bin'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/" + sid
        if args.contents is None:
            # Get the LaML bin to Edit and store it in a file temporarily for editing
            query_params = "/" + sid
            output, status_code =  laml_bin_func(query_params)
            valid = validate_http(status_code)
            if valid:
                output_json = json.loads(output)
                output_laml_bin_contents = output_json["contents"]
                filename = '%s.xml' % sid
                template = output_laml_bin_contents.strip()

                with open(filename, 'w+') as lb:
                    print(output_laml_bin_contents, file=lb)
                    lb.close()

                os.system("%s %s" % (EDITOR, filename))

                with open (filename, 'r') as lb:
                    lines = lb.readlines()
                    changed = change_verify(template, lines)

                    if changed == 0:
                        # Nothing changed.  Exit gracefull and don't update the laml_bin
                        print("Exited.  Nothing to update.\n")
                        return
                    else:
                        args.contents = lines

                    lb.close()
                    os.remove('%s' % filename)
            else:
                print ("Error: Something bad happened")

        # URL Encode the params
        if args.name:
            name = ' '.join(args.name)
            name_url_encode = urllib.parse.quote(name)
        if args.contents:
            contents = ' '.join(args.contents)
            contents_url_encode = urllib.parse.quote(contents, safe='/')

        payload = ""
        if args.name and args.contents:
            payload = "Contents=%s&Name=%s" % (contents_url_encode, name_url_encode)
        elif args.name:
            payload = "Name=%s" % (name_url_encode)
        elif args.contents:
            payload = "Contents=%s" % (contents_url_encode)
        else:
            print("Nothing has changed.  Exiting.\n")

        if payload != "":
            output, status_code = laml_bin_func(query_params, req_type="POST", payload=payload)
            valid = validate_http(status_code)
            if valid:
                output_json = json.loads(output)
                print ("LaML Bin, " + sid + " has been updated successfully\n")
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json_compatibility(output)
                else:
                    print ("Error: " + output + "\n")

    def laml_bin_delete(self, args):
        '''create subcommand of laml_bin'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = '/' + sid
        if not args.force:
            confirm = str(input("Are you sure you want to proceed removing this LaML Bin?  This cannot be undone (Y/n): "))
        else:
            confirm = "y"

        if confirm.lower() == "yes" or confirm.lower() == "y":
            output, status_code = laml_bin_func( query_params, "DELETE" )
            valid = validate_http(status_code)
            if valid:
                print("Success! LaML Bin " + sid + " Removed\n")
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json_compatibility(output)
                else:
                    status_code = str(status_code)
                    print ( status_code + ": " + output + "\n" )
        else:
            print("Cancelling...")

    # Set default handlers for each sub command
    laml_bin_parser_list.set_defaults(func=laml_bin_list)
    laml_bin_parser_create.set_defaults(func=laml_bin_create)
    laml_bin_parser_update.set_defaults(func=laml_bin_update)
    laml_bin_parser_delete.set_defaults(func=laml_bin_delete)

    @cmd2.with_argparser(base_laml_bin_parser)
    def do_laml_bin(self, args: argparse.Namespace):
        '''List, Update, and LaML Bins'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('laml_bin')


## SIGNALWIRE SPACES / PROJECTs
    # Create the top level parser for space: space
    base_space_parser = cmd2.Cmd2ArgumentParser()
    base_space_subparsers = base_space_parser.add_subparsers(title='SPACE', help='space help')

    # Create the space cd subcommand
    space_parser_change = base_space_subparsers.add_parser('cd', help='change to a different space')
    space_parser_change.add_argument('-n', '--hostname', help = 'Domain Hostname of the Space', required=True)
    space_parser_change.add_argument('-t', '--token', help='API token for the Space', required=True)
    space_parser_change.add_argument('-p', '--project-id', help='Project ID to connect to within the space', required=True)

    # Create the space show subcommand
    space_parser_show = base_space_subparsers.add_parser('show', help='show the Current working space and project')
    space_parser_show.add_argument('-t', '--token', help='Include the API token', action='store_true')

    # Subcommand functions for space
    def space_cd(self, args):
        '''change directory subcommand of space'''
        valid_creds = validate_signalwire_creds(args.hostname, args.project_id, args.token)

        if valid_creds:
            os.environ['SIGNALWIRE_SPACE'] = args.hostname
            os.environ['PROJECT_ID'] = args.project_id
            os.environ['REST_API_TOKEN'] = args.token

            signalwire_space, project_id, rest_api_token = get_environment()
            print ("\nNow working in project, " + project_id + ", in the " + signalwire_space + " SignalWire space")
        else:
            print ("Those are not valid SignalWire Creds!\n")

    def space_show(self, args):
        '''show the working space and project configuration'''
        signalwire_space, project_id, rest_api_token = get_environment()
        if args.token:
            output = "SignalWire Space: " + signalwire_space + "\nProject ID: " + project_id + "\nToken: " + rest_api_token + "\n"
        else:
            output = "SignalWire Space: " + signalwire_space + "\nProject ID: " + project_id + "\n"

        print (output)

    # Set default handlers for each sub command
    space_parser_change.set_defaults(func=space_cd)
    space_parser_show.set_defaults(func=space_show)

    @cmd2.with_argparser(base_space_parser)
    def do_space(self, args: argparse.Namespace):
        '''set a new working space'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('space_help')

    # Create the top level parser for projects: project
    base_project_parser = cmd2.Cmd2ArgumentParser()
    base_project_subparsers = base_project_parser.add_subparsers(title='PROJECT',help='project help')

    # Create the project list subcommand
    project_parser_list = base_project_subparsers.add_parser('list', help='List LaML Bins for a Projects')
    project_parser_list.add_argument('-n', '--name', type=str, nargs='+', help='List Single Project by Friendly Name')
    project_parser_list.add_argument('-i', '--id', type=str, help='List SignalWire Space or Subspace with given SID')
    project_parser_list.add_argument('-j', '--json', action='store_true', help='List Signalwire Spaces in JSON format')

    # Create the project create subcommand
    project_parser_create = base_project_subparsers.add_parser('create', help='Create a subproject')
    project_parser_create.add_argument('-n', '--name', type=str, nargs="+", help='Create a subjproject under the current project', required=True)
    
    # Create the project update subcommand
    project_parser_update = base_project_subparsers.add_parser('update', help='Update a project')
    project_parser_update.add_argument('-n', '--name', type=str, nargs="+", help='Update the name of a subproject')
    project_parser_update.add_argument('-i', '--id', help='SignalWire ID of the subproject')

    # Create the project delete subcommand
    # DELETE IS NOT SUPPORTED BY THE API
    #project_parser_delete = base_project_subparsers.add_parser('delete', help='Delete/Remove a subproject')
    #project_parser_delete.add_argument('-i', '--id', type=str, help='Remove Sub Project with SignalWire ID')

    # Subcommand functions for project
    def project_list(self, args):
        '''list subcommand of project'''
        args = is_env_var(args)  # Replace any env vars in the command string

        if args.name:
            if len(args.name) == 1:
                friendly_name = args.name[0]
            elif len(args.name) > 1:
                friendly_name = "%20".join(args.name)
            query_params ="?FriendlyName=%s" % friendly_name
        elif args.id:
             sid = args.id
             query_params = "/" + sid
        else:
            query_params=""

        output, status_code = project_func(query_params=query_params)
        valid = validate_http(status_code)
        if valid:
            output = json.loads(output)
            if args.id and args.json:
                json_nice_print (output)
            
            elif args.id:
                k_num = str("1")

                print(k_num + ")")
                print("  SignalWire ID:\t" + str(output["sid"]))
                print("  Friendly Name:\t" + str(output["friendly_name"]))
                print("  Status:\t\t" + str(output["status"]))
                print("  Auth Token:\t\t" + str(output["auth_token"]))
                print("  Date Created:\t\t" + str(output["date_created"]))
                print("  Date Updated:\t\t" + str(output["date_updated"]))
                print("  Type:\t\t\t" + str(output["type"]))
                print("  Owner Account ID:\t" + str(output["owner_account_sid"]))
                print("  URI:\t\t\t" + str(output["uri"]))
                print("  Subproject:\t\t" + str(output['subproject']))
                print("")
            
            elif args.json:
                json_nice_print(output["accounts"])
            
            else:
                for k, v in enumerate(output["accounts"]):
                    k_num = str(k + 1)

                    print(k_num + ")")
                    print("  SignalWire ID:\t" + str(output["accounts"][k]["sid"]))
                    print("  Friendly Name:\t" + str(output["accounts"][k]["friendly_name"]))
                    print("  Status:\t\t" + str(output["accounts"][k]["status"]))
                    print("  Auth Token:\t\t" + str(output["accounts"][k]["auth_token"]))
                    print("  Date Created:\t\t" + str(output["accounts"][k]["date_created"]))
                    print("  Date Updated:\t\t" + str(output["accounts"][k]["date_updated"]))
                    print("  Type:\t\t\t" + str(output["accounts"][k]["type"]))
                    print("  Owner Account ID:\t" + str(output["accounts"][k]["owner_account_sid"]))
                    print("  URI:\t\t\t" + str(output["accounts"][k]["uri"]))
                    print("  Subproject:\t\t" + str(output["accounts"][k]['subproject']))
                    print("")

        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                status_code = str(status_code)
                print ( status_code + ": " + output + "\n" )

    def project_create(self, args):
        '''create subcommand of project'''
        if args.name:
            name = ' '.join(args.name)
            name_url_encode = urllib.parse.quote(name)

        payload = "FriendlyName=" + name_url_encode

        output, status_code = project_func(req_type="POST", payload=payload)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            sid = str(output_json["sid"])
            print ("Sub-Project " + sid + " has been created successfully\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json_compatibility(output)
            else:
                print("Error: " + output + "\n")

    def project_update(self, args):
        '''create subcommand of project'''
        sid = args.id
        query_params = "/" + sid

        # The only param is name.
        if args.name:
            name = ' '.join(args.name)
            name_url_encode = urllib.parse.quote(name)

        payload = "FriendlyName=" + name_url_encode

        output, status_code = project_func(query_params, req_type="POST", payload=payload)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            print ("Sub-Project " + sid + " has been updated successfully\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json_compatibility(output)
            else:
                print("Error: " + output + "\n")

    # NOTE: DELETE is not supported by the API    
    #def project_delete(self, args):
    #    '''create subcommand of project'''
    #    sid = args.id
    #    query_params = "/" + sid
    #    confirm = str(input("Are you sure you want to proceed removing this subproject?  This cannot be undone (Y/n): "))
    #    if confirm.lower() == "yes" or confirm.lower() == 'y':
    #        output, status_code = laml_bin_func(query_params, "DELETE")
    #        valid = validate_http(status_code)
    #        if valid:
    #            print("Success! Sub Project " + sid + " has been removed\n")
    #        else:
    #            is_json = validate_json(output)
    #            if is_json:
    #                print_error_json_compatibility(output)
    #            else:
    #                status_code = str(status_code)
    #                print(status_code + ": " + output + "\n")

    # Set default handlers for each sub command
    project_parser_list.set_defaults(func=project_list)
    project_parser_create.set_defaults(func=project_create)
    project_parser_update.set_defaults(func=project_update)
    #project_parser_delete.set_defaults(func=project_delete)

    @cmd2.with_argparser(base_project_parser)
    def do_project(self, args: argparse.Namespace):
        '''get or set a new working space'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('project_help')


## LaML APPLICATIONS ##
    # Create the top level parser for domain application: laml_app
    base_laml_app_parser = cmd2.Cmd2ArgumentParser()
    base_laml_app_subparsers = base_laml_app_parser.add_subparsers(title='LaML APP',help='laml_app help')

    # create the domain application list subcommand
    laml_app_parser_list = base_laml_app_subparsers.add_parser('list', help='List LaML Applications for the Project')
    laml_app_parser_list.add_argument('-i', '--id', help='SignalWire ID of the LamL Application')
    laml_app_parser_list.add_argument('-j', '--json', action='store_true', help='List LaML Application in JSON Format')

    # create the domain application create command
    laml_app_parser_create = base_laml_app_subparsers.add_parser('create', help='List Domain Applications for the Project')
    laml_app_parser_create.add_argument('-n', '--name',  nargs='+', help='Friendly name for the domain application', required=True)
    laml_app_parser_create.add_argument('--status-callback', help='URL to pass status updates to the application')
    laml_app_parser_create.add_argument('--status-callback-method',  help='HTTP method for status_callback.  Default is POST.', choices=["POST", "GET"], default="POST" )
    laml_app_parser_create.add_argument('--voice-caller-id-lookup',  help='Look up a callers ID from the database.  Possible values are true or false.  Default is false.', choices=["true", "false"], default="false")
    laml_app_parser_create.add_argument('--voice-url',  help='URL to request when an voice or fax is received')
    laml_app_parser_create.add_argument('--voice-method', help='HTTP method for voice_url.  Default is POST.')
    laml_app_parser_create.add_argument('--voice-fallback-url', help='URL to request if there is an error at primary')
    laml_app_parser_create.add_argument('--voice-fallback-method', help='HTTP method for voice_fallback.  Default is POST.', choices=["POST", "GET"], default="POST")
    laml_app_parser_create.add_argument('--message-status-callback', help='When a message receives a status change, a POST request to this URL with message details')
    laml_app_parser_create.add_argument('--sms-url',  help='URL to request when an SMS is received')
    laml_app_parser_create.add_argument('--sms-method',  help='HTTP method for sms_url.  Default is POST.', choices=["POST", "GET"], default="POST" )
    laml_app_parser_create.add_argument('--sms-fallback-url',  help='URL Signalwire will request if errors occur when fetching the sms_url ' )
    laml_app_parser_create.add_argument('--sms-fallback-method',  help='HTTP method for sms_fallback_url.  Default is POST.', choices=["POST", "GET"], default="POST" )
    laml_app_parser_create.add_argument('--sms-status-callback', help='When a message recevies a status change, a POST request to this URL with message details')

    # create the domain application update command
    laml_app_parser_update = base_laml_app_subparsers.add_parser('update', help='List Domain Applications for the Project')
    laml_app_parser_update.add_argument('-i', '--id', help='ID of the Domain Application to be updated', required=True)
    laml_app_parser_update.add_argument('-n', '--name',  nargs='+', help='Friendly name for the domain application')
    laml_app_parser_update.add_argument('--status-callback', help='URL to pass status updates to the application')
    laml_app_parser_update.add_argument('--status-callback-method',  help='HTTP method for status_callback.  Default is POST.', choices=["POST", "GET"], default="POST" )
    laml_app_parser_update.add_argument('--voice-caller-id-lookup',  help='Look up a callers ID from the database.  Possible values are true or false.  Default is false.', choices=["true", "false"], default="false")
    laml_app_parser_update.add_argument('--voice-url',  help='URL to request when an voice or fax is received')
    laml_app_parser_update.add_argument('--voice-method', help='HTTP method for voice_url.  Default is POST.')
    laml_app_parser_update.add_argument('--voice-fallback-url', help='URL to request if there is an error at primary')
    laml_app_parser_update.add_argument('--voice-fallback-method', help='HTTP method for voice_fallback.  Default is POST.', choices=["POST", "GET"], default="POST")
    laml_app_parser_update.add_argument('--message-status-callback', help='When a message receives a status change, a POST request to this URL with message details')
    laml_app_parser_update.add_argument('--sms-url',  help='URL to request when an SMS is received')
    laml_app_parser_update.add_argument('--sms-method',  help='HTTP method for sms_url.  Default is POST.', choices=["POST", "GET"], default="POST" )
    laml_app_parser_update.add_argument('--sms-fallback-url',  help='URL Signalwire will request if errors occur when fetching the sms_url ' )
    laml_app_parser_update.add_argument('--sms-fallback-method',  help='HTTP method for sms_fallback_url.  Default is POST.', choices=["POST", "GET"], default="POST" )
    laml_app_parser_update.add_argument('--sms-status-callback', help='When a message recevies a status change, a POST request to this URL with message details')


    # create the laml_app delete command
    laml_app_parser_delete = base_laml_app_subparsers.add_parser('delete', help='Delete LaML Applications for Project')
    laml_app_parser_delete.add_argument('-i', '--id', help='Unique id of the LaML Application', required=True)
    laml_app_parser_delete.add_argument('-f', '--force', action='store_true', help='Force removal.  Will not ask to confirm delete of LaML Applications')

    def laml_app_list(self, args):
        '''list subcommand of laml_app'''
        args = is_env_var(args)  # Replace any env vars in the command string

        if args.id:
            sid = args.id
            query_params = "/" + sid
        else:
            query_params=""

        output, status_code = laml_app_func(query_params)
        valid = validate_http(status_code)
        if valid:
            output = json.loads(output)
            if args.id and args.json:
                json_nice_print(output)

            elif args.id:
                k_num = str("1")

                print(k_num + ")")
                print("  SignalWireID:\t\t\t" + str(output["sid"]))
                print("  Name:\t\t\t\t" + str(output["friendly_name"]))
                print("  Date Created:\t\t\t" + str(output["date_created"]))
                print("  Date Updated:\t\t\t" + str(output["date_updated"]))
                print("  Voice URL:\t\t\t" + str(output["voice_url"]))
                print("  Voice Method:\t\t\t" + str(output["voice_method"]))
                print("  Voice Fallback URL:\t\t" + str(output["voice_fallback_url"]))
                print("  Voice Fallback Method:\t" + str(output["voice_fallback_method"]))
                print("  Status Callback:\t\t" + str(output["status_callback"]))
                print("  Status Callback Method:\t" + str(output["status_callback_method"]))
                print("  Voice Caller ID Lookup:\t" + str(output["voice_caller_id_lookup"]))
                print("  SMS URL:\t\t\t" + str(output["sms_url"]))
                print("  SMS Method:\t\t\t" + str(output["sms_method"]))
                print("  SMS Fallback URL:\t\t" + str(output["sms_fallback_url"]))
                print("  SMS Fallback Method:\t\t" + str(output["sms_fallback_method"]))
                print("  SMS Status Callback:\t\t" + str(output["sms_status_callback"]))
                print("  SMS Status Callback Method:\t" + str(output["sms_status_callback_method"]))
                print("  Message Status Callback:\t\t\t" + str(output["message_status_callback"]))
                print("")
            
            elif args.json:
                json_nice_print(output["applications"])

            else:
                for k, v in enumerate(output["applications"]):
                    k_num = str(k + 1)

                    print(k_num + ")")
                    print("  SignalWireID:\t\t\t" + str(output["applications"][k]["sid"]))
                    print("  Name:\t\t\t\t" + str(output["applications"][k]["friendly_name"]))
                    print("  Date Created:\t\t\t" + str(output["applications"][k]["date_created"]))
                    print("  Date Updated:\t\t\t" + str(output["applications"][k]["date_updated"]))
                    print("  Voice URL:\t\t\t" + str(output["applications"][k]["voice_url"]))
                    print("  Voice Method:\t\t\t" + str(output["applications"][k]["voice_method"]))
                    print("  Voice Fallback URL:\t\t" + str(output["applications"][k]["voice_fallback_url"]))
                    print("  Voice Fallback Method:\t" + str(output["applications"][k]["voice_fallback_method"]))
                    print("  Status Callback:\t\t" + str(output["applications"][k]["status_callback"]))
                    print("  Status Callback Method:\t" + str(output["applications"][k]["status_callback_method"]))
                    print("  Voice Caller ID Lookup:\t" + str(output["applications"][k]["voice_caller_id_lookup"]))
                    print("  SMS URL:\t\t\t" + str(output["applications"][k]["sms_url"]))
                    print("  SMS Method:\t\t\t" + str(output["applications"][k]["sms_method"]))
                    print("  SMS Fallback URL:\t\t" + str(output["applications"][k]["sms_fallback_url"]))
                    print("  SMS Fallback Method:\t\t" + str(output["applications"][k]["sms_fallback_method"]))
                    print("  SMS Status Callback:\t\t" + str(output["applications"][k]["sms_status_callback"]))
                    print("  SMS Status Callback Method:\t" + str(output["applications"][k]["sms_status_callback_method"]))
                    print("  Message Status Callback:\t\t\t" + str(output["applications"][k]["message_status_callback"]))
                    print("")
                
        else:
            is_json = validate_json_compatibility(output)
            if is_json:
                 print_error_json(output)
            else:
                 status_code = str(status_code)
                 print ( status_code + ": " + output + "\n" )


    def laml_app_create(self, args):
        '''create subcommand of laml_app'''
        args = is_env_var(args)  # Replace any env vars in the command string

        FriendlyName = ""
        MessageStatusCallback = ""
        SmsFallbackMethod = ""
        SmsFallbackUrl = ""
        SmsMethod = ""
        SmsStatusCallback = ""
        SmsUrl = ""
        StatusCallback = ""
        StatusCallbackMethod = ""
        VoiceCallerIdLookup = ""
        VoiceFallbackMethod = ""
        VoiceFallbackUrl = ""
        VoiceMethod = ""
        VoiceUrl = ""

        if args.name:
            args.name = ' '.join(args.name)
            FriendlyName = "&FriendlyName=" + urllib.parse.quote(args.name)
        if args.message_status_callback:
            MessageStatusCallback = "&MessageStatusCallback=" + urllib.parse.quote(args.message_status_callback)
        if args.sms_fallback_method:
            SmsFallbackMethod = "&SmsFallbackMethod=" + urllib.parse.quote(args.sms_fallback_method)
        if args.sms_fallback_url:
            SmsFallbackUrl = "&SmsFallbackUrl=" + urllib.parse.quote(args.sms_fallback_url)
        if args.sms_method:
            SmsMethod = "&SmsMethod=" + urllib.parse.quote(args.sms_method)
        if args.sms_status_callback:
            SmsStatusCallback = "SmsStatusCallback=" + urllib.parse.quote(args.sms_status_callback)
        if args.sms_url:
            SmsUrl = "&SmsUrl=" + urllib.parse.quote(args.sms_url)
        if args.status_callback:
            StatusCallback = "&StatusCallback=" + urllib.parse.quote(args.status_callback)
        if args.status_callback_method:
            StatusCallbackMethod = "&StatusCallbackMethod=" + urllib.parse.quote(args.status_callback_method)
        if args.voice_caller_id_lookup:
            VoiceCallerIdLookup = "&VoiceCallerIdLookup=" + urllib.parse.quote(args.voice_caller_id_lookup)
        if args.voice_fallback_method:
            VoiceFallbackMethod = "&VoiceFallbackMethod=" + urllib.parse.quote(args.voice_fallback_method)
        if args.voice_fallback_url:
            VoiceFallbackUrl = "&VoiceFallbackUrl=" + urllib.parse.quote(args.voice_fallback_url)
        if args.voice_method:
            VoiceMethod = "&VoiceMethod=" + urllib.parse.quote(args.voice_fallback_url)
        if args.voice_url:
            VoiceUrl = "&VoiceUrl=" + urllib.parse.quote(args.voice_url)

        payload = FriendlyName + MessageStatusCallback + SmsFallbackMethod + SmsFallbackUrl + SmsMethod + SmsStatusCallback + SmsUrl + StatusCallback + StatusCallbackMethod + VoiceCallerIdLookup + VoiceFallbackMethod + VoiceFallbackUrl + VoiceMethod + VoiceUrl

        output, status_code = laml_app_func(req_type="POST", payload=payload)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            sid = str(output_json["sid"])
            print ("LaML App, " + sid + " has been created successfully\n")
        else:
            is_json = valididate_json(output)
            if is_json:
                print_error_json_compatibility(output)
            else:
                print("Error: " + output + "\n")

    def laml_app_update(self, args):
        '''update subcommand of laml_app'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/" + sid
        FriendlyName = ""
        MessageStatusCallback = ""
        SmsFallbackMethod = ""
        SmsFallbackUrl = ""
        SmsMethod = ""
        SmsStatusCallback = ""
        SmsUrl = ""
        StatusCallback = ""
        StatusCallbackMethod = ""
        VoiceCallerIdLookup = ""
        VoiceFallbackMethod = ""
        VoiceFallbackUrl = ""
        VoiceMethod = ""
        VoiceUrl = ""

        if args.name:
            args.name = ' '.join(args.name)
            FriendlyName = "&FriendlyName=" + urllib.parse.quote(args.name)
        if args.message_status_callback:
            MessageStatusCallback = "&MessageStatusCallback=" + urllib.parse.quote(args.message_status_callback)
        if args.sms_fallback_method:
            SmsFallbackMethod = "&SmsFallbackMethod=" + urllib.parse.quote(args.sms_fallback_method)
        if args.sms_fallback_url:
            SmsFallbackUrl = "&SmsFallbackUrl=" + urllib.parse.quote(args.sms_fallback_url)
        if args.sms_method:
            SmsMethod = "&SmsMethod=" + urllib.parse.quote(args.sms_method)
        if args.sms_status_callback:
            SmsStatusCallback = "SmsStatusCallback=" + urllib.parse.quote(args.sms_status_callback)
        if args.sms_url:
            SmsUrl = "&SmsUrl=" + urllib.parse.quote(args.sms_url)
        if args.status_callback:
            StatusCallback = "&StatusCallback=" + urllib.parse.quote(args.status_callback)
        if args.status_callback_method:
            StatusCallbackMethod = "&StatusCallbackMethod=" + urllib.parse.quote(args.status_callback_method)
        if args.voice_caller_id_lookup:
            VoiceCallerIdLookup = "&VoiceCallerIdLookup=" + urllib.parse.quote(args.voice_caller_id_lookup)
        if args.voice_fallback_method:
            VoiceFallbackMethod = "&VoiceFallbackMethod=" + urllib.parse.quote(args.voice_fallback_method)
        if args.voice_fallback_url:
            VoiceFallbackUrl = "&VoiceFallbackUrl=" + urllib.parse.quote(args.voice_fallback_url)
        if args.voice_method:
            VoiceMethod = "&VoiceMethod=" + urllib.parse.quote(args.voice_method)
        if args.voice_url:
            VoiceUrl = "&VoiceUrl=" + urllib.parse.quote(args.voice_url)

        payload = FriendlyName + MessageStatusCallback + SmsFallbackMethod + SmsFallbackUrl + SmsMethod + SmsStatusCallback + SmsUrl + StatusCallback + StatusCallbackMethod + VoiceCallerIdLookup + VoiceFallbackMethod + VoiceFallbackUrl + VoiceMethod + VoiceUrl

        output, status_code = laml_app_func(query_params, req_type="POST", payload=payload)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            print ("LaML App, " + sid + " has been updated successfully\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json_compatibility(output)
            else:
                print ("Error: " + output + "\n")

    def laml_app_delete(self, args):
        sid = args.id
        query_params = "/" + sid
        if sid is not None:
            if not args.force:
                confirm = input("Remove LaML Application " + sid + "?  This cannot be undone! (y/n): ")
            else:
                confirm = "y"

            if (confirm.lower() == "y" or confirm.lower() == "yes"):
                output, status_code = laml_app_func(query_params, req_type="DELETE")
                valid = validate_http(status_code)
                if valid:
                    print("Success! LaML App " + sid + " Removed\n")
                else:
                    is_json = validate_json(output)
                    if is_json:
                        print_error_json_compatibility(output)
                    else:
                        status_code = str(status_code)
                        print ( status_code + ": " + output + "\n" )
            else:
                print ("OK. Cancelling.")
        else:
            print ("ERROR: An error has occurred")

    # Set default handlers for each sub command
    laml_app_parser_list.set_defaults(func=laml_app_list)
    laml_app_parser_create.set_defaults(func=laml_app_create)
    laml_app_parser_update.set_defaults(func=laml_app_update)
    laml_app_parser_delete.set_defaults(func=laml_app_delete)

    @cmd2.with_argparser(base_laml_app_parser)
    def do_laml_app(self, args: argparse.Namespace):
        '''List, Create, Update, or Delete domain applications'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('laml_app')


## DOMAIN APPLICATIONS ##
    # Create the top level parser for domain application: domain_application
    base_domain_application_parser = cmd2.Cmd2ArgumentParser()
    base_domain_application_subparsers = base_domain_application_parser.add_subparsers(title='DOMAIN APPLICATION',help='domain_application help')

    # create the domain application list subcommand
    domain_application_parser_list = base_domain_application_subparsers.add_parser('list', help='List Domain Applications for the Project')
    domain_application_parser_list.add_argument('-d', '--domain', type=str, nargs='+', help='Return all values for given domain of Domain App')
    domain_application_parser_list.add_argument('-n', '--name', type=str, nargs='+', help='Return all values for the given name of Domain App')
    domain_application_parser_list.add_argument('-i', '--id', help='SignalWire ID of the Domain Application')
    domain_application_parser_list.add_argument('-j', '--json', action='store_true', help='List Domain Applications in JSON Format')

    # create the domain application create command
    domain_application_parser_create = base_domain_application_subparsers.add_parser('create', help='List Domain Applications for the Project')
    domain_application_parser_create.add_argument('-n', '--name',  nargs='+', help='Friendly name for the domain application', required=True)
    domain_application_parser_create.add_argument('--identifier', help='Identifier of the domain.  Must be unique accross the project.', required=True)
    domain_application_parser_create.add_argument('--ip-auth-enabled',  help='Whether the domain application will enforce IP authentication (Boolean)', choices=['true','false'] )
    domain_application_parser_create.add_argument('--ip-auth', nargs='+',  help='A List of whitelisted / allowed IPs when --ip-auth-enabled is true ' )
    domain_application_parser_create.add_argument('--call-handler', help='How the domain Application handles calls', choices=['relay_context','laml_webhooks','laml_application','video_room'], required=True )
    domain_application_parser_create.add_argument('--call-request-url', help='The LaML URL to access when a call is received.  This is only used with laml_webhooks call handler')
    domain_application_parser_create.add_argument('--call-request-method', help='The HTTP method to use with call_request_url', choices=["POST", "GET"], default="POST")
    domain_application_parser_create.add_argument('--call-fallback-url', help='The LaML URL to access when call_request_url fails')
    domain_application_parser_create.add_argument('--call-fallback-method', help='The HTTP method to use with call_call_back_url', choices=["POST", "GET"], default="POST")
    domain_application_parser_create.add_argument('--call-status-callback-url', help='The URL to send status change messages to. This is only sed when call_hander is set to laml_webhooks')
    domain_application_parser_create.add_argument('--call-status-callback-method', help='The HTTP method to use with call_status_callback_url', choices=["POST", "GET"], default="POST")
    domain_application_parser_create.add_argument('--call-relay-context', help='Relay context to forward incoming calls to.  This is only used when call_handler is set to relay_context')
    domain_application_parser_create.add_argument('--call-laml-application-id', help='The ID of the LaML application to forward incoming calls to.  this is only used when call_handler is set to laml_application')
    domain_application_parser_create.add_argument('--call-video-room-id', help='The ID of the Video Room to forward incoming calls to.  This is only used when call_handler is set to video_room')
    domain_application_parser_create.add_argument('-e', '--encryption', type=str, help='Default Codecs', choices=['default', 'required', 'optional'])
    domain_application_parser_create.add_argument('--codecs', type=str, nargs='+', help='Default Codecs', choices=['OPUS', 'G722', 'PCMU', 'PCMA', 'VP8', 'H264'])
    domain_application_parser_create.add_argument('--ciphers', type=str, nargs='+',  help='Default Ciphers', choices=['AEAD_AES_256_GCM_8','AES_256_CM_HMAC_SHA1_80','AES_CM_128_HMAC_SHA1_80','AES_256_CM_HMAC_SHA1_32','AES_CM_128_HMAC_SHA1_32'])

    # create the domain application update command
    domain_application_parser_update = base_domain_application_subparsers.add_parser('update', help='List Domain Applications for the Project')
    domain_application_parser_update.add_argument('-i', '--id', help='ID of the Domain Application to be updated', required=True)
    domain_application_parser_update.add_argument('-n', '--name',  nargs='+', help='Friendly name for the domain application')
    domain_application_parser_update.add_argument('--identifier', help='Identifier of the domain.  Must be unique accross the project.')
    domain_application_parser_update.add_argument('--ip-auth-enabled',  help='Whether the domain application will enforce IP authentication (Boolean)', choices=['true','false'] )
    domain_application_parser_update.add_argument('--ip-auth', nargs='+',  help='A List of whitelisted / allowed IPs when --ip-auth-enabled is true ' )
    domain_application_parser_update.add_argument('--call-handler', help='How the domain Application handles calls', choices=['relay_context','laml_webhooks','laml_application','video_room'] )
    domain_application_parser_update.add_argument('--call-request-url', help='The LaML URL to access when a call is received.  This is only used with laml_webhooks call handler')
    domain_application_parser_update.add_argument('--call-request-method', help='The HTTP method to use with call_request_url', choices=["POST", "GET"], default="POST")
    domain_application_parser_update.add_argument('--call-fallback-url', help='The LaML URL to access when call_request_url fails')
    domain_application_parser_update.add_argument('--call-fallback-method', help='The HTTP method to use with call_call_back_url', choices=["POST", "GET"], default="POST")
    domain_application_parser_update.add_argument('--call-status-callback-url', help='The URL to send status change messages to. This is only sed when call_hander is set to laml_webhooks')
    domain_application_parser_update.add_argument('--call-status-callback-method', help='The HTTP method to use with call_status_callback_url', choices=["POST", "GET"], default="POST")
    domain_application_parser_update.add_argument('--call-relay-context', help='Relay context to forward incoming calls to.  This is only used when call_handler is set to relay_context')
    domain_application_parser_update.add_argument('--call-laml-application-id', help='The ID of the LaML application to forward incoming calls to.  this is only used when call_handler is set to laml_application')
    domain_application_parser_update.add_argument('--call-video-room-id', help='The ID of the Video Room to forward incoming calls to.  This is only used when call_handler is set to video_room')
    domain_application_parser_update.add_argument('-e', '--encryption', type=str, help='Default Codecs', choices=['default', 'required', 'optional'])
    domain_application_parser_update.add_argument('--codecs', type=str, nargs='+', help='Default Codecs', choices=['OPUS', 'G722', 'PCMU', 'PCMA', 'VP8', 'H264'])
    domain_application_parser_update.add_argument('--ciphers', type=str, nargs='+',  help='Default Ciphers', choices=['AEAD_AES_256_GCM_8','AES_256_CM_HMAC_SHA1_80','AES_CM_128_HMAC_SHA1_80','AES_256_CM_HMAC_SHA1_32','AES_CM_128_HMAC_SHA1_32'])

    # create the domain application delete command
    domain_application_parser_delete = base_domain_application_subparsers.add_parser('delete', help='List Domain Applications for the Project')
    # API takes the ID, Would be nice to do this by looking up by friendly name and return the ID,
    # but that may return multiple results.  Would need to write some guardrails around that.
    # For now just leaving with having provide the SID.
    domain_application_parser_delete.add_argument('-i', '--id', help='Unique id of the SIP Endpoint', required=True)

    def domain_application_list(self, args):
        '''list subcommand of domain_application'''
        args = is_env_var(args)  # Replace any env vars in the command string

        if args.domain:
            if len(args.domain) == 1:
                domain = args.domain[0]
            elif len(args.domain) > 1:
                domain = "%20".join(args.domain)
            query_params ="?filter_domain=%s" % domain
        elif args.name:
            if len(args.name) == 1:
                name = args.name[0]
            elif len(args.name) > 1:
                name = "%20".join(args.name)
            query_params = "?filter_name=%s" % name
        elif args.id:
            sid = args.id
            query_params = "/" + sid
        else:
            # Will list all Domain Applications
            query_params=""

        # When retrieving just an ID, there is no data json object
        output, status_code = domain_application_func(query_params)
        valid = validate_http(status_code)
        if valid:
            output = json.loads(output)
            if args.id and args.json:
                json_nice_print (output)

            elif args.id:
                k_num = str("1")

                print(k_num + ")")
                print("  SignalWire ID:\t\t" + str(output["id"]))
                print("  Name:\t\t\t\t" + str(output["name"]))
                print("  Domain:\t\t\t" + str(output["domain"]))
                print("  Identifier:\t\t\t" + str(output["identifier"]))
                print("  IP Auth Enabled:\t\t" + str(output["ip_auth_enabled"]))
                print("  IP Auth:\t\t\t" + str(', '.join(output["ip_auth"])))
                print("  Call Handler:\t\t\t" + str(output["call_handler"]))
                print("  Call Request URL:\t\t" + str(output["call_request_url"]))
                print("  Call Request Method:\t\t" + str(output["call_request_method"]))
                print("  Call Fallback URL:\t\t" + str(output["call_fallback_url"]))
                print("  Call Fallback Method:\t\t" + str(output["call_fallback_method"]))
                print("  Call Status Callback URL:\t" + str(output["call_status_callback_url"]))
                print("  Call Status Callback Method:\t" + str(output["call_status_callback_method"]))
                print("  Call Relay Context:\t\t" + str(output["call_relay_context"]))
                print("  Call LaML Application ID:\t" + str(output["call_laml_application_id"]))
                print("  Encryption:\t\t\t" + str(output["encryption"]))
                print("  Codecs:\t\t\t" + str(', '.join(output["codecs"])))
                print("  Encryption Ciphers:\t\t" + str(', '.join(output["ciphers"])))
                print("")

            elif args.json:
                json_nice_print (output["data"])

            else:
                for k, v in enumerate(output["data"]):
                    k_num = str(k + 1)

                    print(k_num + ")")
                    print("  SignalWire ID:\t\t" + str(output["data"][k]["id"]))
                    print("  Name:\t\t\t\t" + str(output["data"][k]["name"]))
                    print("  Domain:\t\t\t" + str(output["data"][k]["domain"]))
                    print("  Identifier:\t\t\t" + str(output["data"][k]["identifier"]))
                    print("  IP Auth Enabled:\t\t" + str(output["data"][k]["ip_auth_enabled"]))
                    print("  IP Auth:\t\t\t" + str(', '.join(output["data"][k]["ip_auth"])))
                    print("  Call Handler:\t\t\t" + str(output["data"][k]["call_handler"]))
                    print("  Call Request URL:\t\t" + str(output["data"][k]["call_request_url"]))
                    print("  Call Request Method:\t\t" + str(output["data"][k]["call_request_method"]))
                    print("  Call Fallback URL:\t\t\t" + str(output["data"][k]["call_fallback_url"]))
                    print("  Call Fallback Method:\t\t" + str(output["data"][k]["call_fallback_method"]))
                    print("  Call Status Callback URL:\t\t" + str(output["data"][k]["call_status_callback_url"]))
                    print("  Call Status Callback Method:\t" + str(output["data"][k]["call_status_callback_method"]))
                    print("  Call Relay Context:\t\t" + str(output["data"][k]["call_relay_context"]))
                    print("  Call LaML Application ID:\t" + str(output["data"][k]["call_laml_application_id"]))
                    print("  Encryption:\t\t\t" + str(output["data"][k]["encryption"]))
                    print("  Codecs:\t\t\t" + str(', '.join(output["data"][k]["codecs"])))
                    print("  Encryption Ciphers:\t\t" + str(', '.join(output["data"][k]["ciphers"])))
                    print("")
            
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json(output)
                else:
                    print (status_code + ": " + output + "\n" )

    def domain_application_create(self, args):
        '''create subcommand of domain_application'''
        args = is_env_var(args)  # Replace any env vars in the command string

        # Make the Name look nice
        if args.name:
            args.name = ' '.join(args.name)
        domain_application_dictionary = {
           "name": args.name,
           "identifier": args.identifier,
           "ip_auth_enabled": args.ip_auth_enabled,
           "ip_auth": args.ip_auth,
           "call_handler": args.call_handler,
           "call_request_url": args.call_request_url,
           "call_request_method": args.call_request_method,
           "call_fallback_url": args.call_fallback_url,
           "call_fallback_method": args.call_fallback_method,
           "call_status_callback_url": args.call_status_callback_url,
           "call_status_callback_method": args.call_status_callback_method,
           "call_relay_context": args.call_relay_context,
           "call_laml_application_id": args.call_laml_application_id,
           "call_video_room_id": args.call_video_room_id,
           "encryption": args.encryption,
           "codecs": args.codecs,
           "ciphers": args.ciphers
        }

        create_domain_application_dictionary = {}
        for x, y in domain_application_dictionary.items():
            if y is not None:
                create_domain_application_dictionary[x] = y

        payload = json.dumps(create_domain_application_dictionary)
        output, status_code = domain_application_func(req_type="POST", payload=payload)
        valid = validate_http(status_code)
        if valid:
            # Grab the SID of the new domain app and output for user
            output_json = json.loads(output)
            endpoint_id = output_json["id"]
            print("Domain Application created with ID: " + endpoint_id)
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print(status_code + ": " + output + "\n")

    def domain_application_update(self, args):
        '''create subcommand of domain_application'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/" + sid
        # Make the Name look nice
        if args.name:
            print(args.name)
            args.name = ' '.join(args.name)
        domain_application_dictionary = {
           "name": args.name,
           "identifier": args.identifier,
           "ip_auth_enabled": args.ip_auth_enabled,
           "ip_auth": args.ip_auth,
           "call_handler": args.call_handler,
           "call_request_url": args.call_request_url,
           "call_request_method": args.call_request_method,
           "call_fallback_url": args.call_fallback_url,
           "call_fallback_method": args.call_fallback_method,
           "call_status_callback_url": args.call_status_callback_url,
           "call_status_callback_method": args.call_status_callback_method,
           "call_relay_context": args.call_relay_context,
           "call_laml_application_id": args.call_laml_application_id,
           "call_video_room_id": args.call_video_room_id,
           "encryption": args.encryption,
           "codecs": args.codecs,
           "ciphers": args.ciphers
        }

        update_domain_application_dictionary = {}
        for x, y in domain_application_dictionary.items():
            if y is not None:
                update_domain_application_dictionary[x] = y

        payload = json.dumps(update_domain_application_dictionary)
        output, status_code = domain_application_func(query_params, req_type="PUT", payload=payload)
        valid = validate_http(status_code)
        if valid:
            print("Domain Application, " + sid + " has been udpated.\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print(status_code + ": " + outpout + "\n")

    def domain_application_delete(self, args):
        '''delete subcommand of domain_application'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/" + sid
        if sid is not None:
            confirm = input("Remove Domain Application " + sid + "? This cannot be undone! (y/n): " )
            if (confirm == "Y" or confirm == "y"):
                output, status_code = domain_application_func(query_params, req_type="DELETE")
                valid = validate_http(status_code)
                if valid:
                    print("Success! Domain Application " + sid + " Removed\n")
                else:
                    is_json = validate_json(output)
                    if is_json:
                        print_error_json(output)
                    else:
                        print (status_code + ": " + output + "\n")
            else:
                print ("Aborting.")
        else:
            print ("ERROR")

    # Set default handlers for each sub command
    domain_application_parser_list.set_defaults(func=domain_application_list)
    domain_application_parser_create.set_defaults(func=domain_application_create)
    domain_application_parser_update.set_defaults(func=domain_application_update)
    domain_application_parser_delete.set_defaults(func=domain_application_delete)

    @cmd2.with_argparser(base_domain_application_parser)
    def do_domain_application(self, args: argparse.Namespace):
        '''List, Create, Update, or Delete domain applications'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('domain_application')


## NUMBER GROUPS ##
    # Create the top level parser for number groups: number_group
    base_number_group_parser = cmd2.Cmd2ArgumentParser()
    base_number_group_subparsers = base_number_group_parser.add_subparsers(title='NUMBER GROUP',help='number_group help')

    # create the number groups list subcommand
    number_group_parser_list = base_number_group_subparsers.add_parser('list', help='List Number Groups for the Project')
    number_group_parser_list.add_argument('-n', '--name', nargs='+', help='Return all Number Groups containing this value')
    number_group_parser_list.add_argument('-i', '--id',help='Return a Number Group with the given ID')
    number_group_parser_list.add_argument('-j', '--json', action='store_true', help='List Number Groups in JSON Format')

    # create the number groups create command
    number_group_parser_create = base_number_group_subparsers.add_parser('create', help='Create for the Project')
    number_group_parser_create.add_argument('-n', '--name', nargs='+', help='Name given to a Number Group within the project', required=True)
    number_group_parser_create.add_argument('-s', '--sticky-sender', help='Whether the number group uses the same From number for outbound requests',  choices=['true', 'false'], default='false')

    # create the domain application update command
    number_group_parser_update = base_number_group_subparsers.add_parser('update', help='Update Number Groups for the Project')
    number_group_parser_update.add_argument('-n', '--name', nargs='+', help='Update the name of a Number Group')
    number_group_parser_update.add_argument('-i', '--id', help='ID of the Number Group to be udpated', required=True)
    number_group_parser_update.add_argument('-s', '--sticky-sender', help='Whether the number group uses the same From number for Outbound requests',  choices=['true', 'false'], default='false')

    # create the domain application delete command
    number_group_parser_delete = base_number_group_subparsers.add_parser('delete', help='Delete Number Groups for the Project')
    number_group_parser_delete.add_argument('-i', '--id', help='Unique id of the Number Group to be removed', required=True)
    number_group_parser_delete.add_argument('-f', '--force', action='store_true', help='Force removal.  Will not ask to confirm delete of Number Groups')

    def number_group_list(self, args):
        '''list subcommand of number_group'''
        args = is_env_var(args)  # Replace any env vars in the command string

        if args.name:
            if len(args.name) == 1:
                name = args.name[0]
            elif len(args.name) > 1:
                name = "%20".join(args.name)
            query_params ="?filter_name=%s" % name
        elif args.id:
            sid = args.id
            query_params = "/%s" % sid
        else:
            query_params=""

        output, status_code = number_group_func( query_params )
        valid = validate_http(status_code)
        if valid:
            output = json.loads(output)
            if args.id and args.json:
                json_nice_print (output)
            
            elif args.id:
                k_num = str("1")

                print(k_num + ")")
                print("  SignalWire ID:\t" + output["id"])
                print("  Name:\t\t\t" + output["name"])
                print("  Phone Number Count:\t" + str(output["phone_number_count"]))
                print("  Sticky Sender:\t" + str(output["sticky_sender"]))
                print("")

            elif args.json:
                json_nice_print (output["data"])

            else:
                for k, v in enumerate(output["data"]):
                    k_num = str(k + 1)

                    print(k_num + ")")
                    print("  SignalWire ID:\t" + output["data"][k]["id"])
                    print("  Name:\t\t\t" + output["data"][k]["name"])
                    print("  Phone Number Count:\t" + str(output["data"][k]["phone_number_count"]))
                    print("  Sticky Sender:\t" + str(output["data"][k]["sticky_sender"]))
                    print("")
    
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print ("Error: " + output + "\n")

    def number_group_create(self, args):
        '''create subcommand of number_group'''
        args = is_env_var(args)  # Replace any env vars in the command string

        number_group_dictionary = {
          "name": args.name,
          "sticky_sender": args.sticky_sender
        }

        payload = json.dumps(number_group_dictionary)
        output, status_code = number_group_func(req_type="POST", payload=payload)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            print (output_json)
            endpoint_id = output_json["id"]
            print("Number group created with ID: " + endpoint_id + "\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print (status_code + ": " + output + "\n")

    def number_group_update(self, args):
        '''update subcommand of number_group'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/" + sid
        number_group_dictionary = {
          "name": args.name,
          "sticky_sender": args.sticky_sender
        }

        update_number_group_dictionary = {}
        for x, y in number_group_dictionary.items():
            if y is not None:
              update_number_group_dictionary[x] = y

        payload = json.dumps(update_number_group_dictionary)
        output, status_code = number_group_func(query_params, req_type="PUT", payload=payload)
        valid = validate_http(status_code)
        if valid:
            print("Success! Number group " + sid + " Updated\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print (status_code + ": " + output + "\n" )

    def number_group_delete(self, args):
        '''delete subcommand of number_group'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/" + sid
        if sid is not None:
            if not args.force:
                confirm = input("Remove Number Group " + sid + "? This cannot be undone! (y/n): " )
            else:
                confirm = "y"

            if (confirm == "Y" or confirm == "y"):
                output, status_code = number_group_func(query_params, req_type="DELETE")
                valid = validate_http(status_code)
                if valid:
                    print("Success! Number Group " + sid + " Removed\n")
                else:
                    is_json = validate_json(output)
                    if is_json:
                        print_error_json(output)
                    else:
                        status_code = str(status_code)
                        print ( status_code + ": " + output + "\n" )
            else:
                print ("OK. Cancelling")
        else:
            print ("ERROR")

    # Set default handlers for each sub command
    number_group_parser_list.set_defaults(func=number_group_list)
    number_group_parser_create.set_defaults(func=number_group_create)
    number_group_parser_update.set_defaults(func=number_group_update)
    number_group_parser_delete.set_defaults(func=number_group_delete)

    @cmd2.with_argparser(base_number_group_parser)
    def do_number_group(self, args: argparse.Namespace):
        '''List, Create, Update, or Delete domain applications'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('number_group')

## FIFO QUEUES ##
# Create the top level parser for queues: fifo_queue
    base_fifo_queue_parser = cmd2.Cmd2ArgumentParser()
    base_fifo_queue_subparsers = base_fifo_queue_parser.add_subparsers(title='FIFO QUEUES',help='fifo_queue help')

    # create the fifo_queue list subcommand
    fifo_queue_parser_list = base_fifo_queue_subparsers.add_parser('list', help='List FIFO Queues for a Project')
    fifo_queue_parser_list.add_argument('-i', '--id', help='List a Single FIFO Queue by SignalWire ID')
    fifo_queue_parser_list.add_argument('-j', '--json', action='store_true', help='Output FIFO Queue(s) in JSON format')

    # create the fifo_queue update subcommand
    fifo_queue_parser_create = base_fifo_queue_subparsers.add_parser('create', help='Create a FIFO Queue')
    fifo_queue_parser_create.add_argument('-n', '--name', nargs='+', help='Identifiable name of the LaML Bin', required=True)
    fifo_queue_parser_create.add_argument('-m', '--maxsize', help='The maximum number of calls that are allowed to wait in a queue.  Default is 5.',default='5')

    # create the fifo_queue update subcommand
    fifo_queue_parser_update = base_fifo_queue_subparsers.add_parser('update', help='Update a FIFO Queue')
    fifo_queue_parser_update.add_argument('-i', '--id', help='SignalWire ID of the FIFO Queue')
    fifo_queue_parser_update.add_argument('-n', '--name', nargs='+', help='Identifiable name of the FIFO Queue', required=True)
    fifo_queue_parser_update.add_argument('-m', '--maxsize', help='The maximum number of calls that are allowed to wait in a queue.')

    # create the fifo_queue delete subcommand
    fifo_queue_parser_delete = base_fifo_queue_subparsers.add_parser('delete', help='Delete/Remove a FIFO Queue')
    fifo_queue_parser_delete.add_argument('-i', '--id', help='SignalWire ID of the FIFO Queue to be deleted')
    fifo_queue_parser_delete.add_argument('-f', '--force', action='store_true', help='Force removal.  Will not ask to confirm delete of FIFO Queue')

    def fifo_queue_list(self, args):
        '''list subcommand of fifo_queue '''
        args = is_env_var(args)  # Replace any env vars in the command string

        query_params = "/Queues"
        if args.id:
            sid = args.id
            query_params = query_params + "/" + sid

        output, status_code = fifo_queue_func(query_params)
        valid = validate_http(status_code)
        if valid:
            # Format the output depending on user args
            output = json.loads(output)
            if args.id and args.json:
                json_nice_print(output)

            elif args.id:
                k_num = str("1")

                # Add Values to the ENV
                for k, v in output.items():
                    key = k.upper()
                    if isinstance(v, list):
                        value = str(', '.join(v))
                    else:
                        value = str(v)

                    #set_shell_env(key + "=" + value)

                print(k_num + ")")
                print("  SignalWire ID:\t" + str(output["sid"]))
                print("  Name:\t\t\t" +  str(output["friendly_name"]))
                print("  Date Created:\t\t" +  str(output["date_created"]))
                print("  Date Updated:\t\t" + str(output["date_updated"]))
                print("  Max Size:\t\t" + str(output["max_size"]))
                print("  Current Size:\t\t" + str(output["current_size"]))
                print("  Average Wait Time:\t" + str(output["average_wait_time"]))
                print("")

            elif args.json:
                json_nice_print(output["queues"])

            else:
                for k, v in enumerate(output["queues"]):
                    k_num = str(k + 1)

                    print(k_num + ")")
                    print("  SignalWire ID:\t" + str(output["queues"][k]["sid"]))
                    print("  Name:\t\t\t" +  str(output["queues"][k]["friendly_name"]))
                    print("  Date Created:\t\t" +  str(output["queues"][k]["date_created"]))
                    print("  Date Updated:\t\t" + str(output["queues"][k]["date_updated"]))
                    print("  Max Size:\t\t" + str(output["queues"][k]["max_size"]))
                    print("  Current Size:\t\t" + str(output["queues"][k]["current_size"]))
                    print("  Average Wait Time:\t" + str(output["queues"][k]["average_wait_time"]))
                    print("")

        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json_compatibility(output)
            else:
                print("Error: " + output + "\n")

    def fifo_queue_create(self, args):
        '''list subcommand of fifo_queue '''
        args = is_env_var(args)  # Replace any env vars in the command string

        query_params="/Queues"

        if args.name:
            name = ' '.join(args.name)
            name_url_encode = urllib.parse.quote(name)
            FriendlyName = "FriendlyName=" + name_url_encode

        if args.maxsize:
            maxsize = args.maxsize
            maxsize_url_encode = urllib.parse.quote(maxsize)
            MaxSize = "MaxSize=" + maxsize_url_encode

        payload = FriendlyName + "&" + MaxSize
        output, status_code = fifo_queue_func(query_params, req_type="POST", payload=payload)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            sid = str(output_json["sid"])
            print ("FIFO Queue " + sid + " has been created successfully\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json_compatibility(output)
            else:
                print("Error: " + output + "\n")

    def fifo_queue_update(self, args):
        '''list subcommand of fifo_queue '''
        args = is_env_var(args)  # Replace any env vars in the command string

        query_params = "/Queues"

        if args.id:
            sid = args.id
            query_params = query_params + "/" + sid

        if args.name:
            name = ' '.join(args.name)
            name_url_encode = urllib.parse.quote(name)
            FriendlyName = "FriendlyName=" + name_url_encode
        else:
            FriendlyName = ""

        if args.maxsize:
            maxsize = args.maxsize
            maxsize_url_encode = urllib.parse.quote(maxsize)
            MaxSize = "MaxSize=" + maxsize_url_encode
        else:
            MaxSize = ""

        payload = FriendlyName + "&" + MaxSize
        output, status_code = fifo_queue_func(query_params, req_type="POST", payload=payload)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            print ("FIFO Queue " + sid + " has been updated successfully\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json_compatibility(output)
            else:
                print("Error: " + output + "\n")

    def fifo_queue_delete(self, args):
        '''delete subcommand of fifo_queue'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/Queues/" + sid
        if sid is not None:
            if not args.force:
                confirm = input("Remove FIFO Queue " + sid + "?  This cannot be undone! (Y/n): ")
            else:
                confirm = "y"

            if confirm.lower() == "yes" or confirm.lower() == "y":
                output, status_code = fifo_queue_func(query_params, "DELETE")
                valid = validate_http(status_code)
                if valid:
                    print("Success! FIFO Queue " + sid + " has been removed\n")
                else:
                    is_json = validate_json(output)
                    if is_json:
                        print_error_json_compatibility(output)
                    else:
                        status_code = str(status_code)
                        print(status_code + ": " + output + "\n")
            else:
                print("OK.  Cancelling...\n")
        else:
            print ("ERROR: Please enter a valid SignalWire ID\n")

    # Set default handlers for each sub command
    fifo_queue_parser_list.set_defaults(func=fifo_queue_list)
    fifo_queue_parser_create.set_defaults(func=fifo_queue_create)
    fifo_queue_parser_update.set_defaults(func=fifo_queue_update)
    fifo_queue_parser_delete.set_defaults(func=fifo_queue_delete)

    @cmd2.with_argparser(base_fifo_queue_parser)
    def do_fifo_queue(self, args: argparse.Namespace):
        '''List, Create, Update, and Remove Queues'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('fifo_queue')

## CALLS ##
    call_parser_make = cmd2.Cmd2ArgumentParser()
    call_parser_make.add_argument('-f', '--from-num', type=str, help='Calling Party Number -- Must be a Signalwire Number', required=True)
    call_parser_make.add_argument('-t', '--to-num', type=str, help='Receiving Party Numner', required=True)
    call_parser_make.add_argument('-u', '--url', type=str, help='URL of Dialplan Bin')
    call_parser_make.add_argument('--laml-bin-id', help='SignalWire ID of a LaML Bin')

    call_parser_get = cmd2.Cmd2ArgumentParser()
    call_parser_get.add_argument('-i', '--id', type=str, help='Retrieve call logs for the SignalWire ID')
    call_parser_get.add_argument('--all-active', action='store_true', help='Return all currently active calls for thep project')
    
    @cmd2.with_argparser(call_parser_make)
    def do_send_call(self, args: argparse.Namespace):
        '''Send an outbound call'''
        args = is_env_var(args)

        from_no = "From=" + urllib.parse.quote(args.from_num)
        to_no = "&To=" + urllib.parse.quote(args.to_num)
        # TODO: validate whether or not there is a URL there.  There may be other situtations where URL is not necessary.
        if args.laml_bin_id:
            # Get the URL from the ID
            sid = args.laml_bin_id
            query_params = "/" + sid
            output, status_code = laml_bin_func(query_params)
            valid = validate_http(status_code)
            if valid:
                output_json = json.loads(output)
                url = "&Url=" + urllib.parse.quote(output_json["request_url"])
            else:
                is_json = validate_json(output)
                if is_json:
                    print_error_json(output)
                else:
                    status_code = str(status_code)
                    print ( status_code + ": " + output + "\n" )
        elif args.url:
            url = "&Url=" + urllib.parse.quote(args.url)
        # TODO: Validate that a validly formatted url is entered before sending to the API
        payload = from_no + to_no + url
        output, status_code = call_func(req_type='POST', payload=payload)
        valid = validate_http(status_code)
        if valid: 
            output_json = json.loads(output)
            print ("\nCall sent successfully")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                status_code = str(status_code)
                print ( status_code + ": " + output + "\n" )

## RETRIEVE A CALL ##
    # Will be helpful for debugging calls
    @cmd2.with_argparser(call_parser_get)
    def do_get_call(self, args:argparse.Namespace):
        '''retrieve logs of a call'''
        query_params = ""
        if args.id:
            sid = args.id
            query_params = "/" + sid

        output, status_code = call_func(query_params)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            # Output all currently active calls
            # TODO: move this into a function that can service other types of requests like this.
            if args.all_active: 
                all_active_json = output_json["calls"]
                active_calls_list = []
                for i in range(0, len(all_active_json)):
                    if all_active_json[i]["status"] == 'in-progress':
                        active_calls_list.append(all_active_json[i])
  
                if len(active_calls_list) == 0:
                    print("No Active Calls!\n")
                else:
                    json_nice_print(active_calls_list)
            else:
                json_nice_print(output_json)
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json(output)
            else:
                print ( status_code + ": " + output + "\n" )

## SEND TEXT MESSAGE ##
    sms_parser = cmd2.Cmd2ArgumentParser()
    sms_parser.add_argument('-f', '--from-num', type=str,  help='Send text FROM number -- Must be a signalwire number registered to campaign', required=True)
    sms_parser.add_argument('-t', '--to-num', type=str, help='Send sms text message TO number', required=True)
    sms_parser.add_argument('-b', '--text-body', type=str, nargs='+',  help='Send sms text message TO number', required=True)
    @cmd2.with_argparser(sms_parser)
    def do_send_text(self, args: argparse.Namespace):
        '''Send an SMS Text Message'''
        # TODO: Move this into the functions file
        args = is_env_var(args)

        signalwire_space, project_id, rest_api_token = get_environment()
        from_no = args.from_num
        to_no = args.to_num
        text_body = " ".join(args.text_body)
        print ("sending a sms text from " + from_no + " to " + to_no + ": \"" + text_body + "\"" )
        client = signalwire_client(project_id, rest_api_token, signalwire_space_url = '%s.signalwire.com' % signalwire_space)
        message = client.messages.create (
          to=to_no,
          from_=from_no,
          body=text_body
        )

        time.sleep (1)
        print("Complete!")


## FACSIMILE ##
# Create the top level parser for Fax: fax
    base_fax_parser = cmd2.Cmd2ArgumentParser()
    base_fax_subparsers = base_fax_parser.add_subparsers(title='FAX',help='fax help')

    # create the fax list command
    fax_parser_list = base_fax_subparsers.add_parser('list', help='List Faxes')
    fax_parser_list.add_argument('-i', '--id', type=str, help='Retrive a fax by ID')
    fax_parser_list.add_argument('--sent',  action='store_true', help='Show sent [outbound] faxes')
    fax_parser_list.add_argument('--received', action='store_true', help='Show received [inbound] faxes')

    # create the fax update command
    # Adding here because the Fax status can be updated, but not sure in what scenario(s) that is needed
    # NOTE: During testing of this, I found that all responses seem to give a 400 status back. I don't know if this is something that is actually still supposed to work.
    fax_parser_update = base_fax_subparsers.add_parser('update', help='Update a Fax by Signalwire ID')
    fax_parser_update.add_argument('-id', '--id', type=str, help='Signalwire ID of Fax to be updated', required=True)
    fax_parser_update.add_argument('-s', '--status', help='The status to change the fax to: queued, processing, sending, delivered, receiving, received, no-answer, busy, failed, canceled', choices=['queued','processing','sending','delivered','receiving','received','no-answer','busy','failed','canceled'])

    # create the fax send command
    fax_parser_send = base_fax_subparsers.add_parser('send', help='Send a to a destination')
    fax_parser_send.add_argument('--to_num', type=str, help='Destinaton Number to send fax', required=True)
    fax_parser_send.add_argument('--from_num', type=str, help='From Number to send fax, must be a number associated with the Space and Project', required=True)
    fax_parser_send.add_argument('-m', '--media-url', type=str, help='URL location of the accessible media (PDF) file', required=True)
    fax_parser_send.add_argument('-b', '--background', action='store_true', help='Send a fax in the background without any output')

    # create the fax receive command
    # Placeholder to receive a fax.  Not sure how this would work.

    # create the fax delete command
    fax_parser_delete = base_fax_subparsers.add_parser('delete', help='Delete Faxes')
    fax_parser_delete.add_argument('-id', '--id', type=str, help='Delete a fax record by SignalWire ID')
    fax_parser_delete.add_argument('-f', '--force', action='store_true', help='Force removal.  Will not ask to confirm delete Fax record')

    def fax_list(self, args):
        '''list subcommand of fax'''
        args = is_env_var(args)  # Replace any env vars in the command string

        query_params = "/Faxes"
        if args.id:
            sid = args.id
            query_params = query_params + "/" + sid

        output, status_code = fax_func(query_params)
        valid = validate_http(status_code)
        if valid:
            # format the output depnding on user args
            output = json.loads(output)
            if args.id:
                json_nice_print(output)
                return

            if args.received:
                all_received_json = output["faxes"]
                received_faxes_list = []
                for i in range(0, len(all_received_json)):
                    if all_received_json[i]["direction"] == 'inbound':
                        received_faxes_list.append(all_received_json[i])

                if len(received_faxes_list) == 0:
                    print("No Received Faxes found\n")
                else:
                    json_nice_print(received_faxes_list)

            elif args.sent:
                all_sent_json = output["faxes"]
                sent_faxes_list = []
                for i in range(0, len(all_sent_json)):
                    if all_sent_json[i]["direction"] == 'outbound':
                        sent_faxes_list.append(all_sent_json[i])

                if len(sent_faxes_list) == 0:
                    print("No Sent Faxes found\n")
                else:
                    json_nice_print(sent_faxes_list)
            else:
                json_nice_print(output["faxes"])

    def fax_update(self, args):
        '''update subcommand of fax'''
        args = is_env_var(args)  # Replace any env vars in the command string

        query_params = "/Faxes"

        if args.id:
            sid = args.id
            query_params = query_params + "/" + sid

        if args.status:
            status = args.status
            status_url_encode = urllib.parse.quote(status)
            Status="Status=" + status_url_encode

        payload = Status
        output, status_code = fax_func(query_params, req_type='POST', payload=payload)
        valid = validate_http(status_code)
        if valid:
            output_json = json.loads(output)
            print ("FAX" + sid + " has been updated successfully\n")
        else:
            is_json = validate_json(output)
            if is_json:
                print_error_json_compatibility(output)
            else:
                print("Error: " + output + "\n")

    def fax_send(self, args):
        '''Send an outbound fax'''
        # TODO: Should Move this to the functions, but going to live here for now.
        # TODO: Long term I would like to be able to upload a PDF to wirestarter
        #       and wirestarter will just take the file, add it to the webserver, and figure out the URL to send.
        #       This is just a Phase 1 iteration.
        args = is_env_var(args)

        signalwire_space, project_id, rest_api_token = get_environment()
        from_no = args.from_num
        to_no = args.to_num
        url = args.media_url
        print ("Sending a fax from " + from_no + " to " + to_no )
        client = signalwire_client(project_id, rest_api_token, signalwire_space_url = '%s.signalwire.com' % signalwire_space)
        fax = client.fax.faxes.create (
          to=to_no,
          from_=from_no,
          media_url=url
        )

        # TODO: Web call back to confirm status // Some kind of output while sending?
        faxsid = fax.sid
        if faxsid is None or faxsid == "":
            print ("There was an ERROR, please try the fax again")
        else:
            if not args.background:
                # Setting as a 10 minute maximum.
                # This will accomodate about a 10 page fax
                # This can be adjusted if there is a need.
                for i in range(1, 200):
                    query_params = "/Faxes/" + faxsid
                    update, status_code = fax_func(query_params)
                    update_json = json.loads(update)

                    from_ = str(update_json["from"])
                    to = str(update_json["to"])
                    status = str(update_json["status"])
                    duration = str(update_json["duration"])

                    print ("| Status: " + status + " | | Duration: " + duration + "|", end='\r')

                    if status == "delivered":
                        print ("\nDelivered Successfully!\n")
                        return True
                    elif status == "busy":
                        print ("ERROR: The fax machine was busy.  Please try again.\n")
                        return False
                    elif status == "failed":
                        print ("ERROR: The fax failed to send.  Please try again.\n")
                        return False
                    elif status == "no-answer":
                        print ("ERROR: The fax machine did not answer. Please try again.\n")
                        return False
                    time.sleep(3)
            else:
                print ("Backgrounding...\n")


    def fax_delete(self, args):
        '''delete subcommand of fax'''
        args = is_env_var(args)  # Replace any env vars in the command string

        sid = args.id
        query_params = "/Faxes/" + sid
        if sid is not None:
            if not args.force:
                confirm = input("Remove FAX " + sid + "?  This cannot be undone! (Y/n): ")
            else:
                confirm = "y"

            if confirm.lower() == "yes" or confirm.lower() == "y":
                output, status_code = fax_func(query_params, "DELETE")
                valid = validate_http(status_code)
                if valid:
                    print("Success! FAX " + sid + " has been removed\n")
                else:
                    is_json = validate_json(output)
                    if is_json:
                        print_error_json_compatibility(output)
                    else:
                        status_code = str(status_code)
                        print(status_code + ": " + output + "\n")
            else:
                print("OK.  Cancelling...\n")
        else:
            print ("ERROR: Please enter a valid SignalWire ID\n")

    # Set default handlers for each sub command
    fax_parser_list.set_defaults(func=fax_list)
    fax_parser_send.set_defaults(func=fax_send)
    fax_parser_update.set_defaults(func=fax_update)
    fax_parser_delete.set_defaults(func=fax_delete)

    @cmd2.with_argparser(base_fax_parser)
    def do_fax(self, args: argparse.Namespace):
        '''List, Send, Update, Retrieve and Remove Faxes'''
        func = getattr(args, 'func', None)
        if func is not None:
            func(self, args)
        else:
            self.do_help('fax')


##
def main():
    MyPrompt().cmdloop()

if __name__ == '__main__':
    main()
