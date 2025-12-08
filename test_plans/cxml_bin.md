# cXML Bin Command Test Plan

## Overview
This test plan covers both `cxml_bin` (primary command) and `laml_bin` (backwards compatibility alias). Both commands provide identical functionality with different naming conventions in help text.

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Compatibility API
- Valid project/account with Voice, Messaging, or Fax scope permissions
- Text editor available (pyvim or $EDITOR)
- Ability to create and manage cXML/LaML bins

## Test Cases

### 1. List Commands
```bash
# TC-001: List all cXML bins (detailed format - DEFAULT)
cxml_bin list

# TC-002: List cXML bins in JSON format
cxml_bin list --json

# TC-003: List specific cXML bin by ID
cxml_bin list --id <bin_sid>

# TC-004: List cXML bin by name
cxml_bin list --name "Test Bin"

# TC-005: List cXML bin by multi-word name
cxml_bin list --name "My Test Bin"

# TC-006: List non-existent cXML bin by ID
cxml_bin list --id nonexistent-123-456

# TC-007: List with invalid bin ID format
cxml_bin list --id invalid_id_format

# TC-008: List when no bins exist (new project)
cxml_bin list

# TC-009: List with very long bin ID
cxml_bin list --id "$(python3 -c "print('a'*100)")"

# TC-010: List with special characters in ID
cxml_bin list --id "test@bin#id"

# TC-011: List by name with special characters
cxml_bin list --name "Test-Bin_2023"

# TC-012: List by name with Unicode characters
cxml_bin list --name "测试"

# TC-013: List by partial name match
cxml_bin list --name "Test"

# TC-014: List by name that doesn't exist
cxml_bin list --name "NonExistentBinName12345"
```

### 2. Create Commands
```bash
# TC-015: Create cXML bin with name only (opens editor)
cxml_bin create --name "Editor Test Bin"

# TC-016: Create cXML bin with name and inline contents
cxml_bin create --name "Inline Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Hello</Say></Response>'

# TC-017: Create cXML bin with multi-word name
cxml_bin create --name "Multi Word Bin Name"

# TC-018: Create cXML bin with complex XML contents
cxml_bin create --name "Complex Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Dial timeout="30"><Sip>sip:user@domain.com</Sip></Dial></Response>'

# TC-019: Create cXML bin with Gather verb
cxml_bin create --name "Gather Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Gather input="dtmf" numDigits="1"><Say>Press 1 to continue</Say></Gather></Response>'

# TC-020: Create cXML bin with Record verb
cxml_bin create --name "Record Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Please leave a message</Say><Record maxLength="120" finishOnKey="#"/></Response>'

# TC-021: Create cXML bin with Redirect verb
cxml_bin create --name "Redirect Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Redirect>https://example.com/next</Redirect></Response>'

# TC-022: Create cXML bin with Message verb
cxml_bin create --name "Message Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Message to="+15551234567" from="+15559876543">Hello from SignalWire</Message></Response>'

# TC-023: Create cXML bin with Conference verb
cxml_bin create --name "Conference Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Dial><Conference>MyRoom</Conference></Dial></Response>'

# TC-024: Create cXML bin with Queue verb
cxml_bin create --name "Queue Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Enqueue>support</Enqueue></Response>'

# TC-025: Create cXML bin with special characters in name
cxml_bin create --name "Test-Bin_2023" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Test</Say></Response>'

# TC-026: Create cXML bin with Unicode characters in name
cxml_bin create --name "测试应用" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Test</Say></Response>'

# TC-027: Create cXML bin without name (should fail)
cxml_bin create --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Hello</Say></Response>'

# TC-028: Create cXML bin with empty name (should fail)
cxml_bin create --name ""

# TC-029: Create cXML bin with only whitespace name (should fail)
cxml_bin create --name "   "

# TC-030: Create cXML bin and cancel in editor (quit without changes)
cxml_bin create --name "Cancel Test"
# Quit editor without making changes - should cancel creation

# TC-031: Create cXML bin with malformed XML
cxml_bin create --name "Malformed XML" --contents '<Response><Say>Missing closing tag'

# TC-032: Create cXML bin with empty contents
cxml_bin create --name "Empty Contents" --contents ""

# TC-033: Create cXML bin with very long name
cxml_bin create --name "$(python3 -c "print('a'*100)")"

# TC-034: Create cXML bin with very long contents
cxml_bin create --name "Long Contents" --contents "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Say>$(python3 -c "print('Hello ' * 500)")</Say></Response>"

# TC-035: Create cXML bin with XML containing special characters
cxml_bin create --name "Special Chars" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Test &amp; verify &lt;special&gt; chars</Say></Response>'

# TC-036: Create cXML bin with template variables
cxml_bin create --name "Template Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Hello {{From}}</Say></Response>'
```

