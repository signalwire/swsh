#!/usr/bin/env python3

import cmd2
import argparse
import json

from commands.base import BaseCommand



# import time
# import re
# import urllib.parse

# import subprocess
# from signalwire.rest import Client as signalwire_clinet

from functions import *

# Dynamically load all command modules and create parsers
import os
import importlib
from pathlib import Path

def load_command_modules():
    """Dynamically load all command modules and create parsers"""
    commands_dir = Path(__file__).parent / "commands"
    command_parsers = {}
    command_classes = {}
    
    # Get all Python files in commands directory (except __init__ and base)
    for file_path in commands_dir.glob("*.py"):
        if file_path.name in ["__init__.py", "base.py"]:
            continue
            
        module_name = file_path.stem
        command_name = module_name
        
        try:
            # Import the module
            module = importlib.import_module(f"commands.{module_name}")
            
            # Find the command class (assumes pattern: SipEndpointCommand from sip_endpoint.py)
            class_name = ''.join(word.capitalize() for word in module_name.split('_')) + 'Command'
            
            if hasattr(module, class_name):
                command_class = getattr(module, class_name)
                # Create parser without shell instance
                parser = command_class(None).get_parser()
                
                command_parsers[f"{command_name}_parser"] = parser
                command_classes[command_name] = command_class
                
        except Exception as e:
            print(f"Warning: Could not load command module {module_name}: {e}")
            
    return command_parsers, command_classes

# Load all command modules dynamically
_parsers, _command_classes = load_command_modules()

# Create module-level parser variables for decorators
for parser_name, parser in _parsers.items():
    globals()[parser_name] = parser

# Dynamically create command methods at module level
def _create_command_methods():
    """Create command methods dynamically"""
    methods = {}
    
    for command_name in _command_classes.keys():
        parser_name = f"{command_name}_parser"
        if parser_name in globals():
            parser = globals()[parser_name]
            
            # Create the method function with closure
            def make_method(cmd_name):
                def command_method(self, args):
                    cmd_attr = f"{cmd_name}_cmd"
                    if hasattr(self, cmd_attr):
                        getattr(self, cmd_attr).handle_command(args)
                    else:
                        print(f"{cmd_name.replace('_', ' ').title()} command not initialized")
                
                # Set proper attributes
                command_method.__name__ = f"do_{cmd_name}"
                command_method.__doc__ = f"{cmd_name.replace('_', ' ').title()} command"
                command_method.__qualname__ = f"MyPrompt.do_{cmd_name}"
                
                # Apply decorator
                return cmd2.with_argparser(parser)(command_method)
            
            methods[f"do_{command_name}"] = make_method(command_name)
    
    return methods

# Create all command methods
_command_methods = _create_command_methods()

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
        """Dynamically initialize all command instances"""
        for command_name, command_class in _command_classes.items():
            # Create command instance and store as attribute
            cmd_instance = command_class(self)
            setattr(self, f"{command_name}_cmd", cmd_instance)

    # COMMANDS will be added dynamically below
    pass





# Add dynamically created methods to the class
for method_name, method in _command_methods.items():
    setattr(MyPrompt, method_name, method)

##
def main():
    MyPrompt().cmdloop()

if __name__ == '__main__':
    main()