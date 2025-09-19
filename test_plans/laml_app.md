# LaML Application Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Compatibility API
- Valid project/account with Voice, Messaging, or Fax scope permissions
- Ability to create and manage LaML applications

## Test Cases

### 1. List Commands
```bash
# TC-001: List all LaML applications (detailed format - DEFAULT)
laml_app list

# TC-002: List LaML applications in JSON format
laml_app list --json

# TC-003: List specific LaML application by ID
laml_app list --id <app_sid>

# TC-004: List non-existent LaML application by ID
laml_app list --id nonexistent-123-456

# TC-005: List with invalid application ID format
laml_app list --id invalid_id_format

# TC-006: List when no applications exist
laml_app list

# TC-007: List with very long application ID
laml_app list --id "$(python3 -c "print('a'*1000)")"

# TC-008: List with special characters in ID
laml_app list --id "test@app#id"
```

### 2. Create Commands
```bash
# TC-009: Create basic LaML application with name only
laml_app create --name "Basic Test App"

# TC-010: Create LaML application with multi-word name
laml_app create --name "Multi Word Application Name"

# TC-011: Create LaML application with voice URL
laml_app create --name "Voice App" --voice-url https://example.com/voice

# TC-012: Create LaML application with voice URL and method
laml_app create --name "Voice Method App" --voice-url https://example.com/voice --voice-method GET

# TC-013: Create LaML application with voice fallback
laml_app create --name "Voice Fallback App" --voice-url https://example.com/voice --voice-fallback-url https://example.com/fallback

# TC-014: Create LaML application with SMS configuration
laml_app create --name "SMS App" --sms-url https://example.com/sms --sms-method POST

# TC-015: Create LaML application with SMS fallback
laml_app create --name "SMS Fallback App" --sms-url https://example.com/sms --sms-fallback-url https://example.com/sms-fallback

# TC-016: Create LaML application with status callback
laml_app create --name "Status App" --status-callback https://example.com/status --status-callback-method GET

# TC-017: Create LaML application with caller ID lookup enabled
laml_app create --name "Caller ID App" --voice-caller-id-lookup true

# TC-018: Create LaML application with message status callback
laml_app create --name "Message Status App" --message-status-callback https://example.com/message-status

# TC-019: Create LaML application with SMS status callback
laml_app create --name "SMS Status App" --sms-status-callback https://example.com/sms-status

# TC-020: Create LaML application with all voice options
laml_app create --name "Full Voice App" --voice-url https://example.com/voice --voice-method POST --voice-fallback-url https://example.com/voice-fallback --voice-fallback-method GET --voice-caller-id-lookup true

# TC-021: Create LaML application with all SMS options
laml_app create --name "Full SMS App" --sms-url https://example.com/sms --sms-method GET --sms-fallback-url https://example.com/sms-fallback --sms-fallback-method POST --sms-status-callback https://example.com/sms-status

# TC-022: Create LaML application with all callback options
laml_app create --name "Full Callback App" --status-callback https://example.com/status --status-callback-method POST --message-status-callback https://example.com/message-status

# TC-023: Create LaML application with all parameters
laml_app create --name "Complete App" --voice-url https://example.com/voice --voice-method POST --voice-fallback-url https://example.com/voice-fallback --voice-fallback-method GET --voice-caller-id-lookup true --sms-url https://example.com/sms --sms-method GET --sms-fallback-url https://example.com/sms-fallback --sms-fallback-method POST --status-callback https://example.com/status --status-callback-method POST --message-status-callback https://example.com/message-status --sms-status-callback https://example.com/sms-status

# TC-024: Create LaML application with special characters in name
laml_app create --name "Test-App_2023"

# TC-025: Create LaML application with Unicode characters
laml_app create --name "测试应用"

# TC-026: Create LaML application without name (should fail)
laml_app create --voice-url https://example.com/voice

# TC-027: Create LaML application with empty name (should fail)
laml_app create --name ""

# TC-028: Create LaML application with only whitespace (should fail)
laml_app create --name "   "

# TC-029: Create LaML application with invalid voice method (should fail)
laml_app create --name "Invalid Method App" --voice-method INVALID

# TC-030: Create LaML application with invalid SMS method (should fail)
laml_app create --name "Invalid SMS Method App" --sms-method INVALID

# TC-031: Create LaML application with invalid status callback method (should fail)
laml_app create --name "Invalid Status Method App" --status-callback-method INVALID

# TC-032: Create LaML application with invalid caller ID lookup (should fail)
laml_app create --name "Invalid Caller ID App" --voice-caller-id-lookup invalid

# TC-033: Create LaML application with malformed URL
laml_app create --name "Malformed URL App" --voice-url "not-a-valid-url"

# TC-034: Create LaML application with very long name
laml_app create --name "$(python3 -c "print('a'*100)")"

# TC-035: Create LaML application with URL containing special characters
laml_app create --name "Special URL App" --voice-url "https://example.com/voice?param=value&other=test"
```

