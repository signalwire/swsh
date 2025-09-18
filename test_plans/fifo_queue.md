# FIFO Queue Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Compatibility API
- Valid project/account with Voice scope permissions
- Ability to create and manage FIFO queues

## Test Cases

### 1. List Commands
```bash
# TC-001: List all FIFO queues (detailed format - DEFAULT)
fifo_queue list

# TC-002: List FIFO queues in JSON format
fifo_queue list --json

# TC-003: List specific FIFO queue by ID
fifo_queue list --id <queue_sid>

# TC-004: List non-existent FIFO queue by ID
fifo_queue list --id nonexistent-123-456

# TC-005: List with invalid queue ID format
fifo_queue list --id invalid_id_format

# TC-006: List when no queues exist
fifo_queue list

# TC-007: List with very long queue ID
fifo_queue list --id "$(python3 -c "print('a'*1000)")"

# TC-008: List with special characters in ID
fifo_queue list --id "test@queue#id"
```

### 2. Create Commands
```bash
# TC-009: Create FIFO queue with single word name
fifo_queue create --name TestQueue

# TC-010: Create FIFO queue with multi-word name
fifo_queue create --name "Test Queue Name"

# TC-011: Create FIFO queue with default maxsize (5)
fifo_queue create --name "Default Max Queue"

# TC-012: Create FIFO queue with custom maxsize
fifo_queue create --name "Custom Max Queue" --maxsize 10

# TC-013: Create FIFO queue with maxsize 1
fifo_queue create --name "Min Size Queue" --maxsize 1

# TC-014: Create FIFO queue with maxsize 100
fifo_queue create --name "Large Queue" --maxsize 100

# TC-015: Create FIFO queue with special characters in name
fifo_queue create --name "Test-Queue_2023"

# TC-016: Create FIFO queue with Unicode characters
fifo_queue create --name "测试队列"

# TC-017: Create FIFO queue with very long name
fifo_queue create --name "$(python3 -c "print('a'*100)")"

# TC-018: Create FIFO queue without name (should fail)
fifo_queue create

# TC-019: Create FIFO queue with empty name (should fail)
fifo_queue create --name ""

# TC-020: Create FIFO queue with only whitespace (should fail)
fifo_queue create --name "   "

# TC-021: Create FIFO queue with maxsize 0 (should test API behavior)
fifo_queue create --name "Zero Max Queue" --maxsize 0

# TC-022: Create FIFO queue with negative maxsize (should fail)
fifo_queue create --name "Negative Max Queue" --maxsize -1

# TC-023: Create FIFO queue with non-numeric maxsize (should fail)
fifo_queue create --name "Invalid Max Queue" --maxsize invalid

# TC-024: Create FIFO queue with URL-encoded characters
fifo_queue create --name "Test Queue@2023"

# TC-025: Create multiple FIFO queues with similar names
fifo_queue create --name "Test Queue 1"
fifo_queue create --name "Test Queue 2"
fifo_queue create --name "Test Queue 3"
```

### 3. Update Commands
```bash
# TC-026: Update FIFO queue name by ID
fifo_queue update --id <queue_sid> --name "Updated Queue Name"

# TC-027: Update FIFO queue maxsize by ID
fifo_queue update --id <queue_sid> --maxsize 15

# TC-028: Update both name and maxsize
fifo_queue update --id <queue_sid> --name "Updated Name and Size" --maxsize 20

# TC-029: Update FIFO queue with multi-word name
fifo_queue update --id <queue_sid> --name "Updated Multi Word Name"

# TC-030: Update FIFO queue with special characters
fifo_queue update --id <queue_sid> --name "Updated-Name_2023"

# TC-031: Update FIFO queue with Unicode characters
fifo_queue update --id <queue_sid> --name "更新的队列"

# TC-032: Update FIFO queue with very long name
fifo_queue update --id <queue_sid> --name "$(python3 -c "print('b'*100)")"

# TC-033: Update FIFO queue without ID (should fail)
fifo_queue update --name "Some Name"

# TC-034: Update FIFO queue without any parameters (should fail)
fifo_queue update --id <queue_sid>

# TC-035: Update FIFO queue with invalid ID (should fail)
fifo_queue update --id invalid-123-456 --name "Test"

# TC-036: Update FIFO queue with non-existent ID (should fail)
fifo_queue update --id QU00000000000000000000000000000000 --name "Test"

# TC-037: Update FIFO queue with empty name (should fail)
fifo_queue update --id <queue_sid> --name ""

# TC-038: Update FIFO queue with only whitespace (should fail)
fifo_queue update --id <queue_sid> --name "   "

# TC-039: Update FIFO queue with maxsize 0
fifo_queue update --id <queue_sid> --maxsize 0

# TC-040: Update FIFO queue with negative maxsize (should fail)
fifo_queue update --id <queue_sid> --maxsize -5

# TC-041: Update FIFO queue with non-numeric maxsize (should fail)
fifo_queue update --id <queue_sid> --maxsize invalid

# TC-042: Update FIFO queue back to original values
fifo_queue update --id <queue_sid> --name "Original Name" --maxsize 5
```

