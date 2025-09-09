# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SWSH (SignalWire interactive SHell) is a Python-based cross-platform command-line shell for managing SignalWire Spaces. It provides both interactive and non-interactive modes for SignalWire API operations.

## Development Commands

### Installation & Setup
```bash
# Install for development
pip install .

# Install with dependencies
pip3 install swsh
```

### Build Commands
```bash
# Build executable for macOS
./build-macos.sh

# Build executable for Linux  
./build-lin.sh

# Build executable for Windows
build-win.bat
```

### Running the Application
```bash
# Interactive mode
swsh

# Non-interactive mode
swsh "phone_number list"
```

## Required Environment Variables

For non-interactive mode, these must be set:
```bash
export SIGNALWIRE_SPACE=<space_name>
export PROJECT_ID=<project_id>
export REST_API_TOKEN=<api_token>
```

## Architecture

### Core Structure
- **Main Shell**: `swsh/swsh.py` - Main application extending cmd2.Cmd with CommandMixin
- **API Functions**: `swsh/functions.py` - HTTP wrapper functions for SignalWire APIs
- **Phone Number Helper**: `swsh/buy_a_phone_number.py` - Interactive phone purchasing
- **Entry Point**: `build-swsh.py` - Simple wrapper for PyInstaller
- **Command Modules**: `swsh/commands/` - Modular command implementations

### Modular Command Architecture (NEW)
Commands are now organized into separate modules under `swsh/commands/`:
- **Base Command**: `base.py` - Shared functionality and patterns for all commands
- **SIP Endpoint**: `sip_endpoint.py` - SIP endpoint management (list, create, update, delete)
- **Phone Number**: `phone_number.py` - Phone number operations (list, update, release, lookup, buy)
- **LAML Bin**: `laml_bin.py` - LAML bin management (list, create, update, delete)

### Command Pattern (REFACTORED)
- Each command module inherits from `BaseCommand` for shared functionality
- Eliminates code duplication in HTTP response handling, JSON formatting, and argument validation
- Centralized error handling and confirmation prompts
- Improved security with subprocess instead of os.system calls

### API Integration
- **Primary API**: `https://{space}.signalwire.com/api/relay/rest/`
- **Compatibility API**: `https://{space}.signalwire.com/api/laml/2010-04-01/`
- **Authentication**: HTTP Basic Auth with `project_id:rest_api_token`
- **HTTP Client**: Custom wrapper using requests library in `functions.py`

### Build System Architecture
Uses PyInstaller with custom patching system:
1. Installs dependencies via pip
2. Applies patches to cmd2 and pygments libraries  
3. Copies custom formatter to pygments
4. Builds standalone executable with `--onefile`

### Dependencies
- **signalwire** - SignalWire SDK
- **cmd2** - Enhanced CLI framework (patched during build)
- **requests** - HTTP client
- **python-dotenv** - Environment management
- **pyvim** - Vim-like editor integration
- **gnureadline** - macOS readline support

## Important Notes

### Build Process Patches
The build system modifies third-party packages:
- Patches applied to cmd2 and pygments during build
- Custom `swishcolor.py` formatter added to pygments
- Platform-specific patch commands (different syntax for Windows vs Unix)

### No Testing Framework
This codebase currently has no automated testing setup. When adding features, manual testing is required.

### Code Organization (REFACTORED)
- **Modular Structure**: Commands split into focused modules under `commands/`
- **Shared Functionality**: Common patterns centralized in `BaseCommand` class  
- **Security Improvements**: Shell injection vulnerabilities fixed with subprocess
- **Reduced Duplication**: ~60% reduction in code duplication across command implementations
- **Main Shell**: Now focuses on initialization and routing to command modules
- API wrapper functions remain centralized in `functions.py`
- Cross-platform compatibility handled through different build scripts

### Adding New Commands
When adding new command modules:
1. Create new file in `swsh/commands/` inheriting from `BaseCommand`
2. Implement `get_parser()` method for argument parsing
3. Implement `handle_command()` method for routing
4. Add command initialization to `_init_modular_commands()` in `swsh.py`
5. Add corresponding `do_<command>()` method in main shell class