### 3. Update Commands
```bash
# TC-036: Update LaML application name by ID
laml_app update --id <app_sid> --name "Updated App Name"

# TC-037: Update LaML application voice URL
laml_app update --id <app_sid> --voice-url https://updated.example.com/voice

# TC-038: Update LaML application voice method
laml_app update --id <app_sid> --voice-method GET

# TC-039: Update LaML application voice fallback
laml_app update --id <app_sid> --voice-fallback-url https://updated.example.com/fallback

# TC-040: Update LaML application SMS configuration
laml_app update --id <app_sid> --sms-url https://updated.example.com/sms --sms-method GET

# TC-041: Update LaML application status callback
laml_app update --id <app_sid> --status-callback https://updated.example.com/status

# TC-042: Update LaML application caller ID lookup
laml_app update --id <app_sid> --voice-caller-id-lookup false

# TC-043: Update LaML application with multi-word name
laml_app update --id <app_sid> --name "Updated Multi Word Name"

# TC-044: Update multiple LaML application parameters
laml_app update --id <app_sid> --name "Fully Updated App" --voice-url https://new.example.com/voice --sms-url https://new.example.com/sms

# TC-045: Update LaML application with special characters
laml_app update --id <app_sid> --name "Updated-App_2023"

# TC-046: Update LaML application with Unicode characters
laml_app update --id <app_sid> --name "更新的应用"

# TC-047: Update LaML application without ID (should fail)
laml_app update --name "Some Name"

# TC-048: Update LaML application without any parameters (should fail)
laml_app update --id <app_sid>

# TC-049: Update LaML application with invalid ID (should fail)
laml_app update --id invalid-123-456 --name "Test"

# TC-050: Update LaML application with non-existent ID (should fail)
laml_app update --id AP00000000000000000000000000000000 --name "Test"

# TC-051: Update LaML application with empty name (should fail)
laml_app update --id <app_sid> --name ""

# TC-052: Update LaML application with only whitespace (should fail)
laml_app update --id <app_sid> --name "   "

# TC-053: Update LaML application with invalid voice method (should fail)
laml_app update --id <app_sid> --voice-method INVALID

# TC-054: Update LaML application with invalid SMS method (should fail)
laml_app update --id <app_sid> --sms-method INVALID

# TC-055: Update LaML application with invalid status callback method (should fail)
laml_app update --id <app_sid> --status-callback-method INVALID

# TC-056: Update LaML application with invalid caller ID lookup (should fail)
laml_app update --id <app_sid> --voice-caller-id-lookup invalid

# TC-057: Update LaML application back to original values
laml_app update --id <app_sid> --name "Original Name" --voice-caller-id-lookup false
```

### 4. Delete Commands
```bash
# TC-058: Delete LaML application with confirmation prompt
laml_app delete --id <app_sid>

# TC-059: Delete LaML application with force flag (no confirmation)
laml_app delete --id <app_sid> --force

# TC-060: Delete LaML application without ID (should fail)
laml_app delete

# TC-061: Delete LaML application with invalid ID (should fail)
laml_app delete --id invalid-123-456 --force

# TC-062: Delete LaML application with non-existent ID (should fail)
laml_app delete --id AP00000000000000000000000000000000 --force

# TC-063: Cancel delete operation (choose 'no' when prompted)
laml_app delete --id <app_sid>

# TC-064: Delete with case variations in confirmation
laml_app delete --id <app_sid>  # Test 'Y', 'y', 'yes', 'Yes'

# TC-065: Delete with invalid confirmation responses
laml_app delete --id <app_sid>  # Test 'maybe', '1', 'sure'

# TC-066: Delete LaML application currently in use (should succeed but may impact service)
laml_app delete --id <active_app_sid> --force
```

