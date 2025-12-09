# Message Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Compatibility API
- Valid project/account with Messaging scope permissions
- At least one SignalWire phone number capable of sending SMS/MMS
- Test phone numbers for inbound/outbound message testing
- Media files accessible via URL for MMS testing
- Webhook endpoint for status callback testing (optional)
- Number Group (Messaging Service) for testing MessagingServiceSid (optional)

## Test Cases

### 1. Send Commands (SMS)
```bash
# TC-001: Send basic SMS with required parameters
message send --to-num +15551234567 --from-num +15559876543 --body "Hello World"

# TC-002: Send SMS with multi-word body
message send --to-num +15551234567 --from-num +15559876543 --body Hello World from SignalWire

# TC-003: Send SMS with quoted body containing special characters
message send --to-num +15551234567 --from-num +15559876543 --body "Hello! How are you? #Testing @SignalWire"

# TC-004: Send SMS with status callback
message send --to-num +15551234567 --from-num +15559876543 --body "Test message" --status-callback https://example.com/message-status

# TC-005: Send SMS with application SID
message send --to-num +15551234567 --from-num +15559876543 --body "Test message" --application-sid AP1234567890abcdef1234567890abcdef

# TC-006: Send SMS with max price
message send --to-num +15551234567 --from-num +15559876543 --body "Test message" --max-price 0.0075

# TC-007: Send SMS with validity period
message send --to-num +15551234567 --from-num +15559876543 --body "Test message" --validity-period 3600

# TC-008: Send SMS using MessagingServiceSid (Number Group)
message send --to-num +15551234567 --messaging-service-sid MG1234567890abcdef1234567890abcdef --body "Test message"

# TC-009: Send SMS with all optional parameters
message send --to-num +15551234567 --from-num +15559876543 --body "Complete test" --status-callback https://example.com/status --max-price 0.01 --validity-period 7200

# TC-010: Send SMS without to number (should fail)
message send --from-num +15559876543 --body "Test message"

# TC-011: Send SMS without from number or messaging service (should fail)
message send --to-num +15551234567 --body "Test message"

# TC-012: Send SMS without body or media (should fail)
message send --to-num +15551234567 --from-num +15559876543

# TC-013: Send SMS with invalid phone number format
message send --to-num "invalid-number" --from-num +15559876543 --body "Test"

# TC-014: Send SMS with invalid from number format
message send --to-num +15551234567 --from-num "invalid-number" --body "Test"

# TC-015: Send SMS with both from-num and messaging-service-sid (messaging-service-sid takes priority)
message send --to-num +15551234567 --from-num +15559876543 --messaging-service-sid MG1234567890abcdef --body "Test"

# TC-016: Send SMS with international phone numbers
message send --to-num +447123456789 --from-num +15559876543 --body "International test"

# TC-017: Send SMS to short code
message send --to-num 12345 --from-num +15559876543 --body "Short code test"

# TC-018: Send SMS with very long body (exceeds 1600 chars - should warn about splitting)
message send --to-num +15551234567 --from-num +15559876543 --body "$(python3 -c "print('A' * 1700)")"

# TC-019: Send SMS with exactly 1600 characters
message send --to-num +15551234567 --from-num +15559876543 --body "$(python3 -c "print('A' * 1600)")"

# TC-020: Send SMS with Unicode/emoji characters
message send --to-num +15551234567 --from-num +15559876543 --body "Hello! Testing unicode: こんにちは 🎉"

# TC-021: Send SMS with newlines in body
message send --to-num +15551234567 --from-num +15559876543 --body "Line 1
Line 2
Line 3"

# TC-022: Send SMS with negative validity period
message send --to-num +15551234567 --from-num +15559876543 --body "Test" --validity-period -1

# TC-023: Send SMS with zero max price
message send --to-num +15551234567 --from-num +15559876543 --body "Test" --max-price 0
```