### 4. Delete Commands
```bash
# TC-043: Delete FIFO queue with confirmation prompt
fifo_queue delete --id <queue_sid>

# TC-044: Delete FIFO queue with force flag (no confirmation)
fifo_queue delete --id <queue_sid> --force

# TC-045: Delete FIFO queue without ID (should fail)
fifo_queue delete

# TC-046: Delete FIFO queue with invalid ID (should fail)
fifo_queue delete --id invalid-123-456 --force

# TC-047: Delete FIFO queue with non-existent ID (should fail)
fifo_queue delete --id QU00000000000000000000000000000000 --force

# TC-048: Cancel delete operation (choose 'no' when prompted)
fifo_queue delete --id <queue_sid>

# TC-049: Delete non-empty FIFO queue (should fail per API requirements)
fifo_queue delete --id <non_empty_queue_sid> --force

# TC-050: Delete empty FIFO queue (should succeed)
fifo_queue delete --id <empty_queue_sid> --force

# TC-051: Delete with case variations in confirmation
fifo_queue delete --id <queue_sid>  # Test 'Y', 'y', 'yes', 'Yes'

# TC-052: Delete with invalid confirmation responses
fifo_queue delete --id <queue_sid>  # Test 'maybe', '1', 'sure'
```

### 5. Edge Cases & Error Handling
```bash
# TC-053: Invalid command (should show help)
fifo_queue invalid_command

# TC-054: No subcommand (should show help)
fifo_queue

# TC-055: Help command
fifo_queue --help

# TC-056: Help for specific subcommands
fifo_queue create --help
fifo_queue update --help
fifo_queue list --help
fifo_queue delete --help

# TC-057: FIFO queue name with newlines
fifo_queue create --name $'Test\nQueue'

# TC-058: FIFO queue name with tabs
fifo_queue create --name $'Test\tQueue'

# TC-059: Multiple concurrent create operations
fifo_queue create --name "Concurrent1" &
fifo_queue create --name "Concurrent2" &
wait

# TC-060: URL encoding edge cases
fifo_queue create --name "Test%20Queue"
fifo_queue create --name "Test+Queue"
fifo_queue create --name "Test&Queue"

# TC-061: Case sensitivity tests
fifo_queue create --name "test"
fifo_queue create --name "Test"
fifo_queue create --name "TEST"

# TC-062: Maximum length name testing
fifo_queue create --name "$(python3 -c "print('TestQueue' * 50)")"

# TC-063: Special API characters
fifo_queue create --name "Test/Queue\\Path"
fifo_queue create --name "Test\"Queue\"Name"
fifo_queue create --name "Test'Queue'Name"

# TC-064: Maxsize boundary testing
fifo_queue create --name "MaxInt Queue" --maxsize 2147483647
fifo_queue create --name "Large Queue" --maxsize 999999
```