### 3. Update Commands
```bash
# TC-037: Update cXML bin name by ID
cxml_bin update --id <bin_sid> --name "Updated Bin Name"

# TC-038: Update cXML bin contents by ID (opens editor)
cxml_bin update --id <bin_sid>

# TC-039: Update cXML bin contents inline
cxml_bin update --id <bin_sid> --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Updated content</Say></Response>'

# TC-040: Update cXML bin name and contents together
cxml_bin update --id <bin_sid> --name "Fully Updated Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Both updated</Say></Response>'

# TC-041: Update cXML bin with multi-word name
cxml_bin update --id <bin_sid> --name "Updated Multi Word Name"

# TC-042: Update cXML bin with special characters in name
cxml_bin update --id <bin_sid> --name "Updated-Bin_2023"

# TC-043: Update cXML bin with Unicode characters in name
cxml_bin update --id <bin_sid> --name "更新的应用"

# TC-044: Update cXML bin and cancel in editor (quit without changes)
cxml_bin update --id <bin_sid>
# Quit editor without making changes - should cancel update

# TC-045: Update cXML bin without ID (should fail)
cxml_bin update --name "Some Name"

# TC-046: Update cXML bin with invalid ID (should fail)
cxml_bin update --id invalid-123-456 --name "Test"

# TC-047: Update cXML bin with non-existent ID (should fail)
cxml_bin update --id 00000000-0000-0000-0000-000000000000 --name "Test"

# TC-048: Update cXML bin with empty name (should fail)
cxml_bin update --id <bin_sid> --name ""

# TC-049: Update cXML bin with only whitespace name (should fail)
cxml_bin update --id <bin_sid> --name "   "

# TC-050: Update cXML bin with malformed XML
cxml_bin update --id <bin_sid> --contents '<Response><Say>Missing closing tag'

# TC-051: Update cXML bin back to original values
cxml_bin update --id <bin_sid> --name "Original Name" --contents '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

# TC-052: Update cXML bin with complex nested XML
cxml_bin update --id <bin_sid> --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Gather input="dtmf" action="/process" numDigits="4"><Say>Enter your PIN</Say></Gather><Say>We did not receive any input</Say></Response>'
```

### 4. Delete Commands
```bash
# TC-053: Delete cXML bin with confirmation prompt
cxml_bin delete --id <bin_sid>

# TC-054: Delete cXML bin with force flag (no confirmation)
cxml_bin delete --id <bin_sid> --force

# TC-055: Delete cXML bin without ID (should fail)
cxml_bin delete

# TC-056: Delete cXML bin with invalid ID (should fail)
cxml_bin delete --id invalid-123-456 --force

# TC-057: Delete cXML bin with non-existent ID (should fail)
cxml_bin delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-058: Cancel delete operation (choose 'no' when prompted)
cxml_bin delete --id <bin_sid>

# TC-059: Delete with case variations in confirmation
cxml_bin delete --id <bin_sid>  # Test 'Y', 'y', 'yes', 'Yes'

# TC-060: Delete with invalid confirmation responses
cxml_bin delete --id <bin_sid>  # Test 'maybe', '1', 'sure'

# TC-061: Delete cXML bin currently assigned to phone number (should succeed but may impact service)
cxml_bin delete --id <active_bin_sid> --force
```

### 5. laml_bin Alias Commands
```bash
# TC-062: List all LaML bins using alias
laml_bin list

# TC-063: List LaML bins in JSON format using alias
laml_bin list --json

# TC-064: List specific LaML bin by ID using alias
laml_bin list --id <bin_sid>

# TC-065: Create LaML bin using alias
laml_bin create --name "Alias Test Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Alias test</Say></Response>'

# TC-066: Update LaML bin using alias
laml_bin update --id <bin_sid> --name "Alias Updated Bin"

# TC-067: Delete LaML bin using alias
laml_bin delete --id <bin_sid> --force

# TC-068: Verify laml_bin help shows 'LAML BIN' branding
laml_bin --help
laml_bin list --help
laml_bin create --help
laml_bin update --help
laml_bin delete --help

# TC-069: Verify cxml_bin help shows 'CXML BIN' branding
cxml_bin --help
cxml_bin list --help
cxml_bin create --help
cxml_bin update --help
cxml_bin delete --help

# TC-070: Verify both commands access same bins
cxml_bin create --name "Cross Command Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Cross test</Say></Response>'
laml_bin list --name "Cross Command Test"
laml_bin delete --id <bin_sid> --force
cxml_bin list --name "Cross Command Test"  # Should return empty
```