### 5. Edge Cases & Error Handling
```bash
# TC-067: Invalid command (should show help)
laml_app invalid_command

# TC-068: No subcommand (should show help)
laml_app

# TC-069: Help command
laml_app --help

# TC-070: Help for specific subcommands
laml_app create --help
laml_app update --help
laml_app list --help
laml_app delete --help

# TC-071: LaML application name with newlines
laml_app create --name $'Test\nApp'

# TC-072: LaML application name with tabs
laml_app create --name $'Test\tApp'

# TC-073: Multiple concurrent create operations
laml_app create --name "Concurrent1" &
laml_app create --name "Concurrent2" &
wait

# TC-074: URL encoding edge cases
laml_app create --name "Test%20App"
laml_app create --name "Test+App"
laml_app create --name "Test&App"

# TC-075: Case sensitivity tests
laml_app create --name "test"
laml_app create --name "Test"
laml_app create --name "TEST"

# TC-076: Maximum length name testing
laml_app create --name "$(python3 -c "print('TestApp' * 50)")"

# TC-077: Special API characters
laml_app create --name "Test/App\\Path"
laml_app create --name "Test\"App\"Name"
laml_app create --name "Test'App'Name"

# TC-078: Application SID boundary testing
laml_app list --id "$(python3 -c "print('AP' + 'a' * 32)")"

# TC-079: URL with query parameters
laml_app create --name "Query Params App" --voice-url "https://example.com/voice?param1=value1&param2=value2"

# TC-080: URL with fragments
laml_app create --name "Fragment App" --voice-url "https://example.com/voice#section"

# TC-081: Very long URLs
laml_app create --name "Long URL App" --voice-url "https://example.com/$(python3 -c "print('a' * 500)")"

# TC-082: International domain names
laml_app create --name "International App" --voice-url "https://测试.example.com/voice"

# TC-083: All HTTP methods testing
laml_app create --name "POST Methods" --voice-method POST --sms-method POST --status-callback-method POST
laml_app create --name "GET Methods" --voice-method GET --sms-method GET --status-callback-method GET

# TC-084: Caller ID lookup variations
laml_app create --name "Caller ID True" --voice-caller-id-lookup true
laml_app create --name "Caller ID False" --voice-caller-id-lookup false
```

### 6. Integration Tests
```bash
# TC-085: Full LaML application lifecycle
# Create -> List (verify) -> Update -> List (verify changes) -> Delete
laml_app create --name "Lifecycle Test" --voice-url https://example.com/lifecycle
laml_app list --id <new_app_sid>
laml_app update --id <new_app_sid> --name "Updated Lifecycle Test" --sms-url https://example.com/sms
laml_app list --id <new_app_sid>
laml_app delete --id <new_app_sid> --force

# TC-086: Create and verify in different output formats
laml_app create --name "Format Test" --voice-url https://example.com/format
laml_app list --id <new_app_sid>
laml_app list --id <new_app_sid> --json

# TC-087: Update and verify changes persist
laml_app update --id <app_sid> --name "Persistence Test" --voice-caller-id-lookup true
laml_app list --id <app_sid>
laml_app list --id <app_sid> --json

# TC-088: Multiple operations on same LaML application
laml_app create --name "Multi Op Test" --voice-url https://example.com/multi
laml_app update --id <new_app_sid> --name "Multi Op Test Updated"
laml_app update --id <new_app_sid> --sms-url https://example.com/sms
laml_app update --id <new_app_sid> --name "Multi Op Test Final" --status-callback https://example.com/status
laml_app list --id <new_app_sid>

# TC-089: Test all output formatting consistency
laml_app list  # Detailed format
laml_app list --json  # JSON format
laml_app list --id <app_sid>  # Single application detailed
laml_app list --id <app_sid> --json  # Single application JSON

# TC-090: Bulk operations testing
laml_app create --name "Bulk Test 1" --voice-url https://example.com/bulk1
laml_app create --name "Bulk Test 2" --sms-url https://example.com/bulk2
laml_app create --name "Bulk Test 3" --status-callback https://example.com/bulk3
laml_app list --json  # Verify all created
laml_app delete --id <bulk1_sid> --force
laml_app delete --id <bulk2_sid> --force
laml_app delete --id <bulk3_sid> --force

# TC-091: Configuration transition testing
laml_app create --name "Config Test" --voice-url https://example.com/initial
laml_app update --id <config_app_sid> --sms-url https://example.com/sms --voice-url
laml_app update --id <config_app_sid> --status-callback https://example.com/status
laml_app update --id <config_app_sid> --voice-caller-id-lookup true
laml_app delete --id <config_app_sid> --force
```