### 6. Integration Tests
```bash
# TC-065: Full FIFO queue lifecycle
# Create -> List (verify) -> Update -> List (verify changes) -> Delete
fifo_queue create --name "Lifecycle Test" --maxsize 8
fifo_queue list --id <new_queue_id>
fifo_queue update --id <new_queue_id> --name "Updated Lifecycle Test" --maxsize 12
fifo_queue list --id <new_queue_id>
fifo_queue delete --id <new_queue_id> --force

# TC-066: Create and verify in different output formats
fifo_queue create --name "Format Test" --maxsize 6
fifo_queue list --id <new_queue_id>
fifo_queue list --id <new_queue_id> --json

# TC-067: Update and verify changes persist
fifo_queue update --id <queue_sid> --name "Persistence Test" --maxsize 10
fifo_queue list --id <queue_sid>
fifo_queue list --id <queue_sid> --json

# TC-068: Multiple operations on same FIFO queue
fifo_queue create --name "Multi Op Test" --maxsize 5
fifo_queue update --id <new_queue_id> --name "Multi Op Test Updated"
fifo_queue update --id <new_queue_id> --maxsize 15
fifo_queue update --id <new_queue_id> --name "Multi Op Test Final" --maxsize 20
fifo_queue list --id <new_queue_id>

# TC-069: Test all output formatting consistency
fifo_queue list  # Detailed format
fifo_queue list --json  # JSON format
fifo_queue list --id <queue_sid>  # Single queue detailed
fifo_queue list --id <queue_sid> --json  # Single queue JSON

# TC-070: Bulk operations testing
fifo_queue create --name "Bulk Test 1" --maxsize 5
fifo_queue create --name "Bulk Test 2" --maxsize 10
fifo_queue create --name "Bulk Test 3" --maxsize 15
fifo_queue list --json  # Verify all created
fifo_queue delete --id <bulk1_id> --force
fifo_queue delete --id <bulk2_id> --force
fifo_queue delete --id <bulk3_id> --force
```

### 7. Maxsize Functionality Tests
```bash
# TC-071: Test maxsize behavior variations
fifo_queue create --name "max_default"  # Should default to 5
fifo_queue create --name "max_one" --maxsize 1
fifo_queue create --name "max_large" --maxsize 100

# Verify settings
fifo_queue list --json | grep -A10 -B5 max_

# Test updates between different maxsize values
fifo_queue update --id <max_one_id> --maxsize 50
fifo_queue update --id <max_large_id> --maxsize 3
fifo_queue list --json | grep -A10 -B5 max_

# Cleanup
fifo_queue delete --id <max_default_id> --force
fifo_queue delete --id <max_one_id> --force
fifo_queue delete --id <max_large_id> --force
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, etc.)
- **Data Validation**: Verify queue data matches input (friendly_name, max_size, sid, etc.)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior

## Test Environment Setup
```bash
# Save original FIFO queues for reference
fifo_queue list --json > original_fifo_queues.json

# Get available FIFO queues for testing
fifo_queue list --json | jq -r '.[] | .sid'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# After testing, clean up test FIFO queues
# (Note: Only delete empty queues - verify queue status before removing)
fifo_queue list --json | jq -r '.[] | select(.friendly_name | test("^Test|^Lifecycle|^Format|^Bulk")) | .sid' | while read sid; do
    fifo_queue delete --id $sid --force
done
```

## Notes
- FIFO queues are used for call queuing and management within SignalWire projects
- Only empty queues can be deleted (per API requirements)
- Default maxsize value is 5 if not specified during creation
- Maxsize determines the maximum number of calls that can wait in the queue
- Queue names should be descriptive and can contain Unicode characters
- The Compatibility API uses form-encoded payloads (not JSON)
- Queue SIDs follow the format: QUxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
- URL encoding is handled automatically for names with special characters
- Always verify queue changes after updates to ensure they were applied correctly
- Delete operations require confirmation unless --force flag is used

## API Endpoint Reference
- **Base URL**: `api/laml/2010-04-01/Accounts/{AccountSid}/Queues`
- **Methods**: GET (list/retrieve), POST (create/update), DELETE (delete)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/x-www-form-urlencoded (Compatibility API)
- **Payload Format**: Form-encoded (e.g., `FriendlyName=value&MaxSize=value`)
- **Delete Response**: 204 No Content on successful deletion

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the fifo_queue command.