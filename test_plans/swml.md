# SWML Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Fabric API
- Valid project/account with appropriate permissions
- Editor configured (EDITOR environment variable or pyvim available)

## Test Cases

### 1. List Commands
```bash
# TC-001: List all SWML scripts
swml list

# TC-002: List all SWML scripts in JSON format
swml list --json

# TC-003: List specific SWML script by ID
swml list --id <script_id>

# TC-004: List specific SWML script by ID in JSON format
swml list --id <script_id> --json

# TC-005: List non-existent SWML script by ID
swml list --id 00000000-0000-0000-0000-000000000000

# TC-006: List with invalid ID format
swml list --id "invalid-id"

# TC-007: List when no scripts exist
swml list
```

### 2. Create Commands
```bash
# TC-008: Create SWML script with name and inline contents
swml create --name "Test Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - play:
        url: "say:Hello"
    - hangup'

# TC-009: Create SWML script with name only (should open editor)
swml create --name "Editor Test Script"

# TC-010: Create SWML script with multi-word name
swml create --name Test Script With Spaces --contents 'version: 1.0.0
sections:
  main:
    - answer
    - hangup'

# TC-011: Create SWML script without name (should fail)
swml create --contents 'version: 1.0.0'

# TC-012: Create SWML script with empty contents
swml create --name "Empty Script" --contents ''

# TC-013: Create SWML script with complex SWML
swml create --name "Complex Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - play:
        url: "say:Welcome to the test"
    - record:
        stereo: true
        beep: true
    - hangup'

# TC-014: Create SWML script with special characters in name
swml create --name "Test Script (v1.0)" --contents 'version: 1.0.0
sections:
  main:
    - hangup'

# TC-015: Create SWML script with unicode characters in name
swml create --name "测试脚本" --contents 'version: 1.0.0
sections:
  main:
    - hangup'

# TC-016: Create SWML script with very long name
swml create --name "$(python3 -c "print('A' * 200)")" --contents 'version: 1.0.0
sections:
  main:
    - hangup'

# TC-017: Create SWML script with very long contents
swml create --name "Long Contents Script" --contents "$(python3 -c "print('version: 1.0.0\nsections:\n  main:\n    - answer\n' + '    - play:\n        url: \"say:Line ' + str(i) + '\"\n' for i in range(100))")"

# TC-018: Create SWML script with JSON format instead of YAML
swml create --name "JSON Format Script" --contents '{"version": "1.0.0", "sections": {"main": [{"answer": {}}]}}'

# TC-019: Create SWML script with invalid YAML
swml create --name "Invalid YAML Script" --contents 'this is not: valid: yaml:'

# TC-020: Create duplicate script name (verify behavior)
swml create --name "Duplicate Test" --contents 'version: 1.0.0
sections:
  main:
    - hangup'
swml create --name "Duplicate Test" --contents 'version: 1.0.0
sections:
  main:
    - hangup'
```

### 3. Update Commands
```bash
# TC-021: Update SWML script name
swml update --id <script_id> --name "Updated Script Name"

# TC-022: Update SWML script contents
swml update --id <script_id> --contents 'version: 1.0.0
sections:
  main:
    - answer
    - play:
        url: "say:Updated content"
    - hangup'

# TC-023: Update SWML script name and contents
swml update --id <script_id> --name "Fully Updated Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - hangup'

# TC-024: Update SWML script without ID (should fail)
swml update --name "New Name"

# TC-025: Update SWML script without any parameters (should open editor)
swml update --id <script_id>

# TC-026: Update SWML script with non-existent ID (should fail)
swml update --id 00000000-0000-0000-0000-000000000000 --name "Test"

# TC-027: Update SWML script with invalid ID format (should fail)
swml update --id "invalid-id" --name "Test"

# TC-028: Update SWML script with multi-word name
swml update --id <script_id> --name Updated Multi Word Name

# TC-029: Update SWML script to empty name
swml update --id <script_id> --name ""

# TC-030: Update SWML script to empty contents
swml update --id <script_id> --contents ""

# TC-031: Update SWML script with special characters in name
swml update --id <script_id> --name "Updated (v2.0) [Final]"
```

