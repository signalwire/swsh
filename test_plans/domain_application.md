# Domain Application Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire REST API
- Valid project/account with Voice scope permissions
- Ability to create and manage domain applications

## Test Cases

### 1. List Commands
```bash
# TC-001: List all domain applications (detailed format - DEFAULT)
domain_application list

# TC-002: List domain applications in JSON format
domain_application list --json

# TC-003: List specific domain application by ID
domain_application list --id <app_id>

# TC-004: Search domain applications by name
domain_application list --name "My Domain App"

# TC-005: Search with multi-word name
domain_application list --name My Test Application

# TC-006: Search domain applications by domain
domain_application list --domain "example.domain.com"

# TC-007: Search with multi-word domain
domain_application list --domain my test domain

# TC-008: Search by both name and domain (combined filters)
domain_application list --name "Test App" --domain "test.domain.com"

# TC-009: List non-existent domain application by ID
domain_application list --id nonexistent-123-456

# TC-010: Search for non-existent domain application by name
domain_application list --name "NonExistentApp"

# TC-011: Search for non-existent domain by domain
domain_application list --domain "nonexistent.domain.com"

# TC-012: List with invalid domain application ID format
domain_application list --id invalid_id_format

# TC-013: List when no domain applications exist
domain_application list

# TC-014: List with very long domain application ID
domain_application list --id "$(python3 -c "print('a'*1000)")"

# TC-015: List with special characters in ID
domain_application list --id "test@app#id"
```

### 2. Create Commands
```bash
# TC-016: Create domain application with relay_context handler
domain_application create --name "Test Relay App" --identifier testrelayapp --call-handler relay_context --call-relay-context my_context

# TC-017: Create domain application with laml_webhooks handler
domain_application create --name "Test Webhook App" --identifier testwebhookapp --call-handler laml_webhooks --call-request-url https://example.com/webhook

# TC-018: Create domain application with laml_application handler
domain_application create --name "Test LaML App" --identifier testlamlapp --call-handler laml_application --call-laml-application-id 12345678-1234-1234-1234-123456789012

# TC-019: Create domain application with video_room handler
domain_application create --name "Test Video App" --identifier testvideoapp --call-handler video_room --call-video-room-id 87654321-4321-4321-4321-210987654321

# TC-020: Create domain application with multi-word name
domain_application create --name "Multi Word Domain Application" --identifier multiwordapp --call-handler relay_context --call-relay-context my_context

# TC-021: Create domain application with IP authentication enabled
domain_application create --name "IP Auth App" --identifier ipauthapp --call-handler relay_context --call-relay-context my_context --ip-auth-enabled true --ip-auth 192.168.1.100 10.0.0.1

# TC-022: Create domain application with encryption settings
domain_application create --name "Encrypted App" --identifier encryptedapp --call-handler relay_context --call-relay-context my_context --encryption required

# TC-023: Create domain application with custom codecs
domain_application create --name "Codec App" --identifier codecapp --call-handler relay_context --call-relay-context my_context --codecs OPUS G722 PCMU

# TC-024: Create domain application with custom ciphers
domain_application create --name "Cipher App" --identifier cipherapp --call-handler relay_context --call-relay-context my_context --ciphers AEAD_AES_256_GCM_8 AES_256_CM_HMAC_SHA1_80

# TC-025: Create domain application with all webhook options
domain_application create --name "Full Webhook App" --identifier fullwebhookapp --call-handler laml_webhooks --call-request-url https://example.com/webhook --call-request-method POST --call-fallback-url https://example.com/fallback --call-fallback-method GET --call-status-callback-url https://example.com/status --call-status-callback-method POST

# TC-026: Create domain application with special characters in name
domain_application create --name "Test-App_2023" --identifier testapp2023 --call-handler relay_context --call-relay-context my_context

# TC-027: Create domain application with Unicode characters
domain_application create --name "测试应用" --identifier testappunicode --call-handler relay_context --call-relay-context my_context

# TC-028: Create domain application without name (should fail)
domain_application create --identifier testapp --call-handler relay_context --call-relay-context my_context

# TC-029: Create domain application without identifier (should fail)
domain_application create --name "Test App" --call-handler relay_context --call-relay-context my_context

# TC-030: Create domain application without call-handler (should fail)
domain_application create --name "Test App" --identifier testapp

# TC-031: Create domain application with relay_context but no context (should fail)
domain_application create --name "Test App" --identifier testapp --call-handler relay_context

# TC-032: Create domain application with laml_webhooks but no URL (should fail)
domain_application create --name "Test App" --identifier testapp --call-handler laml_webhooks

# TC-033: Create domain application with laml_application but no ID (should fail)
domain_application create --name "Test App" --identifier testapp --call-handler laml_application

# TC-034: Create domain application with video_room but no room ID (should fail)
domain_application create --name "Test App" --identifier testapp --call-handler video_room

# TC-035: Create domain application with IP auth enabled but no IPs (should fail)
domain_application create --name "Test App" --identifier testapp --call-handler relay_context --call-relay-context my_context --ip-auth-enabled true

# TC-036: Create domain application with duplicate identifier (should fail)
domain_application create --name "Test App 1" --identifier duplicatetest --call-handler relay_context --call-relay-context my_context
domain_application create --name "Test App 2" --identifier duplicatetest --call-handler relay_context --call-relay-context my_context

# TC-037: Create domain application with empty name (should fail)
domain_application create --name "" --identifier testapp --call-handler relay_context --call-relay-context my_context

# TC-038: Create domain application with empty identifier (should fail)
domain_application create --name "Test App" --identifier "" --call-handler relay_context --call-relay-context my_context

# TC-039: Create domain application with only whitespace name (should fail)
domain_application create --name "   " --identifier testapp --call-handler relay_context --call-relay-context my_context

# TC-040: Create domain application with invalid encryption value (should fail)
domain_application create --name "Test App" --identifier testapp --call-handler relay_context --call-relay-context my_context --encryption invalid

# TC-041: Create domain application with invalid codec (should fail)
domain_application create --name "Test App" --identifier testapp --call-handler relay_context --call-relay-context my_context --codecs INVALID_CODEC

# TC-042: Create domain application with invalid cipher (should fail)
domain_application create --name "Test App" --identifier testapp --call-handler relay_context --call-relay-context my_context --ciphers INVALID_CIPHER
```

