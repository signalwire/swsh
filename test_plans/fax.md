# Fax Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Compatibility API
- Valid project/account with Fax scope permissions
- At least one SignalWire phone number capable of sending faxes
- Test fax numbers for inbound/outbound fax testing
- PDF files accessible via URL for fax testing
- Webhook endpoint for status callback testing (optional)

## Test Cases

### 1. Send Commands
```bash
# TC-001: Send basic fax with required parameters
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf

# TC-002: Send fax with standard quality
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --quality standard

# TC-003: Send fax with fine quality (default)
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --quality fine

# TC-004: Send fax with superfine quality
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --quality superfine

# TC-005: Send fax with status callback
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --status-callback https://example.com/fax-status

# TC-006: Send fax with TTL (time-to-live)
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --ttl 60

# TC-007: Send fax in background mode
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --background

# TC-008: Send fax with all optional parameters
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --quality superfine --status-callback https://example.com/fax-status --ttl 120 --background

# TC-009: Send fax without to number (should fail)
fax send --from-num +15559876543 --media-url https://example.com/document.pdf

# TC-010: Send fax without from number (should fail)
fax send --to-num +15551234567 --media-url https://example.com/document.pdf

# TC-011: Send fax without media URL (should fail)
fax send --to-num +15551234567 --from-num +15559876543

# TC-012: Send fax with invalid quality option (should fail)
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --quality ultra

# TC-013: Send fax with invalid phone number format
fax send --to-num "invalid-number" --from-num +15559876543 --media-url https://example.com/document.pdf

# TC-014: Send fax with invalid from number format
fax send --to-num +15551234567 --from-num "invalid-number" --media-url https://example.com/document.pdf

# TC-015: Send fax with invalid media URL
fax send --to-num +15551234567 --from-num +15559876543 --media-url "not-a-valid-url"

# TC-016: Send fax with non-existent media URL
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/nonexistent.pdf

# TC-017: Send fax with non-PDF media URL
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/image.jpg

# TC-018: Send fax with international phone numbers
fax send --to-num +447123456789 --from-num +15559876543 --media-url https://example.com/document.pdf

# TC-019: Send fax with negative TTL
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --ttl -1

# TC-020: Send fax with very high TTL
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --ttl 10080

# TC-021: Send fax and monitor status (non-background)
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf
# Should show status polling until terminal state

# TC-022: Send fax with URL containing special characters
fax send --to-num +15551234567 --from-num +15559876543 --media-url "https://example.com/documents/test%20fax.pdf"

# TC-023: Send fax with URL containing query parameters
fax send --to-num +15551234567 --from-num +15559876543 --media-url "https://example.com/document.pdf?token=abc123"
```

### 2. List Commands
```bash
# TC-024: List all faxes
fax list

# TC-025: List all faxes in JSON format
fax list --json

# TC-026: List specific fax by ID
fax list --id FX1234567890abcdef1234567890abcdef

# TC-027: List specific fax by ID in JSON format
fax list --id FX1234567890abcdef1234567890abcdef --json

# TC-028: List only sent (outbound) faxes
fax list --sent

# TC-029: List only received (inbound) faxes
fax list --received

# TC-030: List sent faxes in JSON format
fax list --sent --json

# TC-031: List received faxes in JSON format
fax list --received --json

# TC-032: List faxes from specific number
fax list --from-num +15559876543

# TC-033: List faxes to specific number
fax list --to-num +15551234567

# TC-034: List faxes created after specific date
fax list --date-created-after 2023-01-01

# TC-035: List faxes created before specific date
fax list --date-created-before 2023-12-31

# TC-036: List faxes within date range
fax list --date-created-after 2023-01-01 --date-created-before 2023-01-31

# TC-037: List faxes with page size limit
fax list --page-size 10

# TC-038: List faxes with multiple filters
fax list --from-num +15559876543 --date-created-after 2023-01-01 --sent

# TC-039: List faxes with all filters and JSON output
fax list --from-num +15559876543 --to-num +15551234567 --date-created-after 2023-01-01 --date-created-before 2023-12-31 --page-size 25 --json

# TC-040: List non-existent fax by ID
fax list --id FX00000000000000000000000000000000

# TC-041: List with invalid fax ID format
fax list --id "invalid-fax-id"

# TC-042: List faxes when no faxes exist
fax list --sent
fax list --received

# TC-043: List with invalid date format
fax list --date-created-after "invalid-date"

# TC-044: List with future date (should return empty)
fax list --date-created-after 2099-01-01
```