### 6. Edge Cases & Error Handling
```bash
# TC-071: Invalid command (should show help)
cxml_bin invalid_command

# TC-072: No subcommand (should show help)
cxml_bin

# TC-073: Help command
cxml_bin --help

# TC-074: Help for specific subcommands
cxml_bin create --help
cxml_bin update --help
cxml_bin list --help
cxml_bin delete --help

# TC-075: cXML bin name with newlines
cxml_bin create --name $'Test\nBin'

# TC-076: cXML bin name with tabs
cxml_bin create --name $'Test\tBin'

# TC-077: Multiple concurrent create operations
cxml_bin create --name "Concurrent1" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>1</Say></Response>' &
cxml_bin create --name "Concurrent2" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>2</Say></Response>' &
wait

# TC-078: URL encoding edge cases in name
cxml_bin create --name "Test%20Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Test</Say></Response>'
cxml_bin create --name "Test+Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Test</Say></Response>'
cxml_bin create --name "Test&Bin" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Test</Say></Response>'

# TC-079: Case sensitivity tests for names
cxml_bin create --name "test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>lower</Say></Response>'
cxml_bin create --name "Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>title</Say></Response>'
cxml_bin create --name "TEST" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>upper</Say></Response>'

# TC-080: Special API characters in name
cxml_bin create --name "Test/Bin\\Path" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Test</Say></Response>'
cxml_bin create --name 'Test"Bin"Name' --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Test</Say></Response>'
cxml_bin create --name "Test'Bin'Name" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Test</Say></Response>'

# TC-081: XML with CDATA sections
cxml_bin create --name "CDATA Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say><![CDATA[Special <characters> & more]]></Say></Response>'

# TC-082: XML with comments
cxml_bin create --name "Comment Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><!-- This is a comment --><Say>Hello</Say></Response>'

# TC-083: XML with processing instructions
cxml_bin create --name "PI Test" --contents '<?xml version="1.0" encoding="UTF-8"?><?custom instruction?><Response><Say>Hello</Say></Response>'

# TC-084: Editor environment variable test
EDITOR=vim cxml_bin create --name "Vim Editor Test"
EDITOR=nano cxml_bin create --name "Nano Editor Test"

# TC-085: Non-existent editor
EDITOR=nonexistent_editor cxml_bin create --name "Bad Editor Test"
```

### 7. Integration Tests
```bash
# TC-086: Full cXML bin lifecycle
# Create -> List (verify) -> Update -> List (verify changes) -> Delete
cxml_bin create --name "Lifecycle Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Original</Say></Response>'
cxml_bin list --name "Lifecycle Test"
cxml_bin update --id <new_bin_sid> --name "Updated Lifecycle Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Updated</Say></Response>'
cxml_bin list --id <new_bin_sid>
cxml_bin delete --id <new_bin_sid> --force

# TC-087: Create and verify in different output formats
cxml_bin create --name "Format Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Format</Say></Response>'
cxml_bin list --id <new_bin_sid>
cxml_bin list --id <new_bin_sid> --json

# TC-088: Update and verify changes persist
cxml_bin update --id <bin_sid> --name "Persistence Test"
cxml_bin list --id <bin_sid>
cxml_bin list --id <bin_sid> --json

# TC-089: Multiple operations on same cXML bin
cxml_bin create --name "Multi Op Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Initial</Say></Response>'
cxml_bin update --id <new_bin_sid> --name "Multi Op Test Updated"
cxml_bin update --id <new_bin_sid> --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Second update</Say></Response>'
cxml_bin update --id <new_bin_sid> --name "Multi Op Test Final" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Final</Say></Response>'
cxml_bin list --id <new_bin_sid>

# TC-090: Test all output formatting consistency
cxml_bin list  # Detailed format
cxml_bin list --json  # JSON format
cxml_bin list --id <bin_sid>  # Single bin detailed
cxml_bin list --id <bin_sid> --json  # Single bin JSON

# TC-091: Bulk operations testing
cxml_bin create --name "Bulk Test 1" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Bulk 1</Say></Response>'
cxml_bin create --name "Bulk Test 2" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Bulk 2</Say></Response>'
cxml_bin create --name "Bulk Test 3" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Bulk 3</Say></Response>'
cxml_bin list --json  # Verify all created
cxml_bin delete --id <bulk1_sid> --force
cxml_bin delete --id <bulk2_sid> --force
cxml_bin delete --id <bulk3_sid> --force

# TC-092: Cross-command compatibility (cxml_bin and laml_bin)
cxml_bin create --name "Cross Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Cross</Say></Response>'
laml_bin list --name "Cross Test"  # Should find it
laml_bin update --id <bin_sid> --name "Cross Test Updated"
cxml_bin list --name "Cross Test Updated"  # Should find it
cxml_bin delete --id <bin_sid> --force
laml_bin list --name "Cross Test Updated"  # Should not find it

# TC-093: Verify request_url is generated correctly
cxml_bin create --name "URL Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>URL</Say></Response>'
cxml_bin list --id <new_bin_sid> --json | jq '.request_url'  # Should show valid LaML bin URL

# TC-094: Test bin with all common cXML verbs
cxml_bin create --name "All Verbs Test" --contents '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Welcome</Say><Pause length="1"/><Play>https://example.com/audio.mp3</Play><Gather input="dtmf speech" timeout="5"><Say>Press or say a number</Say></Gather></Response>'
cxml_bin list --id <new_bin_sid>
cxml_bin delete --id <new_bin_sid> --force
```