### 3. Update Commands
```bash
# TC-043: Update domain application name by ID
domain_application update --id <app_id> --name "Updated App Name"

# TC-044: Update domain application identifier
domain_application update --id <app_id> --identifier updatedidentifier

# TC-045: Update domain application call handler
domain_application update --id <app_id> --call-handler laml_webhooks --call-request-url https://new.example.com/webhook

# TC-046: Update domain application from relay_context to laml_application
domain_application update --id <app_id> --call-handler laml_application --call-laml-application-id 11111111-1111-1111-1111-111111111111

# TC-047: Update domain application with multi-word name
domain_application update --id <app_id> --name "Updated Multi Word Name"

# TC-048: Update domain application IP authentication
domain_application update --id <app_id> --ip-auth-enabled true --ip-auth 192.168.1.200 10.0.0.2

# TC-049: Update domain application encryption settings
domain_application update --id <app_id> --encryption optional

# TC-050: Update domain application codecs
domain_application update --id <app_id> --codecs OPUS VP8 H264

# TC-051: Update domain application ciphers
domain_application update --id <app_id> --ciphers AES_CM_128_HMAC_SHA1_80 AES_CM_128_HMAC_SHA1_32

# TC-052: Update multiple domain application parameters
domain_application update --id <app_id> --name "Fully Updated App" --identifier fullyupdated --encryption required --codecs OPUS G722

# TC-053: Update domain application with special characters
domain_application update --id <app_id> --name "Updated-App_2023"

# TC-054: Update domain application with Unicode characters
domain_application update --id <app_id> --name "更新的应用"

# TC-055: Update domain application without ID (should fail)
domain_application update --name "Some Name"

# TC-056: Update domain application without any parameters (should fail)
domain_application update --id <app_id>

# TC-057: Update domain application with invalid ID (should fail)
domain_application update --id invalid-123-456 --name "Test"

# TC-058: Update domain application with non-existent ID (should fail)
domain_application update --id 00000000-0000-0000-0000-000000000000 --name "Test"

# TC-059: Update domain application with empty name (should fail)
domain_application update --id <app_id> --name ""

# TC-060: Update domain application with only whitespace (should fail)
domain_application update --id <app_id> --name "   "

# TC-061: Update domain application with invalid call handler requirements (should fail)
domain_application update --id <app_id> --call-handler relay_context

# TC-062: Update domain application with conflicting IP auth settings (should fail)
domain_application update --id <app_id> --ip-auth-enabled true

# TC-063: Update domain application back to original values
domain_application update --id <app_id> --name "Original Name" --identifier originalidentifier
```

### 4. Delete Commands
```bash
# TC-064: Delete domain application with confirmation prompt
domain_application delete --id <app_id>

# TC-065: Delete domain application with force flag (no confirmation)
domain_application delete --id <app_id> --force

# TC-066: Delete domain application without ID (should fail)
domain_application delete

# TC-067: Delete domain application with invalid ID (should fail)
domain_application delete --id invalid-123-456 --force

# TC-068: Delete domain application with non-existent ID (should fail)
domain_application delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-069: Cancel delete operation (choose 'no' when prompted)
domain_application delete --id <app_id>

# TC-070: Delete with case variations in confirmation
domain_application delete --id <app_id>  # Test 'Y', 'y', 'yes', 'Yes'

# TC-071: Delete with invalid confirmation responses
domain_application delete --id <app_id>  # Test 'maybe', '1', 'sure'

# TC-072: Delete domain application currently in use (should succeed but may impact service)
domain_application delete --id <active_app_id> --force
```