### 3. Get Commands (Alias for List with ID)
```bash
# TC-045: Get specific fax by ID
fax get --id FX1234567890abcdef1234567890abcdef

# TC-046: Get specific fax by ID in JSON format
fax get --id FX1234567890abcdef1234567890abcdef --json

# TC-047: Get fax without ID (should fail)
fax get

# TC-048: Get non-existent fax by ID
fax get --id FX00000000000000000000000000000000

# TC-049: Get fax with invalid ID format
fax get --id "invalid-fax-id"

# TC-050: Verify get and list --id produce identical results
fax get --id FX1234567890abcdef1234567890abcdef > get_result.tmp
fax list --id FX1234567890abcdef1234567890abcdef > list_result.tmp
diff get_result.tmp list_result.tmp
rm get_result.tmp list_result.tmp
```

### 4. Update Commands
```bash
# TC-051: Update fax status to canceled
fax update --id FX1234567890abcdef1234567890abcdef --status canceled

# TC-052: Update fax without ID (should fail)
fax update --status canceled

# TC-053: Update fax without status (should fail)
fax update --id FX1234567890abcdef1234567890abcdef

# TC-054: Update fax with invalid status (should fail)
fax update --id FX1234567890abcdef1234567890abcdef --status completed

# TC-055: Update fax with non-existent ID
fax update --id FX00000000000000000000000000000000 --status canceled

# TC-056: Update already completed fax (should fail)
fax update --id <completed_fax_id> --status canceled

# TC-057: Update already canceled fax (should fail)
fax update --id <canceled_fax_id> --status canceled
```

### 5. Cancel Commands (Alias for Update --status canceled)
```bash
# TC-058: Cancel fax by ID
fax cancel --id FX1234567890abcdef1234567890abcdef

# TC-059: Cancel fax without ID (should fail)
fax cancel

# TC-060: Cancel non-existent fax
fax cancel --id FX00000000000000000000000000000000

# TC-061: Cancel with invalid ID format
fax cancel --id "invalid-fax-id"

# TC-062: Cancel already completed fax (should fail)
fax cancel --id <completed_fax_id>

# TC-063: Cancel already canceled fax (should fail)
fax cancel --id <canceled_fax_id>

# TC-064: Verify cancel and update --status canceled produce identical results
fax cancel --id FX1234567890abcdef1234567890abcdef
fax update --id FX1234567890abcdef1234567890abcdef --status canceled
```

### 6. Delete Commands
```bash
# TC-065: Delete fax with confirmation prompt
fax delete --id FX1234567890abcdef1234567890abcdef

# TC-066: Delete fax with force flag (no confirmation)
fax delete --id FX1234567890abcdef1234567890abcdef --force

# TC-067: Delete fax without ID (should fail)
fax delete

# TC-068: Delete fax with invalid ID (should fail)
fax delete --id "invalid-fax-id" --force

# TC-069: Delete fax with non-existent ID (should fail)
fax delete --id FX00000000000000000000000000000000 --force

# TC-070: Cancel delete operation (choose 'no' when prompted)
fax delete --id FX1234567890abcdef1234567890abcdef

# TC-071: Delete with case variations in confirmation
fax delete --id FX1234567890abcdef1234567890abcdef  # Test 'Y', 'y', 'yes', 'Yes'

# TC-072: Delete with invalid confirmation responses
fax delete --id FX1234567890abcdef1234567890abcdef  # Test 'maybe', '1', 'sure'
```

### 7. Media List Commands
```bash
# TC-073: List media for a fax
fax media list --fax-id FX1234567890abcdef1234567890abcdef

# TC-074: List media for a fax in JSON format
fax media list --fax-id FX1234567890abcdef1234567890abcdef --json

# TC-075: List media without fax ID (should fail)
fax media list

# TC-076: List media for non-existent fax
fax media list --fax-id FX00000000000000000000000000000000

# TC-077: List media for fax with no media
fax media list --fax-id <fax_with_no_media>

# TC-078: List media with invalid fax ID format
fax media list --fax-id "invalid-fax-id"
```