### 2. Send Commands (MMS)
```bash
# TC-024: Send MMS with single media URL
message send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/image.jpg

# TC-025: Send MMS with body and media URL
message send --to-num +15551234567 --from-num +15559876543 --body "Check out this image" --media-url https://example.com/image.jpg

# TC-026: Send MMS with multiple media URLs
message send --to-num +15551234567 --from-num +15559876543 --body "Multiple images" --media-url https://example.com/image1.jpg https://example.com/image2.jpg

# TC-027: Send MMS with maximum media URLs (10)
message send --to-num +15551234567 --from-num +15559876543 --body "Max media" --media-url https://example.com/1.jpg https://example.com/2.jpg https://example.com/3.jpg https://example.com/4.jpg https://example.com/5.jpg https://example.com/6.jpg https://example.com/7.jpg https://example.com/8.jpg https://example.com/9.jpg https://example.com/10.jpg

# TC-028: Send MMS with more than 10 media URLs (should fail)
message send --to-num +15551234567 --from-num +15559876543 --body "Too many" --media-url https://example.com/1.jpg https://example.com/2.jpg https://example.com/3.jpg https://example.com/4.jpg https://example.com/5.jpg https://example.com/6.jpg https://example.com/7.jpg https://example.com/8.jpg https://example.com/9.jpg https://example.com/10.jpg https://example.com/11.jpg

# TC-029: Send MMS with invalid media URL
message send --to-num +15551234567 --from-num +15559876543 --media-url "not-a-valid-url"

# TC-030: Send MMS with non-existent media URL
message send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/nonexistent.jpg

# TC-031: Send MMS with different media types
message send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/image.png
message send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/image.gif
message send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/video.mp4
message send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/audio.mp3

# TC-032: Send MMS with URL containing special characters
message send --to-num +15551234567 --from-num +15559876543 --media-url "https://example.com/images/test%20image.jpg"

# TC-033: Send MMS with URL containing query parameters
message send --to-num +15551234567 --from-num +15559876543 --media-url "https://example.com/image.jpg?token=abc123&size=large"
```

### 3. List Commands
```bash
# TC-034: List all messages
message list

# TC-035: List all messages in JSON format
message list --json

# TC-036: List specific message by ID
message list --id SM1234567890abcdef1234567890abcdef

# TC-037: List specific message by ID in JSON format
message list --id SM1234567890abcdef1234567890abcdef --json

# TC-038: List messages by status - queued
message list --status queued

# TC-039: List messages by status - sending
message list --status sending

# TC-040: List messages by status - sent
message list --status sent

# TC-041: List messages by status - failed
message list --status failed

# TC-042: List messages by status - delivered
message list --status delivered

# TC-043: List messages by status - undelivered
message list --status undelivered

# TC-044: List messages by status - receiving
message list --status receiving

# TC-045: List messages by status - received
message list --status received

# TC-046: List messages by date sent
message list --date-sent 2023-06-15

# TC-047: List messages by date sent with less than operator
message list --date-sent "<2023-06-15"

# TC-048: List messages by date sent with greater than operator
message list --date-sent ">2023-06-01"

# TC-049: List messages from specific number
message list --from-num +15559876543

# TC-050: List messages to specific number
message list --to-num +15551234567

# TC-051: List messages with page size limit
message list --page-size 25

# TC-052: List messages with multiple filters
message list --status delivered --from-num +15559876543 --date-sent ">2023-01-01"

# TC-053: List messages with all filters and JSON output
message list --status sent --from-num +15559876543 --to-num +15551234567 --date-sent 2023-06-15 --page-size 50 --json

# TC-054: List non-existent message by ID
message list --id SM00000000000000000000000000000000

# TC-055: List with invalid message ID format
message list --id "invalid-message-id"

# TC-056: List messages when no messages exist matching filter
message list --status queued

# TC-057: List with invalid status (should fail)
message list --status invalid-status

# TC-058: List with invalid date format
message list --date-sent "invalid-date"

# TC-059: List with future date (should return empty)
message list --date-sent ">2099-01-01"

# TC-060: List with very large page size
message list --page-size 1000
```

### 4. Get Commands (Alias for List with ID)
```bash
# TC-061: Get specific message by ID
message get --id SM1234567890abcdef1234567890abcdef

# TC-062: Get specific message by ID in JSON format
message get --id SM1234567890abcdef1234567890abcdef --json

# TC-063: Get message without ID (should fail)
message get

# TC-064: Get non-existent message by ID
message get --id SM00000000000000000000000000000000

# TC-065: Get message with invalid ID format
message get --id "invalid-message-id"

# TC-066: Verify get and list --id produce identical results
message get --id SM1234567890abcdef1234567890abcdef > get_result.tmp
message list --id SM1234567890abcdef1234567890abcdef > list_result.tmp
diff get_result.tmp list_result.tmp
rm get_result.tmp list_result.tmp
```

