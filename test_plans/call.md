# Call Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Compatibility API
- Valid project/account with Voice scope permissions
- At least one SignalWire phone number for outbound calling
- Test phone numbers for inbound/outbound call testing
- Access to LaML applications and LaML bins for testing

## Test Cases

### 1. Send Commands
```bash
# TC-001: Send basic call with URL
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml

# TC-002: Send call with LaML Bin ID
call send --from-num +15551234567 --to-num +15559876543 --laml-bin-id LB1234567890abcdef1234567890abcdef

# TC-003: Send call with HTTP method
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --method GET

# TC-004: Send call with fallback URL
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --fallback-url https://example.com/fallback

# TC-005: Send call with fallback method
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --fallback-url https://example.com/fallback --fallback-method GET

# TC-006: Send call with status callback
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --status-callback https://example.com/status

# TC-007: Send call with status callback method
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --status-callback https://example.com/status --status-callback-method GET

# TC-008: Send call with status callback events
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --status-callback https://example.com/status --status-callback-event initiated ringing answered completed

# TC-009: Send call with timeout
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --timeout 30

# TC-010: Send call with recording enabled
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --record

# TC-011: Send call with recording channels
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --record --record-channels dual

# TC-012: Send call with recording format
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --record --record-format wav

# TC-013: Send call with trim setting
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --record --trim do-not-trim

# TC-014: Send call with caller ID
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --caller-id +15555555555

# TC-015: Send call with DTMF digits
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --send-digits "12345"

# TC-016: Send call with machine detection
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable

# TC-017: Send call with machine detection action
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable --if-machine hangup

# TC-018: Send call with machine URL
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable --if-machine-url https://example.com/machine

# TC-019: Send call with machine detection timeout
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable --machine-detection-timeout 10

# TC-020: Send call with speech thresholds
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable --machine-detection-speech-threshold 2000 --machine-detection-speech-end-threshold 1200

# TC-021: Send call with silence timeout
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable --machine-detection-silence-timeout 5000

# TC-022: Send call with all parameters
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --method POST --fallback-url https://example.com/fallback --fallback-method GET --status-callback https://example.com/status --status-callback-method POST --status-callback-event initiated answered completed --timeout 60 --record --record-channels dual --record-format mp3 --trim trim-silence --caller-id +15555555555 --send-digits "123" --machine-detection enable --if-machine continue --if-machine-url https://example.com/machine --machine-detection-timeout 10 --machine-detection-speech-threshold 2000 --machine-detection-speech-end-threshold 1200 --machine-detection-silence-timeout 5000

# TC-023: Send call without from number (should fail)
call send --to-num +15559876543 --url https://example.com/laml

# TC-024: Send call without to number (should fail)
call send --from-num +15551234567 --url https://example.com/laml

# TC-025: Send call without URL or LaML Bin ID (should fail)
call send --from-num +15551234567 --to-num +15559876543

# TC-026: Send call with both URL and LaML Bin ID (should fail)
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --laml-bin-id LB1234567890abcdef1234567890abcdef

# TC-027: Send call with invalid from number format
call send --from-num "invalid-number" --to-num +15559876543 --url https://example.com/laml

# TC-028: Send call with invalid to number format
call send --from-num +15551234567 --to-num "invalid-number" --url https://example.com/laml

# TC-029: Send call with invalid HTTP method (should fail)
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --method INVALID

# TC-030: Send call with invalid recording channels (should fail)
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --record --record-channels invalid

# TC-031: Send call with invalid recording format (should fail)
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --record --record-format invalid

# TC-032: Send call with invalid trim setting (should fail)
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --record --trim invalid

# TC-033: Send call with invalid machine detection (should fail)
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection invalid

# TC-034: Send call with invalid if-machine action (should fail)
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --if-machine invalid

# TC-035: Send call with negative timeout
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --timeout -1

# TC-036: Send call with very high timeout
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --timeout 3600

# TC-037: Send call with non-existent LaML Bin ID
call send --from-num +15551234567 --to-num +15559876543 --laml-bin-id LB00000000000000000000000000000000

# TC-038: Send call with malformed URL
call send --from-num +15551234567 --to-num +15559876543 --url "not-a-valid-url"

# TC-039: Send call with international phone numbers
call send --from-num +15551234567 --to-num +447123456789 --url https://example.com/laml

# TC-040: Send call with short codes
call send --from-num +15551234567 --to-num 12345 --url https://example.com/laml
```