### 5. Edge Cases & Error Handling
```bash
# TC-073: Invalid command (should show help)
domain_application invalid_command

# TC-074: No subcommand (should show help)
domain_application

# TC-075: Help command
domain_application --help

# TC-076: Help for specific subcommands
domain_application create --help
domain_application update --help
domain_application list --help
domain_application delete --help

# TC-077: Domain application name with newlines
domain_application create --name $'Test\nApp' --identifier testnewline --call-handler relay_context --call-relay-context my_context

# TC-078: Domain application name with tabs
domain_application create --name $'Test\tApp' --identifier testtab --call-handler relay_context --call-relay-context my_context

# TC-079: Multiple concurrent create operations
domain_application create --name "Concurrent1" --identifier concurrent1 --call-handler relay_context --call-relay-context context1 &
domain_application create --name "Concurrent2" --identifier concurrent2 --call-handler relay_context --call-relay-context context2 &
wait

# TC-080: URL encoding edge cases
domain_application create --name "Test%20App" --identifier testpercent --call-handler relay_context --call-relay-context my_context
domain_application create --name "Test+App" --identifier testplus --call-handler relay_context --call-relay-context my_context
domain_application create --name "Test&App" --identifier testamp --call-handler relay_context --call-relay-context my_context

# TC-081: Case sensitivity tests
domain_application create --name "test" --identifier testlower --call-handler relay_context --call-relay-context my_context
domain_application create --name "Test" --identifier testcap --call-handler relay_context --call-relay-context my_context
domain_application create --name "TEST" --identifier testupper --call-handler relay_context --call-relay-context my_context

# TC-082: Maximum length name testing
domain_application create --name "$(python3 -c "print('TestApp' * 50)")" --identifier longname --call-handler relay_context --call-relay-context my_context

# TC-083: Special API characters
domain_application create --name "Test/App\\Path" --identifier testpath --call-handler relay_context --call-relay-context my_context
domain_application create --name "Test\"App\"Name" --identifier testquote --call-handler relay_context --call-relay-context my_context
domain_application create --name "Test'App'Name" --identifier testsingle --call-handler relay_context --call-relay-context my_context

# TC-084: Identifier boundary testing
domain_application create --name "Test App" --identifier "$(python3 -c "print('a' * 100)")" --call-handler relay_context --call-relay-context my_context

# TC-085: Multiple IP addresses testing
domain_application create --name "Multi IP App" --identifier multiip --call-handler relay_context --call-relay-context my_context --ip-auth-enabled true --ip-auth 192.168.1.1 192.168.1.2 10.0.0.1 10.0.0.2 172.16.0.1

# TC-086: All codec combinations
domain_application create --name "All Codecs App" --identifier allcodecs --call-handler relay_context --call-relay-context my_context --codecs OPUS G722 PCMU PCMA VP8 H264

# TC-087: All cipher combinations
domain_application create --name "All Ciphers App" --identifier allciphers --call-handler relay_context --call-relay-context my_context --ciphers AEAD_AES_256_GCM_8 AES_256_CM_HMAC_SHA1_80 AES_CM_128_HMAC_SHA1_80 AES_256_CM_HMAC_SHA1_32 AES_CM_128_HMAC_SHA1_32
```

