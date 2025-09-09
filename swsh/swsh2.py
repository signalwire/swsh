#!/usr/bin/env python3

import cmd2
import argparse
import json

from commands.base import BaseCommand
from commands.sip_endpoint import SipEndpointCommand



# import time
# import re
# import urllib.parse

# import subprocess
# from signalwire.rest import Client as signalwire_clinet

from functions import *

class MyPrompt(cmd2.Cmd):

    # TODO: Review pipes.  It seems like it could give system access to the shell.


    # TODO: Revist this.  Do these still make sense?
    # TODO: is the EDITOR still something that should be optional?
    global noninteractive_flag
    global swsh_version

    EDITOR = os.environ.get('EDITOR', 'pyvim')

    # TODO: No more entering the env crap.  It needs to be in a .env file or exported env vars
    signalwire_space, project_id, rest_api_token = get_environment()
    if signalwire_space == "" or signalwire_space is None \
        or project_id == "" or project_id is None \
            or rest_api_token == "" or rest_api_token is None:
                print("ERROR: SignalWire Space, Project ID, or Rest API Token is not set")
                sys.exit(1)

    def __init__(self):
        super().__init__(
            completekey='tab',
            persistent_history_file='~/.swsh_history'
        )

        self.hidden_commands.append('macro')
        self.hidden_commands.append('alias')
        self.hidden_commands.append('set')
        self.hidden_commands.append('exit')

        # Delete some built-in commands that we don't want access to
        del_list = ['shell', 'shortcuts', 'run_script', 'run_pyscript', 'edit', 'ipy', 'py'] # TODO: Add 'set' here once ready for build
        for command in del_list:
            delattr(cmd2.Cmd, f'do_{command}')

        self._init_modular_commands()

    


    ## Lots of stuff goes above this ##
    def _init_modular_commands(self):
        # Create command instances
        self.sip_endpoint_cmd = SipEndpointCommand(self)

        # Register command handlers
        self.sip_endpoint_parser = self.sip_endpoint_cmd.get_parser()
    
    def do_sip_endpoint(self, args):
        """List, Create, Update, Delete SIP Endpoint"""
        if hasattr(self, 'sip_endpoint_cmd'):
            try:
                parsed_args = self.sip_endpoint_parser.parse_args(args.split())
                self.sip_endpoint_cmd.handle_command(parsed_args)
            except SystemExit:
                pass
        else:
            print("SIP Endpoint command not initialized")





##
def main():
    MyPrompt().cmdloop()

if __name__ == '__main__':
    main()