### 2. Get Commands
```bash
# TC-041: Get all calls
call get

# TC-042: Get all calls in JSON format
call get --json

# TC-043: Get specific call by ID
call get --id CA1234567890abcdef1234567890abcdef

# TC-044: Get specific call by ID in JSON format
call get --id CA1234567890abcdef1234567890abcdef --json

# TC-045: Get all active calls
call get --all-active

# TC-046: Get all active calls in JSON format
call get --all-active --json

# TC-047: Get calls by status - queued
call get --status queued

# TC-048: Get calls by status - ringing
call get --status ringing

# TC-049: Get calls by status - in-progress
call get --status in-progress

# TC-050: Get calls by status - completed
call get --status completed

# TC-051: Get calls by status - failed
call get --status failed

# TC-052: Get calls by status - busy
call get --status busy

# TC-053: Get calls by status - no-answer
call get --status no-answer

# TC-054: Get calls by status - canceled
call get --status canceled

# TC-055: Get calls by start time
call get --start-time 2023-01-01

# TC-056: Get calls by end time
call get --end-time 2023-12-31

# TC-057: Get calls by time range
call get --start-time 2023-01-01 --end-time 2023-01-31

# TC-058: Get calls from specific number
call get --from-num +15551234567

# TC-059: Get calls to specific number
call get --to-num +15559876543

# TC-060: Get calls by parent call SID
call get --parent-call-sid CA1234567890abcdef1234567890abcdef

# TC-061: Get calls with multiple filters
call get --status completed --from-num +15551234567 --start-time 2023-01-01

# TC-062: Get non-existent call by ID
call get --id CA00000000000000000000000000000000

# TC-063: Get calls with invalid status (should fail)
call get --status invalid-status

# TC-064: Get calls with invalid date format
call get --start-time "invalid-date"

# TC-065: Get calls with malformed call SID
call get --id "invalid-call-sid"

# TC-066: Get calls when no calls exist
call get --status queued

# TC-067: Get active calls when no active calls exist
call get --all-active
```

### 3. Lookup Commands (Alias for Get)
```bash
# TC-068: Lookup all calls
call lookup

# TC-069: Lookup all calls in JSON format
call lookup --json

# TC-070: Lookup specific call by ID
call lookup --id CA1234567890abcdef1234567890abcdef

# TC-071: Lookup specific call by ID in JSON format
call lookup --id CA1234567890abcdef1234567890abcdef --json

# TC-072: Lookup all active calls
call lookup --all-active

# TC-073: Lookup all active calls in JSON format
call lookup --all-active --json

# TC-074: Lookup calls by status
call lookup --status in-progress

# TC-075: Lookup calls by time range
call lookup --start-time 2023-01-01 --end-time 2023-01-31

# TC-076: Lookup calls from specific number
call lookup --from-num +15551234567

# TC-077: Lookup calls to specific number
call lookup --to-num +15559876543

# TC-078: Lookup calls with multiple filters
call lookup --status completed --from-num +15551234567 --json

# TC-079: Verify lookup and get produce identical results
call get --id CA1234567890abcdef1234567890abcdef > get_result.tmp
call lookup --id CA1234567890abcdef1234567890abcdef > lookup_result.tmp
diff get_result.tmp lookup_result.tmp
rm get_result.tmp lookup_result.tmp
```

### 4. Update Commands
```bash
# TC-080: Update call URL
call update --id CA1234567890abcdef1234567890abcdef --url https://updated.example.com/laml

# TC-081: Update call method
call update --id CA1234567890abcdef1234567890abcdef --method GET

# TC-082: Update call status to canceled
call update --id CA1234567890abcdef1234567890abcdef --status canceled

# TC-083: Update call status to completed
call update --id CA1234567890abcdef1234567890abcdef --status completed

# TC-084: Update call fallback URL
call update --id CA1234567890abcdef1234567890abcdef --fallback-url https://updated.example.com/fallback

# TC-085: Update call fallback method
call update --id CA1234567890abcdef1234567890abcdef --fallback-method GET

# TC-086: Update call status callback
call update --id CA1234567890abcdef1234567890abcdef --status-callback https://updated.example.com/status

# TC-087: Update call status callback method
call update --id CA1234567890abcdef1234567890abcdef --status-callback-method GET

# TC-088: Update multiple call parameters
call update --id CA1234567890abcdef1234567890abcdef --url https://updated.example.com/laml --method POST --status-callback https://updated.example.com/status

# TC-089: Update call without ID (should fail)
call update --url https://updated.example.com/laml

# TC-090: Update call without any parameters (should fail)
call update --id CA1234567890abcdef1234567890abcdef

# TC-091: Update call with invalid ID (should fail)
call update --id invalid-call-id --url https://updated.example.com/laml

# TC-092: Update call with non-existent ID (should fail)
call update --id CA00000000000000000000000000000000 --url https://updated.example.com/laml

# TC-093: Update call with invalid status (should fail)
call update --id CA1234567890abcdef1234567890abcdef --status invalid-status

# TC-094: Update call with invalid method (should fail)
call update --id CA1234567890abcdef1234567890abcdef --method INVALID

# TC-095: Update completed call (should test API behavior)
call update --id <completed_call_id> --url https://updated.example.com/laml

# TC-096: Update canceled call (should test API behavior)
call update --id <canceled_call_id> --url https://updated.example.com/laml
```

