# Number Group Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Test phone numbers available for number group assignment
- Network connectivity to SignalWire API

## Test Cases

### 1. List Commands
```bash
# TC-001: List all number groups
number_group list

# TC-002: List number groups in JSON format
number_group list --json

# TC-003: List specific number group by ID
number_group list --id <group_id>

# TC-004: Search number groups by name
number_group list --name testgroup

# TC-005: Search with multi-word name
number_group list --name "test group name"

# TC-006: List non-existent number group
number_group list --id nonexistent123
```

### 2. Create Commands
```bash
# TC-007: Create basic number group
number_group create --name testgroup1

# TC-008: Create number group with sticky sender enabled
number_group create --name testgroup2 --sticky-sender true

# TC-009: Create number group with sticky sender disabled
number_group create --name testgroup3 --sticky-sender false

# TC-010: Create with multi-word name
number_group create --name "Test Group Four"

# TC-011: Create without required name (should fail)
number_group create --sticky-sender true

# TC-012: Create with invalid sticky-sender value (should fail)
number_group create --name testgroup5 --sticky-sender invalid
```

### 3. Update Commands
```bash
# TC-013: Update number group name
number_group update --id <group_id> --name newgroupname

# TC-014: Update sticky sender setting to true
number_group update --id <group_id> --sticky-sender true

# TC-015: Update sticky sender setting to false
number_group update --id <group_id> --sticky-sender false

# TC-016: Update both name and sticky sender
number_group update --id <group_id> --name "Updated Group Name" --sticky-sender true

# TC-017: Update with multi-word name
number_group update --id <group_id> --name "New Multi Word Name"

# TC-018: Update without ID (should fail)
number_group update --name somegroup

# TC-019: Update non-existent number group (should fail)
number_group update --id nonexistent123 --name testgroup

# TC-020: Update with invalid sticky-sender value (should fail)
number_group update --id <group_id> --sticky-sender invalid
```

### 4. Delete Commands
```bash
# TC-021: Delete with confirmation prompt
number_group delete --id <group_id>

# TC-022: Delete with force flag (no confirmation)
number_group delete --id <group_id> --force

# TC-023: Delete without ID (should fail)
number_group delete

# TC-024: Delete non-existent number group (should fail)
number_group delete --id nonexistent123

# TC-025: Cancel delete operation (choose 'no' when prompted)
number_group delete --id <group_id>
```

### 5. Edge Cases & Error Handling
```bash
# TC-026: Invalid command (should show help)
number_group invalid_command

# TC-027: No subcommand (should show help)
number_group

# TC-028: Very long group name (test limits)
number_group create --name $(python3 -c "print('a'*1000)")

# TC-029: Special characters in group name
number_group create --name "test@group.com"

# TC-030: Empty name (should fail)
number_group create --name ""

# TC-031: Name with only whitespace (should fail)
number_group create --name "   "

# TC-032: Unicode characters in name
number_group create --name "测试组"
```

### 6. Integration Tests
```bash
# TC-033: Full lifecycle test
# Create -> List -> Update -> List -> Delete
number_group create --name lifecycle_test --sticky-sender true
number_group list --name lifecycle_test
number_group update --id <created_id> --name "Updated Lifecycle Test" --sticky-sender false
number_group list --id <created_id>
number_group delete --id <created_id> --force

# TC-034: Multiple groups management
number_group create --name group1 --sticky-sender true
number_group create --name group2 --sticky-sender false
number_group create --name group3
number_group list --json  # Verify all groups exist
number_group delete --id <group1_id> --force
number_group delete --id <group2_id> --force
number_group delete --id <group3_id> --force

# TC-035: Search functionality verification
number_group create --name "search test alpha"
number_group create --name "search test beta"
number_group create --name "different name"
number_group list --name "search test"  # Should return first two
number_group list --name alpha  # Should return first one
number_group list --name nonexistent  # Should return empty/error
# Cleanup
number_group delete --id <alpha_id> --force
number_group delete --id <beta_id> --force
number_group delete --id <different_id> --force
```

### 7. Sticky Sender Functionality Tests
```bash
# TC-036: Test sticky sender behavior variations
number_group create --name sticky_true --sticky-sender true
number_group create --name sticky_false --sticky-sender false
number_group create --name sticky_default  # Should default to false

# Verify settings
number_group list --json | grep -A5 -B5 sticky_

# Test updates between true/false
number_group update --id <sticky_true_id> --sticky-sender false
number_group update --id <sticky_false_id> --sticky-sender true
number_group list --json | grep -A5 -B5 sticky_

# Cleanup
number_group delete --id <sticky_true_id> --force
number_group delete --id <sticky_false_id> --force
number_group delete --id <sticky_default_id> --force
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes
- **Data Validation**: Verify created/updated data matches input
- **Sticky Sender Validation**: Ensure sticky-sender setting is correctly applied

## Test Environment Setup
```bash
# Save original number groups for cleanup
number_group list --json > original_number_groups.json

# After testing, cleanup test groups
# (Remove any number groups created during testing)

# Verify no test groups remain
number_group list --json | grep -i test
```

## Notes
- Number groups are used for organizing phone numbers within a SignalWire project
- Sticky sender determines if outbound calls from the group use a consistent From number
- Default sticky-sender value is 'false' if not specified
- Group names should be descriptive and unique within the project
- Deleting a number group may affect associated phone numbers (verify behavior)
- Always test both true/false values for sticky-sender to ensure proper functionality

## API Endpoint Reference
- **Base URL**: `api/relay/rest/number_groups`
- **Methods**: GET (list), POST (create), PUT (update), DELETE (delete)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the number_group command.