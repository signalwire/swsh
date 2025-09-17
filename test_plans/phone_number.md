# Phone Number Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Test phone numbers available in the project
- Network connectivity to SignalWire API
- Valid webhook URLs for testing handlers (optional)

## Test Cases

**Note**: As of the latest update, `phone_number list` now shows detailed format by default. Use `--short` flag for the previous behavior (numbers only).

### 1. List Commands
```bash
# TC-001: List all phone numbers (detailed format - DEFAULT)
phone_number list

# TC-002: List phone numbers in short format (numbers only)
phone_number list --short

# TC-003: List phone numbers in JSON format
phone_number list --json

# TC-004: List phone numbers in short format with JSON
phone_number list --short --json

# TC-005: List specific phone number by ID
phone_number list --id <phone_number_id>

# TC-006: List specific phone number by E.164 number
phone_number list --number +15551234567

# TC-007: Search phone numbers by name
phone_number list --name testphone

# TC-008: Search with multi-word name
phone_number list --name "test phone name"

# TC-009: List with both name and number filters
phone_number list --name testphone --number +15551234567

# TC-010: List non-existent phone number by ID
phone_number list --id nonexistent123

# TC-011: List non-existent phone number by number
phone_number list --number +15559999999

# TC-012: List with invalid E.164 format (should still work - no validation on list)
phone_number list --number 5551234567
```

### 2. Update Commands - Basic
```bash
# TC-011: Update phone number name by ID
phone_number update --id <phone_number_id> --name "Updated Name"

# TC-012: Update phone number name by number
phone_number update --number +15551234567 --name "Updated by Number"

# TC-013: Update with multi-word name
phone_number update --id <phone_number_id> --name "Multi Word Phone Name"

# TC-014: Update without ID or number (should fail)
phone_number update --name "Some Name"

# TC-015: Update with invalid phone number ID (should fail)
phone_number update --id invalid123 --name "Test"

# TC-016: Update with non-existent phone number (should fail)
phone_number update --number +15559999999 --name "Test"

# TC-017: Update with no parameters provided (should fail)
phone_number update --id <phone_number_id>
```

### 3. Update Commands - Call Handlers
```bash
# TC-018: Update call handler to relay_context
phone_number update --number +15551234567 --call-handler relay_context --call-relay-context my_app

# TC-019: Update call handler to relay_topic
phone_number update --number +15551234567 --call-handler relay_topic --call-relay-topic office --call-relay-topic-status-callback-url https://example.com/callback

# TC-020: Update call handler to relay_application
phone_number update --number +15551234567 --call-handler relay_application --call-relay-application my_relay_app

# TC-021: Update call handler to laml_webhooks
phone_number update --number +15551234567 --call-handler laml_webhooks --call-request-url https://example.com/webhook

# TC-022: Update call handler to laml_application
phone_number update --number +15551234567 --call-handler laml_application --call-laml-application-id app123

# TC-023: Update call handler to dialogflow
phone_number update --number +15551234567 --call-handler dialogflow --call-dialogflow-agent-id agent123

# TC-024: Update call handler to relay_connector
phone_number update --number +15551234567 --call-handler relay_connector --call-relay-connector-id connector123

# TC-025: Update call handler to relay_sip_endpoint
phone_number update --number +15551234567 --call-handler relay_sip_endpoint --call-sip-endpoint-id endpoint123

# TC-026: Update call handler to relay_script
phone_number update --number +15551234567 --call-handler relay_script --call-relay-script-url https://example.com/script

# TC-027: Update call handler to relay_verto_endpoint
phone_number update --number +15551234567 --call-handler relay_verto_endpoint --call-verto-resource verto_resource

# TC-028: Update call handler to video_room
phone_number update --number +15551234567 --call-handler video_room --call-video-room-id room123

# TC-029: Update call receive mode to fax
phone_number update --number +15551234567 --call-receive-mode fax

# TC-030: Update call receive mode to voice
phone_number update --number +15551234567 --call-receive-mode voice
```

### 4. Update Commands - Message Handlers
```bash
# TC-031: Update message handler to relay_context
phone_number update --number +15551234567 --message-handler relay_context --message-relay-context my_app

# TC-032: Update message handler to relay_topic
phone_number update --number +15551234567 --message-handler relay_topic --message-relay-topic office

# TC-033: Update message handler to relay_application
phone_number update --number +15551234567 --message-handler relay_application --message-relay-application my_relay_app

# TC-034: Update message handler to laml_webhooks
phone_number update --number +15551234567 --message-handler laml_webhooks --message-request-url https://example.com/webhook

# TC-035: Update message handler to laml_application
phone_number update --number +15551234567 --message-handler laml_application --message-laml-application-id app123
```