### 5. Update Commands (Redact)
```bash
# TC-067: Update message body with new text
message update --id SM1234567890abcdef1234567890abcdef --body "Updated message content"

# TC-068: Update message body with multi-word text
message update --id SM1234567890abcdef1234567890abcdef --body Updated message with multiple words

# TC-069: Redact message body using --redact flag
message update --id SM1234567890abcdef1234567890abcdef --redact

# TC-070: Redact message body using empty --body
message update --id SM1234567890abcdef1234567890abcdef --body

# TC-071: Update message without ID (should fail)
message update --body "New content"

# TC-072: Update message without body or redact flag (should fail)
message update --id SM1234567890abcdef1234567890abcdef

# TC-073: Update message with invalid ID
message update --id "invalid-message-id" --body "Test"

# TC-074: Update message with non-existent ID
message update --id SM00000000000000000000000000000000 --body "Test"

# TC-075: Update in-progress message (may fail depending on status)
message update --id <in_progress_message_id> --body "Updated"

# TC-076: Update already redacted message
message update --id <redacted_message_id> --body "New content after redact"
```

### 6. Delete Commands
```bash
# TC-077: Delete message with confirmation prompt
message delete --id SM1234567890abcdef1234567890abcdef

# TC-078: Delete message with force flag (no confirmation)
message delete --id SM1234567890abcdef1234567890abcdef --force

# TC-079: Delete message without ID (should fail)
message delete

# TC-080: Delete message with invalid ID (should fail)
message delete --id "invalid-message-id" --force

# TC-081: Delete message with non-existent ID (should fail)
message delete --id SM00000000000000000000000000000000 --force

# TC-082: Cancel delete operation (choose 'no' when prompted)
message delete --id SM1234567890abcdef1234567890abcdef

# TC-083: Delete with case variations in confirmation
message delete --id SM1234567890abcdef1234567890abcdef  # Test 'Y', 'y', 'yes', 'Yes'

# TC-084: Delete with invalid confirmation responses
message delete --id SM1234567890abcdef1234567890abcdef  # Test 'maybe', '1', 'sure'

# TC-085: Delete in-progress message (should fail with specific error)
message delete --id <in_progress_message_id> --force
```

### 7. Media List Commands
```bash
# TC-086: List media for a message
message media list --message-id SM1234567890abcdef1234567890abcdef

# TC-087: List media for a message in JSON format
message media list --message-id SM1234567890abcdef1234567890abcdef --json

# TC-088: List media without message ID (should fail)
message media list

# TC-089: List media for non-existent message
message media list --message-id SM00000000000000000000000000000000

# TC-090: List media for SMS message (should return empty - no media)
message media list --message-id <sms_only_message_id>

# TC-091: List media for MMS message with attachments
message media list --message-id <mms_message_id>

# TC-092: List media with invalid message ID format
message media list --message-id "invalid-message-id"
```

### 8. Media Get Commands
```bash
# TC-093: Get specific media for a message
message media get --message-id SM1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef

# TC-094: Get specific media in JSON format
message media get --message-id SM1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef --json

# TC-095: Get media without message ID (should fail)
message media get --media-id ME1234567890abcdef1234567890abcdef

# TC-096: Get media without media ID (should fail)
message media get --message-id SM1234567890abcdef1234567890abcdef

# TC-097: Get media with non-existent message ID
message media get --message-id SM00000000000000000000000000000000 --media-id ME1234567890abcdef1234567890abcdef

# TC-098: Get media with non-existent media ID
message media get --message-id SM1234567890abcdef1234567890abcdef --media-id ME00000000000000000000000000000000

# TC-099: Get media with invalid ID formats
message media get --message-id "invalid" --media-id "invalid"
```

### 9. Media Delete Commands
```bash
# TC-100: Delete media with confirmation prompt
message media delete --message-id SM1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef

# TC-101: Delete media with force flag
message media delete --message-id SM1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef --force

# TC-102: Delete media without message ID (should fail)
message media delete --media-id ME1234567890abcdef1234567890abcdef --force

# TC-103: Delete media without media ID (should fail)
message media delete --message-id SM1234567890abcdef1234567890abcdef --force

# TC-104: Delete media with non-existent IDs
message media delete --message-id SM00000000000000000000000000000000 --media-id ME00000000000000000000000000000000 --force

# TC-105: Cancel media delete operation
message media delete --message-id SM1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef
# Choose 'no' when prompted

# TC-106: Delete media - verify message still exists after
message media delete --message-id SM1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef --force
message get --id SM1234567890abcdef1234567890abcdef  # Message should still exist
```