### 6. Integration Tests
```bash
# TC-088: Full domain application lifecycle
# Create -> List (verify) -> Update -> List (verify changes) -> Delete
domain_application create --name "Lifecycle Test" --identifier lifecycletest --call-handler relay_context --call-relay-context test_context
domain_application list --id <new_app_id>
domain_application update --id <new_app_id> --name "Updated Lifecycle Test" --call-handler laml_webhooks --call-request-url https://example.com/updated
domain_application list --id <new_app_id>
domain_application delete --id <new_app_id> --force

# TC-089: Create and verify in different output formats
domain_application create --name "Format Test" --identifier formattest --call-handler relay_context --call-relay-context test_context
domain_application list --id <new_app_id>
domain_application list --id <new_app_id> --json

# TC-090: Update and verify changes persist
domain_application update --id <app_id> --name "Persistence Test" --encryption required
domain_application list --id <app_id>
domain_application list --id <app_id> --json

# TC-091: Multiple operations on same domain application
domain_application create --name "Multi Op Test" --identifier multioptest --call-handler relay_context --call-relay-context test_context
domain_application update --id <new_app_id> --name "Multi Op Test Updated"
domain_application update --id <new_app_id> --encryption optional
domain_application update --id <new_app_id> --name "Multi Op Test Final" --codecs OPUS G722
domain_application list --id <new_app_id>

# TC-092: Test all output formatting consistency
domain_application list  # Detailed format
domain_application list --json  # JSON format
domain_application list --id <app_id>  # Single application detailed
domain_application list --id <app_id> --json  # Single application JSON

# TC-093: Bulk operations testing
domain_application create --name "Bulk Test 1" --identifier bulktest1 --call-handler relay_context --call-relay-context context1
domain_application create --name "Bulk Test 2" --identifier bulktest2 --call-handler laml_webhooks --call-request-url https://example.com/bulk2
domain_application create --name "Bulk Test 3" --identifier bulktest3 --call-handler laml_application --call-laml-application-id 33333333-3333-3333-3333-333333333333
domain_application list --json  # Verify all created
domain_application delete --id <bulk1_id> --force
domain_application delete --id <bulk2_id> --force
domain_application delete --id <bulk3_id> --force

# TC-094: Call handler transition testing
domain_application create --name "Handler Test" --identifier handlertest --call-handler relay_context --call-relay-context initial_context
domain_application update --id <handler_app_id> --call-handler laml_webhooks --call-request-url https://example.com/transition
domain_application update --id <handler_app_id> --call-handler laml_application --call-laml-application-id 44444444-4444-4444-4444-444444444444
domain_application update --id <handler_app_id> --call-handler video_room --call-video-room-id 55555555-5555-5555-5555-555555555555
domain_application delete --id <handler_app_id> --force
```

### 7. Call Handler Functionality Tests
```bash
# TC-095: Test all call handler types with their requirements
domain_application create --name "relay_handler" --identifier relayhandler --call-handler relay_context --call-relay-context test_context
domain_application create --name "webhook_handler" --identifier webhookhandler --call-handler laml_webhooks --call-request-url https://example.com/webhook
domain_application create --name "laml_handler" --identifier lamlhandler --call-handler laml_application --call-laml-application-id 12345678-1234-1234-1234-123456789012
domain_application create --name "video_handler" --identifier videohandler --call-handler video_room --call-video-room-id 87654321-4321-4321-4321-210987654321

# Verify handler-specific fields
domain_application list --json | grep -A20 -B5 relay_handler
domain_application list --json | grep -A20 -B5 webhook_handler
domain_application list --json | grep -A20 -B5 laml_handler
domain_application list --json | grep -A20 -B5 video_handler

# Test handler updates with proper requirements
domain_application update --id <relay_id> --call-handler laml_webhooks --call-request-url https://new.example.com/webhook
domain_application update --id <webhook_id> --call-handler relay_context --call-relay-context new_context
domain_application update --id <laml_id> --call-handler video_room --call-video-room-id 99999999-9999-9999-9999-999999999999
domain_application update --id <video_id> --call-handler laml_application --call-laml-application-id 88888888-8888-8888-8888-888888888888

# Cleanup
domain_application delete --id <relay_id> --force
domain_application delete --id <webhook_id> --force
domain_application delete --id <laml_id> --force
domain_application delete --id <video_id> --force
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, etc.)
- **Data Validation**: Verify domain application data matches input (name, identifier, call_handler, etc.)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **Conditional Validation**: Verify required parameters are enforced based on call handler type

## Test Environment Setup
```bash
# Save original domain applications for reference
domain_application list --json > original_domain_applications.json

# Get available domain applications for testing
domain_application list --json | jq -r '.[] | .id'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# After testing, clean up test domain applications
domain_application list --json | jq -r '.[] | select(.name | test("^Test|^Lifecycle|^Format|^Bulk")) | .id' | while read id; do
    domain_application delete --id $id --force
done
```

## Notes
- Domain applications are used for SIP/WebRTC endpoint registration and call routing within SignalWire projects
- Each domain application requires a unique identifier within the project
- Call handlers determine how incoming calls are processed (relay context, webhooks, LaML applications, or video rooms)
- IP authentication provides security by restricting access to specific IP addresses
- Encryption, codecs, and ciphers control media security and quality settings
- Domain applications can affect active connections when deleted or modified
- The REST API uses JSON payloads (not form-encoded like Compatibility API)
- Domain Application IDs follow the UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
- Always verify domain application changes after updates to ensure they were applied correctly
- Delete operations require confirmation unless --force flag is used
- Conditional validation ensures required parameters are provided based on call handler selection

## API Endpoint Reference
- **Base URL**: `api/relay/rest/domain_applications`
- **Methods**: GET (list/retrieve), POST (create), PUT (update), DELETE (delete)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/json (REST API)
- **Payload Format**: JSON (e.g., `{"name": "value", "identifier": "value"}`)
- **Delete Response**: 204 No Content on successful deletion

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the domain_application command.