### 5. Update Commands - Conditional Validation (Should Fail)
```bash
# TC-036: Call handler relay_context without required context (should fail)
phone_number update --number +15551234567 --call-handler relay_context

# TC-037: Call handler relay_topic without required topic (should fail)
phone_number update --number +15551234567 --call-handler relay_topic

# TC-038: Call handler laml_webhooks without required URL (should fail)
phone_number update --number +15551234567 --call-handler laml_webhooks

# TC-039: Call handler laml_application without required ID (should fail)
phone_number update --number +15551234567 --call-handler laml_application

# TC-040: Call handler dialogflow without required agent ID (should fail)
phone_number update --number +15551234567 --call-handler dialogflow

# TC-041: Call handler relay_connector without required connector ID (should fail)
phone_number update --number +15551234567 --call-handler relay_connector

# TC-042: Call handler relay_sip_endpoint without required endpoint ID (should fail)
phone_number update --number +15551234567 --call-handler relay_sip_endpoint

# TC-043: Call handler relay_script without required script URL (should fail)
phone_number update --number +15551234567 --call-handler relay_script

# TC-044: Call handler relay_verto_endpoint without required resource (should fail)
phone_number update --number +15551234567 --call-handler relay_verto_endpoint

# TC-045: Call handler video_room without required room ID (should fail)
phone_number update --number +15551234567 --call-handler video_room

# TC-046: Message handler relay_context without required context (should fail)
phone_number update --number +15551234567 --message-handler relay_context

# TC-047: Message handler relay_topic without required topic (should fail)
phone_number update --number +15551234567 --message-handler relay_topic

# TC-048: Message handler relay_application without required application (should fail)
phone_number update --number +15551234567 --message-handler relay_application

# TC-049: Message handler laml_webhooks without required URL (should fail)
phone_number update --number +15551234567 --message-handler laml_webhooks

# TC-050: Message handler laml_application without required ID (should fail)
phone_number update --number +15551234567 --message-handler laml_application
```

### 6. Update Commands - Advanced Options
```bash
# TC-051: Update laml_webhooks with all optional parameters
phone_number update --number +15551234567 --call-handler laml_webhooks --call-request-url https://example.com/webhook --call-request-method POST --call-fallback-url https://example.com/fallback --call-fallback-method GET --call-status-callback-url https://example.com/status --call-status-callback-method POST

# TC-052: Update message laml_webhooks with all optional parameters
phone_number update --number +15551234567 --message-handler laml_webhooks --message-request-url https://example.com/webhook --message-request-method POST --message-fallback-url https://example.com/fallback --message-fallback-method GET

# TC-053: Update call and message handlers simultaneously
phone_number update --number +15551234567 --call-handler relay_context --call-relay-context call_app --message-handler relay_application --message-relay-application message_app

# TC-054: Update with deprecated parameters (should still work)
phone_number update --number +15551234567 --call-handler relay_context --call-relay-context old_app

# TC-055: Update invalid handler choice (should fail)
phone_number update --number +15551234567 --call-handler invalid_handler
```

### 7. Release Commands
```bash
# TC-056: Release phone number by ID with confirmation
phone_number release --id <phone_number_id>

# TC-057: Release phone number by number with confirmation
phone_number release --number +15551234567

# TC-058: Release phone number with force flag (no confirmation)
phone_number release --id <phone_number_id> --force

# TC-059: Release phone number with force flag by number (no confirmation)
phone_number release --number +15551234567 --force

# TC-060: Release without ID or number (should fail)
phone_number release

# TC-061: Release non-existent phone number (should fail)
phone_number release --id nonexistent123

# TC-062: Release non-existent phone number by number (should fail)
phone_number release --number +15559999999

# TC-063: Cancel release operation (choose 'no' when prompted)
phone_number release --id <phone_number_id>
```

### 8. Lookup Commands
```bash
# TC-064: Basic phone number lookup
phone_number lookup --number +15551234567

# TC-065: Phone number lookup with JSON output
phone_number lookup --number +15551234567 --json

# TC-066: Phone number lookup with CNAM
phone_number lookup --number +15551234567 --cnam

# TC-067: Phone number lookup with carrier info
phone_number lookup --number +15551234567 --carrier

# TC-068: Phone number lookup with both CNAM and carrier
phone_number lookup --number +15551234567 --cnam --carrier

# TC-069: Phone number lookup with both CNAM and carrier in JSON
phone_number lookup --number +15551234567 --cnam --carrier --json

# TC-070: Lookup without number parameter (should fail)
phone_number lookup

# TC-071: Lookup with invalid E.164 format (should fail)
phone_number lookup --number 5551234567

# TC-072: Lookup with invalid E.164 format - missing plus (should fail)
phone_number lookup --number 15551234567

# TC-073: Lookup with invalid E.164 format - too short (should fail)
phone_number lookup --number +1555123

# TC-074: Lookup with invalid E.164 format - too long (should fail)
phone_number lookup --number +155512345678901234567890
```