### 10. Logs Commands
```bash
# TC-107: List message logs
message logs list

# TC-108: List message logs in JSON format
message logs list --json

# TC-109: Get specific message log by ID
message logs get --id <log_id>

# TC-110: Get specific message log by ID in JSON format
message logs get --id <log_id> --json

# TC-111: Get non-existent message log by ID
message logs get --id 00000000-0000-0000-0000-000000000000

# TC-112: Get message log without ID (should fail)
message logs get

# TC-113: Logs subcommand without action (should show help)
message logs

# TC-114: Logs subcommand help
message logs --help
message logs list --help
message logs get --help
```

### 11. Edge Cases & Error Handling

```bash
# TC-115: Invalid command (should show help)
message invalid_command

# TC-108: No subcommand (should show help)
message

# TC-109: Help command
message --help

# TC-110: Help for specific subcommands
message send --help
message list --help
message get --help
message update --help
message delete --help
message media --help
message media list --help
message media get --help
message media delete --help

# TC-111: Phone numbers with extensions
message send --to-num "+15551234567;ext=123" --from-num +15559876543 --body "Test"

# TC-112: Phone numbers with special characters
message send --to-num "+1(555)123-4567" --from-num +15559876543 --body "Test"

# TC-113: Multiple concurrent send operations
message send --to-num +15551234567 --from-num +15559876543 --body "Concurrent 1" &
message send --to-num +15551234568 --from-num +15559876543 --body "Concurrent 2" &
wait

# TC-114: Message SID boundary testing
message get --id "$(python3 -c "print('SM' + 'a' * 32)")"
message get --id "SM1234567890abcdef1234567890ABCDEF"  # Test case sensitivity

# TC-115: Phone number variations
message list --from-num "15559876543"  # Without +
message list --from-num "+1 555 987 6543"  # With spaces
message list --from-num "+1-555-987-6543"  # With dashes
message list --from-num "+1(555)987-6543"  # With parentheses

# TC-116: Body with various escape sequences
message send --to-num +15551234567 --from-num +15559876543 --body "Tab:\tNewline:\nQuote:\"Backslash:\\"

# TC-117: Body with only whitespace
message send --to-num +15551234567 --from-num +15559876543 --body "   "

# TC-118: Body with leading/trailing whitespace
message send --to-num +15551234567 --from-num +15559876543 --body "  Trimmed message  "

# TC-119: Empty body with only media (valid MMS)
message send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/image.jpg

# TC-120: Date filtering with various formats
message list --date-sent "2023-06-15T00:00:00Z"
message list --date-sent "06/15/2023"
```

### 11. Integration Tests
```bash
# TC-121: Full SMS lifecycle
# Send -> Get (verify) -> Update/Redact -> Get (verify changes) -> Delete
message send --to-num +15551234567 --from-num +15559876543 --body "Lifecycle test"
message get --id <new_message_sid>
message update --id <new_message_sid> --redact
message get --id <new_message_sid>
message delete --id <new_message_sid> --force

# TC-122: Full MMS lifecycle with media
message send --to-num +15551234567 --from-num +15559876543 --body "MMS lifecycle" --media-url https://example.com/image.jpg
message get --id <new_message_sid>
message media list --message-id <new_message_sid>
message media get --message-id <new_message_sid> --media-id <media_sid>
message media delete --message-id <new_message_sid> --media-id <media_sid> --force
message delete --id <new_message_sid> --force

# TC-123: Test status callback functionality
message send --to-num +15551234567 --from-num +15559876543 --body "Callback test" --status-callback https://example.com/message-status
# Monitor callback logs to verify status updates

# TC-124: Test message filtering by status progression
message send --to-num +15551234567 --from-num +15559876543 --body "Status test"
message list --status queued  # May catch it if quick
message list --status sending
message list --status sent
message list --status delivered

# TC-125: Test message filtering combinations
message list --status delivered --from-num +15559876543 --to-num +15551234567 --json
message list --date-sent ">2023-01-01" --page-size 10 --json

# TC-126: Test MessagingServiceSid integration
message send --to-num +15551234567 --messaging-service-sid <number_group_sid> --body "Number Group test"
message get --id <message_sid>  # Verify from number was selected automatically

# TC-127: Test max price limiting
message send --to-num +15551234567 --from-num +15559876543 --body "Max price test" --max-price 0.001
# May fail if message cost exceeds max price

# TC-128: Test validity period expiration
message send --to-num +15551234567 --from-num +15559876543 --body "Validity test" --validity-period 60
# Wait for validity period and verify message behavior

# TC-129: Bulk message operations
message send --to-num +15551234567 --from-num +15559876543 --body "Bulk 1"
message send --to-num +15551234568 --from-num +15559876543 --body "Bulk 2"
message send --to-num +15551234569 --from-num +15559876543 --body "Bulk 3"
message list --from-num +15559876543 --json  # Verify all created
message list --status sent --from-num +15559876543

# TC-130: Test redaction workflow
message send --to-num +15551234567 --from-num +15559876543 --body "Sensitive information: SSN 123-45-6789"
message get --id <message_sid>  # Verify body content
message update --id <message_sid> --redact
message get --id <message_sid>  # Verify body is empty

# TC-131: Test MMS with multiple media files
message send --to-num +15551234567 --from-num +15559876543 --body "Multi-media test" --media-url https://example.com/1.jpg https://example.com/2.jpg https://example.com/3.jpg
message media list --message-id <message_sid>  # Should show 3 media items
message media get --message-id <message_sid> --media-id <first_media_sid>
message media get --message-id <message_sid> --media-id <second_media_sid>
message media get --message-id <message_sid> --media-id <third_media_sid>

# TC-132: Test deleting individual media from MMS
message send --to-num +15551234567 --from-num +15559876543 --body "Media delete test" --media-url https://example.com/1.jpg https://example.com/2.jpg
message media list --message-id <message_sid>  # 2 media items
message media delete --message-id <message_sid> --media-id <first_media_sid> --force
message media list --message-id <message_sid>  # 1 media item remaining
message get --id <message_sid>  # Message still exists

# TC-133: Test application SID for callbacks
message send --to-num +15551234567 --from-num +15559876543 --body "App SID test" --application-sid <laml_app_sid>
message get --id <message_sid>  # Verify application_sid is set
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, etc.)
- **Data Validation**: Verify message data matches input (from, to, body, status, media)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **Message State**: Verify message status transitions (queued -> sending -> sent -> delivered)
- **Callback Verification**: For status callbacks, verify events are triggered correctly
- **Media Handling**: Verify media is properly attached and accessible

## Test Environment Setup
```bash
# Save original messages for reference
message list --json > original_messages.json