### 4. Delete Commands
```bash
# TC-032: Delete SWML script with confirmation prompt
swml delete --id <script_id>

# TC-033: Delete SWML script with force flag (no confirmation)
swml delete --id <script_id> --force

# TC-034: Delete SWML script without ID (should fail)
swml delete

# TC-035: Delete SWML script with non-existent ID (should fail)
swml delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-036: Delete SWML script with invalid ID format (should fail)
swml delete --id "invalid-id" --force

# TC-037: Cancel delete operation (choose 'no' when prompted)
swml delete --id <script_id>

# TC-038: Delete with case variations in confirmation
swml delete --id <script_id>  # Test 'Y', 'y', 'yes', 'Yes'

# TC-039: Delete with invalid confirmation responses
swml delete --id <script_id>  # Test 'maybe', '1', 'sure'
```

### 5. Addresses Commands
```bash
# TC-040: List addresses for SWML script
swml addresses --id <script_id>

# TC-041: List addresses for SWML script in JSON format
swml addresses --id <script_id> --json

# TC-042: List addresses without script ID (should fail)
swml addresses

# TC-043: List addresses for non-existent script
swml addresses --id 00000000-0000-0000-0000-000000000000

# TC-044: List addresses for script with no addresses
swml addresses --id <script_with_no_addresses>

# TC-045: List addresses with invalid ID format
swml addresses --id "invalid-id"
```

### 6. Edge Cases & Error Handling
```bash
# TC-046: Invalid command (should show help)
swml invalid_command

# TC-047: No subcommand (should show help)
swml

# TC-048: Help command
swml --help

# TC-049: Help for specific subcommands
swml list --help
swml create --help
swml update --help
swml delete --help
swml addresses --help

# TC-050: SWML script ID boundary testing
swml list --id "$(python3 -c "print('a' * 100)")"

# TC-051: Contents with escape sequences
swml create --name "Escape Test" --contents 'version: 1.0.0
sections:
  main:
    - play:
        url: "say:Tab\tNewline\nQuote\"End"'

# TC-052: Contents with only whitespace
swml create --name "Whitespace Script" --contents "   "

# TC-053: Name with leading/trailing whitespace
swml create --name "  Trimmed Name  " --contents 'version: 1.0.0
sections:
  main:
    - hangup'

# TC-054: Very long script ID
swml list --id "$(python3 -c "print('0' * 500)")"

# TC-055: Script with nested SWML sections
swml create --name "Nested Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - execute:
        dest: /subroutine
  subroutine:
    - play:
        url: "say:Subroutine executed"
    - return'

# TC-056: Script with AI agent configuration
swml create --name "AI Agent Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - ai:
        prompt:
          text: "You are a helpful assistant"
        post_prompt_url: "https://example.com/callback"
    - hangup'
```