### 9. Buy Commands - Interactive Mode
```bash
# TC-075: Buy phone number in interactive mode (no filters)
phone_number buy

# TC-076: Buy phone number with starts-with filter
phone_number buy --starts-with 555

# TC-077: Buy phone number with contains filter
phone_number buy --contains 123

# TC-078: Buy phone number with ends-with filter
phone_number buy --ends-with 7890

# TC-079: Buy phone number with max-results limit
phone_number buy --max-results 5

# TC-080: Buy phone number with multiple filters (starts-with and max-results)
phone_number buy --starts-with 555 --max-results 20

# TC-081: Buy phone number with invalid selection (should fail gracefully)
phone_number buy --starts-with 555
# Then enter invalid selection like 'abc' or '999'

# TC-082: Buy phone number and cancel purchase
phone_number buy --starts-with 555
# Then cancel when prompted for confirmation

# TC-083: Buy phone number with no available results
phone_number buy --starts-with 00000000

# TC-084: Interactive buy with invalid filter selection
phone_number buy
# Then enter invalid selection like '5' when only 1-4 are valid
```

### 10. Edge Cases & Error Handling
```bash
# TC-085: Invalid command (should show help)
phone_number invalid_command

# TC-086: No subcommand (should show help)
phone_number

# TC-087: Help command
phone_number --help

# TC-088: Help for specific subcommand
phone_number update --help

# TC-089: Very long phone number name (test limits)
phone_number update --number +15551234567 --name "$(python3 -c "print('a'*1000)")"

# TC-090: Special characters in phone number name
phone_number update --number +15551234567 --name "Test@Phone.com"

# TC-091: Unicode characters in phone number name
phone_number update --number +15551234567 --name "测试电话"

# TC-092: Empty name parameter
phone_number update --number +15551234567 --name ""

# TC-093: Name with only whitespace
phone_number update --number +15551234567 --name "   "

# TC-094: Multiple conflicting handler assignments
phone_number update --number +15551234567 --call-handler relay_context --call-relay-application conflicting_app

# TC-095: URL validation in webhook handlers
phone_number update --number +15551234567 --call-handler laml_webhooks --call-request-url "not-a-valid-url"
```

### 11. Integration Tests
```bash
# TC-096: Full phone number lifecycle
# List -> Update -> List (verify changes) -> Release
phone_number list --number +15551234567
phone_number update --number +15551234567 --name "Lifecycle Test" --call-handler relay_context --call-relay-context test_app
phone_number list --number +15551234567 --json
phone_number release --number +15551234567 --force

# TC-097: Multiple handler updates sequence
phone_number update --number +15551234567 --call-handler relay_context --call-relay-context app1
phone_number update --number +15551234567 --message-handler laml_webhooks --message-request-url https://example.com/webhook
phone_number update --number +15551234567 --call-handler laml_application --call-laml-application-id app123
phone_number list --number +15551234567  # Verify all changes persisted

# TC-098: Handler switching (change from one handler type to another)
phone_number update --number +15551234567 --call-handler relay_context --call-relay-context app1
phone_number update --number +15551234567 --call-handler laml_webhooks --call-request-url https://example.com/webhook
phone_number list --number +15551234567  # Verify handler changed correctly

# TC-099: Validation error recovery
phone_number update --number +15551234567 --message-handler relay_context  # Should fail with validation error
phone_number update --number +15551234567 --message-handler relay_context --message-relay-context correct_app  # Should succeed
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes
- **Data Validation**: Verify updated phone number data matches input
- **Validation Messages**: For conditional validation tests, verify proper error messages are shown

## Test Environment Setup
```bash
# Save original phone numbers for reference
phone_number list --json > original_phone_numbers.json

# Get available phone numbers for testing
phone_number list --json | jq -r '.[] | .number'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# After testing, verify phone numbers are in expected state
# (Restore any phone numbers to original configuration if needed)
```

## Notes
- Phone numbers are billable resources - exercise caution with buy/release operations
- Handler configurations affect how calls and messages are processed
- E.164 format validation is enforced on lookup command but not on list/update commands
- Conditional validation prevents API errors by catching missing required parameters
- Some handlers may require additional setup (webhooks, applications, etc.) to function properly
- Always verify handler settings after updates to ensure they were applied correctly
- Test with actual phone numbers in your SignalWire project when possible

## API Endpoint Reference
- **Base URL**: `api/relay/rest/phone_numbers`
- **Lookup URL**: `api/relay/rest/lookup/phone_number/`
- **Search URL**: `api/relay/rest/phone_numbers/search`
- **Methods**: GET (list/lookup), POST (buy), PUT (update), DELETE (release)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token

This test plan covers all functionality, conditional validation, edge cases, and error conditions for comprehensive validation of the phone_number command.