### 8. Editor Integration Tests
```bash
# TC-095: Create bin - make changes in editor - verify saved
cxml_bin create --name "Editor Save Test"
# In editor: Add <Say>Editor content</Say> and save
cxml_bin list --name "Editor Save Test"  # Verify contents

# TC-096: Create bin - quit editor without changes - verify cancelled
cxml_bin create --name "Editor Cancel Test"
# In editor: Quit without saving
# Should output: "cXML Bin creation cancelled"
cxml_bin list --name "Editor Cancel Test"  # Should not exist

# TC-097: Update bin - make changes in editor - verify saved
cxml_bin update --id <bin_sid>
# In editor: Modify content and save
cxml_bin list --id <bin_sid>  # Verify updated contents

# TC-098: Update bin - quit editor without changes - verify cancelled
cxml_bin update --id <bin_sid>
# In editor: Quit without saving
# Should output: "cXML Bin update cancelled"

# TC-099: Update bin with only name - should not open editor
cxml_bin update --id <bin_sid> --name "Name Only Update"
# Should update immediately without opening editor
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, etc.)
- **Data Validation**: Verify bin data matches input (name, contents, sid, request_url)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **Editor Behavior**: For create/update without inline contents, verify editor opens and changes are detected

## Test Environment Setup
```bash
# Save original cXML bins for reference
cxml_bin list --json > original_cxml_bins.json

# Get available cXML bins for testing
cxml_bin list --json | jq -r '.[].sid'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# Check editor setting
echo $EDITOR

# After testing, clean up test cXML bins
cxml_bin list --json | jq -r '.[] | select(.name | test("^Test|^Lifecycle|^Format|^Bulk|^Multi|^Editor|^Cross|^Alias|^Concurrent")) | .sid' | while read sid; do
    cxml_bin delete --id $sid --force
done
```

## Notes
- cXML bins store XML documents for handling voice calls, SMS messages, and fax
- The `cxml_bin` command is the new primary name; `laml_bin` is a backwards compatibility alias
- Both commands access the same API endpoint and manage the same resources
- Contents can be provided inline with `--contents` or edited interactively via the configured editor
- If no changes are made in the editor (quit without saving), the operation is cancelled
- The Compatibility API uses form-encoded payloads (not JSON)
- Bin SIDs are UUIDs in the format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
- URL encoding is handled automatically for names and contents with special characters
- The `request_url` field provides the webhook URL to use in phone number or application configurations
- XML should be well-formed; malformed XML may still be accepted by the API but could cause runtime errors
- Template variables like `{{From}}` and `{{To}}` can be used in cXML for dynamic content
- Always verify bin changes after updates to ensure they were applied correctly
- Delete operations require confirmation unless --force flag is used
- Editor defaults to `pyvim` if `$EDITOR` environment variable is not set

## API Endpoint Reference
- **Base URL**: `api/laml/2010-04-01/Accounts/{AccountSid}/LamlBins`
- **Methods**: GET (list/retrieve), POST (create/update), DELETE (delete)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/x-www-form-urlencoded (Compatibility API)
- **Payload Format**: Form-encoded (e.g., `Name=value&Contents=value`)
- **Delete Response**: 204 No Content on successful deletion

## Command Reference

### cxml_bin (Primary)
```
cxml_bin list [-n NAME] [-i ID] [-j]
cxml_bin create -n NAME [--contents CONTENTS]
cxml_bin update -i ID [-n NAME] [--contents CONTENTS]
cxml_bin delete -i ID [-f]
```

### laml_bin (Alias)
```
laml_bin list [-n NAME] [-i ID] [-j]
laml_bin create -n NAME [--contents CONTENTS]
laml_bin update -i ID [-n NAME] [--contents CONTENTS]
laml_bin delete -i ID [-f]
```

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the cxml_bin and laml_bin commands.