### 7. Integration Tests
```bash
# TC-057: Full SWML script lifecycle
# Create -> List -> Update -> List -> Delete
swml create --name "Lifecycle Test Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - hangup'
swml list --json  # Find the new script ID
swml list --id <created_id>
swml update --id <created_id> --name "Updated Lifecycle Script"
swml list --id <created_id>
swml delete --id <created_id> --force

# TC-058: Create script and check addresses
swml create --name "Address Test Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - hangup'
swml addresses --id <created_id>
swml delete --id <created_id> --force

# TC-059: Bulk script creation and cleanup
swml create --name "Bulk Test 1" --contents 'version: 1.0.0
sections:
  main:
    - hangup'
swml create --name "Bulk Test 2" --contents 'version: 1.0.0
sections:
  main:
    - hangup'
swml create --name "Bulk Test 3" --contents 'version: 1.0.0
sections:
  main:
    - hangup'
swml list --json  # Verify all created
# Cleanup
swml delete --id <bulk1_id> --force
swml delete --id <bulk2_id> --force
swml delete --id <bulk3_id> --force

# TC-060: Update script through editor
swml update --id <script_id>  # Opens editor, make changes, save
swml list --id <script_id>  # Verify changes

# TC-061: Create script through editor
swml create --name "Editor Created Script"  # Opens editor, add content, save
swml list --json  # Verify creation

# TC-062: Cancel editor creation
swml create --name "Cancelled Script"  # Opens editor, don't change, save (should cancel)

# TC-063: Cancel editor update
swml update --id <script_id>  # Opens editor, don't change, save (should cancel)

# TC-064: Verify JSON output structure
swml list --json | jq '.'
swml list --id <script_id> --json | jq '.'
swml addresses --id <script_id> --json | jq '.'

# TC-065: Create script with phone integration SWML
swml create --name "Phone Integration Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - connect:
        to: "+15551234567"
        from: "+15559876543"
    - hangup'

# TC-066: Create script with recording SWML
swml create --name "Recording Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - record:
        stereo: true
        format: "mp3"
        direction: "both"
        terminators: "#"
    - hangup'

# TC-067: Create script with TTS SWML
swml create --name "TTS Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - play:
        url: "say:Hello, welcome to SignalWire"
        say_voice: "en-US-Neural2-J"
    - hangup'

# TC-068: Test script with variables
swml create --name "Variables Script" --contents 'version: 1.0.0
sections:
  main:
    - answer
    - set:
        name: "greeting"
        value: "Hello World"
    - play:
        url: "say:%{variables.greeting}"
    - hangup'

# TC-069: Create and immediately delete
swml create --name "Quick Delete Test" --contents 'version: 1.0.0
sections:
  main:
    - hangup'
swml delete --id <just_created_id> --force

# TC-070: Update non-existent script while another exists
swml create --name "Existing Script" --contents 'version: 1.0.0
sections:
  main:
    - hangup'
swml update --id 00000000-0000-0000-0000-000000000000 --name "Should Fail"
swml delete --id <existing_id> --force
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, 422, etc.)
- **Data Validation**: Verify script data matches input (name, contents, id)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **Editor Behavior**: Verify editor opens/closes correctly and changes are captured
- **JSON Structure**: For --json output, verify proper JSON formatting

## Test Environment Setup
```bash
# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
test -n "$REST_API_TOKEN" && echo "REST_API_TOKEN is set"

# Verify editor is configured
echo $EDITOR

# Save original scripts for reference
swml list --json > original_scripts.json

# Get available scripts for testing
swml list --json | jq -r '.[] | .id'

# After testing, cleanup test scripts
# Delete only what this plan created, one id at a time (never by a name or number pattern):
swml delete --id <id> --force

# Cleanup bulk test scripts
# Delete only what this plan created, one id at a time (never by a name or number pattern):
swml delete --id <id> --force
```

## Notes
- SWML Scripts use YAML format for content (JSON is also supported)
- The Fabric API uses JSON payloads (not form-encoded like Compatibility API)
- Script IDs are UUIDs in the format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
- Contents can include various SWML actions: answer, hangup, play, record, connect, ai, etc.
- Addresses are phone numbers or SIP endpoints associated with a script
- Editor will use $EDITOR environment variable or fall back to pyvim
- Creating a script without --contents opens the editor with a template
- Updating a script without --name or --contents opens the editor with current contents
- Delete operations require confirmation unless --force flag is used
- Version field in SWML should be "1.0.0"
- SWML supports variables, sections, and control flow

## API Endpoint Reference
- **Base URL**: `api/fabric/resources/swml_scripts`
- **List Scripts**: GET `/resources/swml_scripts`
- **Get Script**: GET `/resources/swml_scripts/:id`
- **Create Script**: POST `/resources/swml_scripts`
- **Update Script**: PUT `/resources/swml_scripts/:id`
- **Delete Script**: DELETE `/resources/swml_scripts/:id`
- **List Addresses**: GET `/resources/swml_scripts/:id/addresses`
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/json (Fabric API)
- **Delete Response**: 204 No Content on successful deletion

## Command Reference
```
swml list [-i ID] [-j]
swml create -n NAME [--contents CONTENTS]
swml update -i ID [-n NAME] [--contents CONTENTS]
swml delete -i ID [-f]
swml addresses -i ID [-j]
```