# Get available messages for testing
message list --json | jq -r '.[].sid'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# Verify test phone numbers and media URLs
echo "From Number: +15559876543"  # Replace with actual SignalWire number
echo "To Numbers: +15551234567, +15551234568, +15551234569"  # Replace with test numbers
echo "Test Image: https://example.com/image.jpg"  # Replace with accessible image URL

# After testing, clean up test messages
message list --json | jq -r '.[] | select(.from == "+15559876543") | .sid' | while read sid; do
    message delete --id $sid --force
done
```

## Notes
- Messages are billable resources - exercise caution with send operations
- SMS messages have a 1600 character limit per segment
- MMS supports up to 10 media URLs with 5MB combined size
- Status values: queued, sending, sent, failed, delivered, undelivered, receiving, received
- Outbound statuses: queued -> sending -> sent -> delivered/undelivered/failed
- Inbound statuses: receiving -> received
- The Compatibility API uses form-encoded payloads (not JSON)
- Message SIDs follow the format: SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
- Media SIDs follow the format: MExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
- Phone numbers should be in E.164 format (+1XXXXXXXXXX for US/Canada)
- URL encoding is handled automatically for body and URLs with special characters
- Deleting a message does NOT delete associated media - use media delete separately
- In-progress messages cannot be deleted
- Redacting a message sets the body to empty string (cannot be undone)
- MessagingServiceSid is the ID of a Number Group for automatic number selection
- Status callbacks require accessible webhook endpoints
- Unicode characters and emojis count as multiple characters in SMS

## API Endpoint Reference
- **Base URL**: `api/laml/2010-04-01/Accounts/{AccountSid}/Messages`
- **Media URL**: `api/laml/2010-04-01/Accounts/{AccountSid}/Messages/{MessageSid}/Media`
- **Methods**: GET (list/retrieve), POST (create/update), DELETE (delete)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/x-www-form-urlencoded (Compatibility API)
- **Payload Format**: Form-encoded (e.g., `To=value&From=value&Body=value`)
- **Delete Response**: 204 No Content on successful deletion

## Command Reference
```
message send -t TO [-f FROM | --messaging-service-sid SID] [-b BODY] [-m MEDIA_URL...] [--status-callback URL] [--application-sid SID] [--max-price PRICE] [--validity-period SECS]
message list [-i ID] [-j] [--status STATUS] [--date-sent DATE] [--from-num NUM] [--to-num NUM] [--page-size N]
message get -i ID [-j]
message update -i ID [-b BODY | --redact]
message delete -i ID [-f]
message media list --message-id ID [-j]
message media get --message-id ID --media-id ID [-j]
message media delete --message-id ID --media-id ID [-f]
```

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the message command.