### 5. Delete Commands
```bash
# TC-097: Delete call with confirmation prompt
call delete --id CA1234567890abcdef1234567890abcdef

# TC-098: Delete call with force flag (no confirmation)
call delete --id CA1234567890abcdef1234567890abcdef --force

# TC-099: Delete call without ID (should fail)
call delete

# TC-100: Delete call with invalid ID (should fail)
call delete --id invalid-call-id --force

# TC-101: Delete call with non-existent ID (should fail)
call delete --id CA00000000000000000000000000000000 --force

# TC-102: Cancel delete operation (choose 'no' when prompted)
call delete --id CA1234567890abcdef1234567890abcdef

# TC-103: Delete with case variations in confirmation
call delete --id CA1234567890abcdef1234567890abcdef  # Test 'Y', 'y', 'yes', 'Yes'

# TC-104: Delete with invalid confirmation responses
call delete --id CA1234567890abcdef1234567890abcdef  # Test 'maybe', '1', 'sure'

# TC-105: Delete active call
call delete --id <active_call_id> --force

# TC-106: Delete completed call
call delete --id <completed_call_id> --force
```

### 6. Logs Commands
```bash
# TC-107: List voice logs
call logs list

# TC-108: List voice logs in JSON format
call logs list --json

# TC-109: Get specific voice log by ID
call logs get --id <log_id>

# TC-110: Get specific voice log by ID in JSON format
call logs get --id <log_id> --json

# TC-111: Get non-existent voice log by ID
call logs get --id 00000000-0000-0000-0000-000000000000

# TC-112: Get voice log without ID (should fail)
call logs get

# TC-113: Logs subcommand without action (should show help)
call logs

# TC-114: Logs subcommand help
call logs --help
call logs list --help
call logs get --help
```

### 7. Edge Cases & Error Handling
```bash
# TC-115: Invalid command (should show help)
call invalid_command

# TC-108: No subcommand (should show help)
call

# TC-109: Help command
call --help

# TC-110: Help for specific subcommands
call send --help
call get --help
call lookup --help
call update --help
call delete --help

# TC-111: Phone numbers with extensions
call send --from-num +15551234567 --to-num "+15559876543;ext=123" --url https://example.com/laml

# TC-112: Phone numbers with special characters
call send --from-num +15551234567 --to-num "+1(555)987-6543" --url https://example.com/laml

# TC-113: URLs with query parameters
call send --from-num +15551234567 --to-num +15559876543 --url "https://example.com/laml?param1=value1&param2=value2"

# TC-114: URLs with fragments
call send --from-num +15551234567 --to-num +15559876543 --url "https://example.com/laml#section"

# TC-115: Very long URLs
call send --from-num +15551234567 --to-num +15559876543 --url "https://example.com/$(python3 -c "print('a' * 500)")"

# TC-116: International domain names
call send --from-num +15551234567 --to-num +15559876543 --url "https://测试.example.com/laml"

# TC-117: Multiple concurrent send operations
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/concurrent1 &
call send --from-num +15551234567 --to-num +15559876544 --url https://example.com/concurrent2 &
wait

# TC-118: DTMF digits with special characters
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --send-digits "123*456#789"

# TC-119: Status callback events - single event
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --status-callback https://example.com/status --status-callback-event initiated

# TC-120: Status callback events - multiple events
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --status-callback https://example.com/status --status-callback-event initiated ringing answered

# TC-121: Machine detection with DetectMessageEnd
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection DetectMessageEnd

# TC-122: Boundary testing for machine detection timeouts
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable --machine-detection-timeout 1
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable --machine-detection-timeout 60

# TC-123: Boundary testing for speech thresholds
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable --machine-detection-speech-threshold 100
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/laml --machine-detection enable --machine-detection-speech-threshold 10000

# TC-124: Date filtering with various formats
call get --start-time "2023-01-01T00:00:00Z"
call get --start-time "01/01/2023"
call get --end-time "2023-12-31T23:59:59Z"

# TC-125: Call SID boundary testing
call get --id "$(python3 -c "print('CA' + 'a' * 32)")"
call get --id "CA1234567890abcdef1234567890ABCDEF"  # Test case sensitivity

# TC-126: Phone number variations
call get --from-num "15551234567"  # Without +
call get --from-num "+1 555 123 4567"  # With spaces
call get --from-num "+1-555-123-4567"  # With dashes
call get --from-num "+1(555)123-4567"  # With parentheses
```