### 7. URL and Callback Functionality Tests
```bash
# TC-092: Test various URL configurations
laml_app create --name "HTTP App" --voice-url http://example.com/voice
laml_app create --name "HTTPS App" --voice-url https://secure.example.com/voice
laml_app create --name "Port App" --voice-url https://example.com:8080/voice
laml_app create --name "Path App" --voice-url https://example.com/path/to/voice

# TC-093: Test callback combinations
laml_app create --name "Voice Only" --voice-url https://example.com/voice
laml_app create --name "SMS Only" --sms-url https://example.com/sms
laml_app create --name "Status Only" --status-callback https://example.com/status
laml_app create --name "Voice+SMS" --voice-url https://example.com/voice --sms-url https://example.com/sms
laml_app create --name "Voice+Status" --voice-url https://example.com/voice --status-callback https://example.com/status
laml_app create --name "SMS+Status" --sms-url https://example.com/sms --status-callback https://example.com/status

# TC-094: Test fallback configurations
laml_app create --name "Voice Fallback" --voice-url https://example.com/voice --voice-fallback-url https://example.com/voice-fallback
laml_app create --name "SMS Fallback" --sms-url https://example.com/sms --sms-fallback-url https://example.com/sms-fallback
laml_app create --name "Both Fallbacks" --voice-url https://example.com/voice --voice-fallback-url https://example.com/voice-fallback --sms-url https://example.com/sms --sms-fallback-url https://example.com/sms-fallback

# TC-095: Test method combinations
laml_app create --name "All POST" --voice-url https://example.com/voice --voice-method POST --sms-url https://example.com/sms --sms-method POST --status-callback https://example.com/status --status-callback-method POST
laml_app create --name "All GET" --voice-url https://example.com/voice --voice-method GET --sms-url https://example.com/sms --sms-method GET --status-callback https://example.com/status --status-callback-method GET
laml_app create --name "Mixed Methods" --voice-url https://example.com/voice --voice-method POST --sms-url https://example.com/sms --sms-method GET --status-callback https://example.com/status --status-callback-method POST

# Cleanup test applications
laml_app list --json | jq -r '.[] | select(.friendly_name | test("^HTTP|^HTTPS|^Port|^Path|^Voice Only|^SMS Only|^Status Only|^Voice\\+|^SMS\\+|^Voice Fallback|^SMS Fallback|^Both Fallbacks|^All POST|^All GET|^Mixed Methods")) | .sid' | while read sid; do
    laml_app delete --id $sid --force
done
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, etc.)
- **Data Validation**: Verify LaML application data matches input (friendly_name, voice_url, sms_url, etc.)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **URL Validation**: Verify URLs are properly encoded and stored

## Test Environment Setup
```bash
# Save original LaML applications for reference
laml_app list --json > original_laml_applications.json

# Get available LaML applications for testing
laml_app list --json | jq -r '.[] | .sid'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# After testing, clean up test LaML applications
laml_app list --json | jq -r '.[] | select(.friendly_name | test("^Test|^Lifecycle|^Format|^Bulk|^Basic|^Multi|^Voice|^SMS|^Status|^Complete|^Full")) | .sid' | while read sid; do
    laml_app delete --id $sid --force
done
```

## Notes
- LaML applications are used for handling voice calls, SMS messages, and fax within SignalWire projects
- Applications define webhooks and callback URLs for processing incoming communications
- Voice URLs handle incoming voice calls and can include fallback URLs for reliability
- SMS URLs handle incoming text messages with optional fallback and status callback URLs
- Status callbacks provide real-time updates on application events
- Caller ID lookup enables database verification of incoming caller information
- The Compatibility API uses form-encoded payloads (not JSON)
- Application SIDs follow the format: APxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
- URL encoding is handled automatically for URLs and parameters with special characters
- HTTP methods can be POST or GET for various webhook configurations
- Always verify application changes after updates to ensure they were applied correctly
- Delete operations require confirmation unless --force flag is used
- Applications can be referenced by phone numbers, domain applications, and other SignalWire resources

## API Endpoint Reference
- **Base URL**: `api/laml/2010-04-01/Accounts/{AccountSid}/Applications`
- **Methods**: GET (list/retrieve), POST (create/update), DELETE (delete)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/x-www-form-urlencoded (Compatibility API)
- **Payload Format**: Form-encoded (e.g., `FriendlyName=value&VoiceUrl=value`)
- **Delete Response**: 204 No Content on successful deletion

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the laml_app command.