### 8. Media Get Commands
```bash
# TC-079: Get specific media for a fax
fax media get --fax-id FX1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef

# TC-080: Get specific media in JSON format
fax media get --fax-id FX1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef --json

# TC-081: Get media without fax ID (should fail)
fax media get --media-id ME1234567890abcdef1234567890abcdef

# TC-082: Get media without media ID (should fail)
fax media get --fax-id FX1234567890abcdef1234567890abcdef

# TC-083: Get media with non-existent fax ID
fax media get --fax-id FX00000000000000000000000000000000 --media-id ME1234567890abcdef1234567890abcdef

# TC-084: Get media with non-existent media ID
fax media get --fax-id FX1234567890abcdef1234567890abcdef --media-id ME00000000000000000000000000000000

# TC-085: Get media with invalid ID formats
fax media get --fax-id "invalid" --media-id "invalid"
```

### 9. Media Delete Commands
```bash
# TC-086: Delete media with confirmation prompt
fax media delete --fax-id FX1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef

# TC-087: Delete media with force flag
fax media delete --fax-id FX1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef --force

# TC-088: Delete media without fax ID (should fail)
fax media delete --media-id ME1234567890abcdef1234567890abcdef --force

# TC-089: Delete media without media ID (should fail)
fax media delete --fax-id FX1234567890abcdef1234567890abcdef --force

# TC-090: Delete media with non-existent IDs
fax media delete --fax-id FX00000000000000000000000000000000 --media-id ME00000000000000000000000000000000 --force

# TC-091: Cancel media delete operation
fax media delete --fax-id FX1234567890abcdef1234567890abcdef --media-id ME1234567890abcdef1234567890abcdef
# Choose 'no' when prompted
```

### 10. Logs Commands
```bash
# TC-092: List fax logs
fax logs list

# TC-093: List fax logs in JSON format
fax logs list --json

# TC-094: Get specific fax log by ID
fax logs get --id <log_id>

# TC-095: Get specific fax log by ID in JSON format
fax logs get --id <log_id> --json

# TC-096: Get non-existent fax log by ID
fax logs get --id 00000000-0000-0000-0000-000000000000

# TC-097: Get fax log without ID (should fail)
fax logs get

# TC-098: Logs subcommand without action (should show help)
fax logs

# TC-099: Logs subcommand help
fax logs --help
fax logs list --help
fax logs get --help
```

### 11. Edge Cases & Error Handling
```bash
# TC-100: Invalid command (should show help)
fax invalid_command

# TC-093: No subcommand (should show help)
fax

# TC-094: Help command
fax --help

# TC-095: Help for specific subcommands
fax send --help
fax list --help
fax get --help
fax update --help
fax cancel --help
fax delete --help
fax media --help
fax media list --help
fax media get --help
fax media delete --help

# TC-096: Phone numbers with extensions
fax send --to-num "+15551234567;ext=123" --from-num +15559876543 --media-url https://example.com/document.pdf

# TC-097: Phone numbers with special characters
fax send --to-num "+1(555)123-4567" --from-num +15559876543 --media-url https://example.com/document.pdf

# TC-098: Multiple concurrent send operations
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/doc1.pdf --background &
fax send --to-num +15551234568 --from-num +15559876543 --media-url https://example.com/doc2.pdf --background &
wait

# TC-099: Very long media URL
fax send --to-num +15551234567 --from-num +15559876543 --media-url "https://example.com/$(python3 -c "print('a' * 500)").pdf"

# TC-100: Fax SID boundary testing
fax get --id "$(python3 -c "print('FX' + 'a' * 32)")"
fax get --id "FX1234567890abcdef1234567890ABCDEF"  # Test case sensitivity

# TC-101: Date filtering with various formats
fax list --date-created-after "2023-01-01T00:00:00Z"
fax list --date-created-after "01/01/2023"
fax list --date-created-before "2023-12-31T23:59:59Z"

# TC-102: Combining sent/received filters (should use last one or error)
fax list --sent --received
```