### 7. Integration Tests
```bash
# TC-127: Full call lifecycle
# Send -> Get (verify) -> Update -> Get (verify changes) -> Delete
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/lifecycle
call get --id <new_call_sid>
call update --id <new_call_sid> --status canceled
call get --id <new_call_sid>
call delete --id <new_call_sid> --force

# TC-128: Send and monitor call progress
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/monitor --status-callback https://example.com/status
# Monitor status changes through status callbacks or periodic get commands
call get --id <call_sid>
sleep 5
call get --id <call_sid>
sleep 5
call get --id <call_sid>

# TC-129: Test recording functionality
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/record --record --record-format wav --record-channels dual
call get --id <call_sid> --json  # Verify recording parameters

# TC-130: Test machine detection workflow
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/machine --machine-detection enable --if-machine hangup --machine-detection-timeout 10
call get --id <call_sid>  # Monitor for machine detection results

# TC-131: Test fallback URL functionality
call send --from-num +15551234567 --to-num +15559876543 --url https://invalid.example.com/laml --fallback-url https://example.com/fallback
call get --id <call_sid>  # Verify fallback was used

# TC-132: Test status callback events
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/events --status-callback https://example.com/status --status-callback-event initiated ringing answered completed
# Monitor status callback logs to verify events are triggered

# TC-133: Test LaML Bin integration
call send --from-num +15551234567 --to-num +15559876543 --laml-bin-id <valid_laml_bin_id>
call get --id <call_sid>  # Verify call was created with LaML Bin URL

# TC-134: Test active call filtering
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/active1
call send --from-num +15551234567 --to-num +15559876544 --url https://example.com/active2
call get --all-active  # Should show both calls if still in progress
call get --status in-progress  # Should match all-active results

# TC-135: Test call filtering combinations
call get --status completed --from-num +15551234567 --start-time 2023-01-01 --end-time 2023-12-31 --json
call get --to-num +15559876543 --status failed --json

# TC-136: Test update during active call
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/original
# While call is ringing or in-progress:
call update --id <call_sid> --url https://example.com/updated
call get --id <call_sid>  # Verify URL was updated

# TC-137: Test delete active vs completed calls
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/delete-test
call delete --id <call_sid> --force  # Delete while active
# Compare with deleting a completed call

# TC-138: Bulk operations testing
call send --from-num +15551234567 --to-num +15559876543 --url https://example.com/bulk1
call send --from-num +15551234567 --to-num +15559876544 --url https://example.com/bulk2
call send --from-num +15551234567 --to-num +15559876545 --url https://example.com/bulk3
call get --json  # Verify all calls created
call get --from-num +15551234567 --status in-progress  # Filter by sender
# Cleanup bulk calls
call delete --id <bulk1_sid> --force
call delete --id <bulk2_sid> --force
call delete --id <bulk3_sid> --force
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, etc.)
- **Data Validation**: Verify call data matches input (from, to, url, status, etc.)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **Call State**: Verify call status transitions (queued -> ringing -> in-progress -> completed)
- **Callback Verification**: For status callbacks, verify events are triggered correctly

## Test Environment Setup
```bash
# Save original calls for reference
call get --json > original_calls.json

# Get available calls for testing
call get --json | jq -r '.[] | .sid'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# Verify test phone numbers
echo "From Number: +15551234567"  # Replace with actual SignalWire number
echo "To Numbers: +15559876543, +15559876544, +15559876545"  # Replace with test numbers

# Create test LaML Bin for testing
# laml_bin create --name "Call Test Bin" --contents "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Say>Test call</Say></Response>"

# After testing, clean up test calls (be careful with active calls)
call get --json | jq -r '.[] | select(.status == "completed" or .status == "failed" or .status == "canceled") | select(.from == "+15551234567") | .sid' | while read sid; do
    call delete --id $sid --force
done
```

## Notes
- Calls are billable resources - exercise caution with send operations
- Active calls may incur charges until completed or canceled
- Machine detection and recording features may have additional costs
- Status callbacks require accessible webhook endpoints for testing
- Call progress depends on recipient phone behavior (answer, busy, no-answer)
- The Compatibility API uses form-encoded payloads (not JSON)
- Call SIDs follow the format: CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
- Phone numbers should be in E.164 format (+1XXXXXXXXXX for US/Canada)
- URL encoding is handled automatically for URLs and parameters with special characters
- Always verify call changes after updates to ensure they were applied correctly
- Delete operations require confirmation unless --force flag is used
- LaML Bin integration requires valid LaML Bin IDs from the same project
- Recording and machine detection features may not be available in all regions

## API Endpoint Reference
- **Base URL**: `api/laml/2010-04-01/Accounts/{AccountSid}/Calls`
- **Methods**: GET (list/retrieve), POST (create/update), DELETE (delete)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/x-www-form-urlencoded (Compatibility API)
- **Payload Format**: Form-encoded (e.g., `From=value&To=value&Url=value`)
- **Delete Response**: 204 No Content on successful deletion

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the call command.