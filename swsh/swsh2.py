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
import sys
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

    # Shell configuration
    EDITOR = os.environ.get('EDITOR', 'pyvim')
    swsh_version = "2.0"
    noninteractive_flag = False
    output_format = "formatted"  # Options: json, formatted
    prompt = 'swsh> '
    intro = r'''
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

        # Load and apply persistent configuration
        self._apply_config(self._load_config())

        self._init_modular_commands()

    


    def _init_modular_commands(self):
        """Dynamically initialize all command instances"""
        for command_name, command_class in _command_classes.items():
            # Create command instance and store as attribute
            cmd_instance = command_class(self)
            setattr(self, f"{command_name}_cmd", cmd_instance)

    def default(self, line):
        """Handle unknown commands - check for shell variable assignment"""
        # Check if this is a shell variable assignment (var=value)
        if "=" in line.command:
            set_shell_env(line.command)
            return

        # If not a variable assignment, show error
        self.poutput(f"Unknown command: {line.command}")
        self.poutput("Type 'help' for a list of available commands.")

    def do_clear(self, args):
        """Clear the screen"""
        import subprocess
        try:
            subprocess.run(['clear'], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback for systems where 'clear' command is not available (Windows, etc.)
            print('\033[H\033[J', end='')

    def do_echo(self, args):
        """Echo text or shell variable values"""
        if not args:
            print("")
            return

        parts = args.split()
        output_parts = []

        for part in parts:
            if part.startswith("$"):
                # This is a shell variable reference
                var_name = part.strip("$")
                try:
                    var_value = get_shell_env(var_name)
                    if var_value:
                        output_parts.append(var_value)
                    else:
                        output_parts.append("")  # Variable not set
                except (KeyError, TypeError):
                    output_parts.append("")  # Variable not found
            else:
                output_parts.append(part)

        print(' '.join(output_parts))

    def do_env(self, args):
        """Display all shell environment variables"""
        get_shell_env_all()

    def do_exit(self, args):
        """Exit the application"""
        if not self.noninteractive_flag:
            print("Thanks for using SignalWire\n")
        return True

    def help_exit(self):
        print("Exit the application. Shorthand: Ctrl-D.")

    # Alias quit to exit
    do_quit = do_exit
    help_quit = help_exit

    def do_whoami(self, args):
        """Display current SignalWire space, project, and token (masked)"""
        signalwire_space, project_id, rest_api_token = get_environment()

        # Mask the token, showing only last 4 characters
        if rest_api_token and len(rest_api_token) > 4:
            masked_token = "*" * (len(rest_api_token) - 4) + rest_api_token[-4:]
        else:
            masked_token = "****"

        print(f"Space:      {signalwire_space}.signalwire.com")
        print(f"Project ID: {project_id}")
        print(f"Token:      {masked_token}")

    def do_version(self, args):
        """Display the swsh version"""
        print(f"swsh version {self.swsh_version}")

    # Output format command with subcommands
    output_parser = cmd2.Cmd2ArgumentParser()
    output_subparsers = output_parser.add_subparsers(title='OUTPUT FORMAT', help='output format help')

    # output show - display current format
    output_show_parser = output_subparsers.add_parser('show', help='Show current output format')
    output_show_parser.set_defaults(output_action='show')

    # output json - set to JSON format
    output_json_parser = output_subparsers.add_parser('json', help='Set output format to JSON')
    output_json_parser.set_defaults(output_action='json')

    # output formatted - set to formatted (default)
    output_formatted_parser = output_subparsers.add_parser('formatted', help='Set output format to formatted (default)')
    output_formatted_parser.set_defaults(output_action='formatted')

    # output compact - set to compact format
    output_compact_parser = output_subparsers.add_parser('compact', help='Set output format to compact')
    output_compact_parser.set_defaults(output_action='compact')

    @cmd2.with_argparser(output_parser)
    def do_output(self, args):
        """Set or display the default output format for commands"""
        action = getattr(args, 'output_action', None)

        if action == 'show' or action is None:
            print(f"Current output format: {self.output_format}")
        elif action in ['json', 'formatted', 'compact']:
            self.output_format = action
            print(f"Output format set to: {self.output_format}")

    # Config command with subcommands
    config_parser = cmd2.Cmd2ArgumentParser()
    config_subparsers = config_parser.add_subparsers(title='CONFIG', help='config help')

    # config show - display all configuration
    config_show_parser = config_subparsers.add_parser('show', help='Show all configuration settings')
    config_show_parser.set_defaults(config_action='show')

    # config get - get a specific configuration value
    config_get_parser = config_subparsers.add_parser('get', help='Get a specific configuration value')
    config_get_parser.add_argument('key', help='Configuration key to retrieve')
    config_get_parser.set_defaults(config_action='get')

    # config set - set a configuration value
    config_set_parser = config_subparsers.add_parser('set', help='Set a configuration value')
    config_set_parser.add_argument('key', help='Configuration key to set')
    config_set_parser.add_argument('value', help='Value to set')
    config_set_parser.set_defaults(config_action='set')

    # config reset - reset to defaults
    config_reset_parser = config_subparsers.add_parser('reset', help='Reset configuration to defaults')
    config_reset_parser.set_defaults(config_action='reset')

    # Valid configuration keys and their defaults
    CONFIG_DEFAULTS = {
        'output_format': 'formatted',
        'editor': 'pyvim',
        'history_file': '~/.swsh_history',
    }

    def _get_config_path(self):
        """Get the path to the config file"""
        config_dir = os.path.expanduser('~/.swsh')
        return os.path.join(config_dir, 'config.json')

    def _load_config(self):
        """Load configuration from file"""
        config_path = self._get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return dict(self.CONFIG_DEFAULTS)
        return dict(self.CONFIG_DEFAULTS)

    def _save_config(self, config):
        """Save configuration to file"""
        config_path = self._get_config_path()
        config_dir = os.path.dirname(config_path)

        # Create config directory if it doesn't exist
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

    def _apply_config(self, config):
        """Apply configuration to shell instance"""
        if 'output_format' in config:
            self.output_format = config['output_format']
        if 'editor' in config:
            self.EDITOR = config['editor']

    @cmd2.with_argparser(config_parser)
    def do_config(self, args):
        """View and set persistent configuration options"""
        action = getattr(args, 'config_action', None)

        if action == 'show' or action is None:
            config = self._load_config()
            print("Current configuration:")
            for key, value in config.items():
                print(f"  {key}: {value}")

        elif action == 'get':
            config = self._load_config()
            key = args.key
            if key in config:
                print(f"{key}: {config[key]}")
            elif key in self.CONFIG_DEFAULTS:
                print(f"{key}: {self.CONFIG_DEFAULTS[key]} (default)")
            else:
                print(f"Unknown configuration key: {key}")
                print(f"Valid keys: {', '.join(self.CONFIG_DEFAULTS.keys())}")

        elif action == 'set':
            key = args.key
            value = args.value

            if key not in self.CONFIG_DEFAULTS:
                print(f"Unknown configuration key: {key}")
                print(f"Valid keys: {', '.join(self.CONFIG_DEFAULTS.keys())}")
                return

            # Validate output_format values
            if key == 'output_format' and value not in ['json', 'formatted', 'compact']:
                print(f"Invalid value for output_format. Must be: json, formatted, or compact")
                return

            config = self._load_config()
            config[key] = value
            self._save_config(config)
            self._apply_config(config)
            print(f"Configuration updated: {key} = {value}")

        elif action == 'reset':
            self._save_config(dict(self.CONFIG_DEFAULTS))
            self._apply_config(self.CONFIG_DEFAULTS)
            print("Configuration reset to defaults")





# Add dynamically created methods to the class
for method_name, method in _command_methods.items():
    setattr(MyPrompt, method_name, method)

##
def main():
    # Handle CLI arguments before starting the shell
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        # Handle version flag
        if arg in ['-v', '--version']:
            print(f"swsh version {MyPrompt.swsh_version}")
            sys.exit(0)

        # Handle help flag
        elif arg in ['-h', '--help']:
            print('''SWSH Help Menu:
================
SignalWire interactive SHell
Cross platform command line utility and shell for administering a Space or Spaces in SignalWire

Usage:
  swsh                     Start interactive shell
  swsh "command"           Execute a single command and exit
  swsh -v | --version      Show version
  swsh -h | --help         Show this help menu

Environment Variables (required):
  SIGNALWIRE_SPACE         Your SignalWire space name
  PROJECT_ID               Your SignalWire project ID
  REST_API_TOKEN           Your SignalWire REST API token

Examples:
  swsh "phone_number list"
  swsh "sip_endpoint list --json"
''')
            sys.exit(0)

        # Non-interactive mode: execute command and exit
        else:
            # Group all arguments as a single command
            command = ' '.join(sys.argv[1:])
            sys.argv = [sys.argv[0], command, 'quit']

            # Create shell instance with non-interactive settings
            shell = MyPrompt()
            shell.noninteractive_flag = True
            shell.intro = None  # Suppress intro banner in non-interactive mode
            shell.cmdloop()
            return

    # Interactive mode
    MyPrompt().cmdloop()

if __name__ == '__main__':
    main()