### 11. Integration Tests
```bash
# TC-103: Full fax lifecycle
# Send -> Get (verify) -> Cancel/Update -> Get (verify changes) -> Delete
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --background
fax get --id <new_fax_sid>
fax cancel --id <new_fax_sid>
fax get --id <new_fax_sid>
fax delete --id <new_fax_sid> --force

# TC-104: Send and monitor fax progress (non-background)
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf
# Monitor status changes through polling

# TC-105: Test status callback functionality
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --status-callback https://example.com/fax-status --background
# Monitor callback logs to verify status updates

# TC-106: Test fax with different quality settings
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --quality standard --background
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --quality fine --background
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --quality superfine --background

# TC-107: Test fax filtering by direction
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --background
fax list --sent  # Should include the new fax
fax list --received  # Should not include the new fax

# TC-108: Test fax media workflow
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --background
fax get --id <fax_sid>  # Get fax details
fax media list --fax-id <fax_sid>  # List associated media
fax media get --fax-id <fax_sid> --media-id <media_sid>  # Get media details

# TC-109: Bulk fax operations
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/doc1.pdf --background
fax send --to-num +15551234568 --from-num +15559876543 --media-url https://example.com/doc2.pdf --background
fax send --to-num +15551234569 --from-num +15559876543 --media-url https://example.com/doc3.pdf --background
fax list --sent --json  # Verify all created
fax list --from-num +15559876543  # Filter by sender

# TC-110: Test TTL functionality
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/document.pdf --ttl 1 --background
# Wait for TTL to expire and verify fax behavior

# TC-111: Cancel fax during sending
fax send --to-num +15551234567 --from-num +15559876543 --media-url https://example.com/large-document.pdf --background
fax cancel --id <fax_sid>  # Cancel while still queued/sending
fax get --id <fax_sid>  # Verify canceled status

# TC-112: Test date range filtering
fax list --date-created-after 2023-01-01 --date-created-before 2023-12-31 --json
fax list --date-created-after $(date -v-7d +%Y-%m-%d)  # Last 7 days
fax list --date-created-before $(date +%Y-%m-%d)  # Up to today
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, etc.)
- **Data Validation**: Verify fax data matches input (from, to, media_url, quality, status)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **Fax State**: Verify fax status transitions (queued -> sending -> delivered/failed/busy/no-answer)
- **Callback Verification**: For status callbacks, verify events are triggered correctly

## Test Environment Setup
```bash
# Save original faxes for reference
fax list --json > original_faxes.json

# Get available faxes for testing
fax list --json | jq -r '.[].sid'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# Verify test phone numbers and PDF URLs
echo "From Number: +15559876543"  # Replace with actual SignalWire number
echo "To Numbers: +15551234567, +15551234568, +15551234569"  # Replace with test fax numbers
echo "Test PDF: https://example.com/document.pdf"  # Replace with accessible PDF URL

# After testing, clean up test faxes
fax list --json | jq -r '.[] | select(.from == "+15559876543") | .sid' | while read sid; do
    fax delete --id $sid --force
done
```

## Notes
- Faxes are billable resources - exercise caution with send operations
- Fax delivery depends on recipient fax machine availability
- Quality settings affect transmission time and clarity (superfine is slowest but clearest)
- Status polling occurs every 3 seconds in non-background mode (up to ~10 minutes timeout)
- Terminal statuses are: delivered, busy, failed, no-answer, canceled
- The Compatibility API uses form-encoded payloads (not JSON)
- Fax SIDs follow the format: FXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
- Media SIDs follow the format: MExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
- Phone numbers should be in E.164 format (+1XXXXXXXXXX for US/Canada)
- Media URL must point to a valid, accessible PDF file
- URL encoding is handled automatically for URLs with special characters
- Received faxes persist indefinitely until explicitly deleted
- Media files are separate resources that must be deleted independently
- The --background flag skips status polling and returns immediately

## API Endpoint Reference
- **Base URL**: `api/laml/2010-04-01/Accounts/{AccountSid}/Faxes`
- **Media URL**: `api/laml/2010-04-01/Accounts/{AccountSid}/Faxes/{FaxSid}/Media`
- **Methods**: GET (list/retrieve), POST (create/update), DELETE (delete)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/x-www-form-urlencoded (Compatibility API)
- **Payload Format**: Form-encoded (e.g., `To=value&From=value&MediaUrl=value`)
- **Delete Response**: 204 No Content on successful deletion

## Command Reference
```
fax send -t TO -f FROM -m MEDIA_URL [-q QUALITY] [--status-callback URL] [--ttl MINUTES] [-b]
fax list [-i ID] [-j] [--sent] [--received] [--from-num NUM] [--to-num NUM] [--date-created-after DATE] [--date-created-before DATE] [--page-size N]
fax get -i ID [-j]
fax update -i ID -s STATUS
fax cancel -i ID
fax delete -i ID [-f]
fax media list --fax-id ID [-j]
fax media get --fax-id ID --media-id ID [-j]
fax media delete --fax-id ID --media-id ID [-f]
```

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the fax command.
