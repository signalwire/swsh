# Project Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Compatibility API
- Valid project/account with subproject creation permissions

## Test Cases

### 1. List Commands
```bash
# TC-001: List all projects/accounts (detailed format - DEFAULT)
project list

# TC-002: List projects in JSON format
project list --json

# TC-003: List specific project by ID
project list --id <project_id>

# TC-004: Search projects by friendly name
project list --name "Main"

# TC-005: Search with multi-word friendly name
project list --name "Demo 2 Testing"

# TC-006: Search with quoted name containing spaces
project list --name "My Test Project"

# TC-007: List non-existent project by ID
project list --id nonexistent-123-456

# TC-008: Search for non-existent project by name
project list --name "NonExistentProject"

# TC-009: Search with partial name match
project list --name "Demo"

# TC-010: List with URL encoding test (special characters)
project list --name "Test@Project#1"
```

### 2. Create Commands
```bash
# TC-011: Create subproject with single word name
project create --name TestProject

# TC-012: Create subproject with multi-word name
project create --name "Test Project Name"

# TC-013: Create subproject with special characters
project create --name "Test-Project_2023"

# TC-014: Create subproject with Unicode characters
project create --name "测试项目"

# TC-015: Create subproject with very long name
project create --name "$(python3 -c "print('a'*100)")"

# TC-016: Create subproject without name (should fail)
project create

# TC-017: Create subproject with empty name (should fail)
project create --name ""

# TC-018: Create subproject with only whitespace (should fail)
project create --name "   "

# TC-019: Create subproject with URL-encoded characters
project create --name "Test Project@2023"

# TC-020: Create multiple subprojects with similar names
project create --name "Test 1"
project create --name "Test 2"
project create --name "Test 3"
```

### 3. Update Commands
```bash
# TC-021: Update project name by ID
project update --id <project_id> --name "Updated Name"

# TC-022: Update project with multi-word name
project update --id <project_id> --name "Updated Multi Word Name"

# TC-023: Update project with special characters
project update --id <project_id> --name "Updated-Name_2023"

# TC-024: Update project with Unicode characters
project update --id <project_id> --name "更新的项目"

# TC-025: Update project with very long name
project update --id <project_id> --name "$(python3 -c "print('b'*100)")"

# TC-026: Update project without ID (should fail)
project update --name "Some Name"

# TC-027: Update project without name (should fail)
project update --id <project_id>

# TC-028: Update project with invalid ID (should fail)
project update --id invalid-123-456 --name "Test"

# TC-029: Update project with non-existent ID (should fail)
project update --id 00000000-0000-0000-0000-000000000000 --name "Test"

# TC-030: Update project with empty name (should fail)
project update --id <project_id> --name ""

# TC-031: Update project with only whitespace (should fail)
project update --id <project_id> --name "   "

# TC-032: Update main project (parent account)
project update --id <main_project_id> --name "Updated Main Project"

# TC-033: Update subproject back to original name
project update --id <project_id> --name "Original Name"
```

### 4. Edge Cases & Error Handling
```bash
# TC-034: Invalid command (should show help)
project invalid_command

# TC-035: No subcommand (should show help)
project

# TC-036: Help command
project --help

# TC-037: Help for specific subcommand
project create --help
project update --help
project list --help

# TC-038: Very long project ID
project list --id "$(python3 -c "print('a'*1000)")"

# TC-039: Project ID with special characters
project list --id "test@project#id"

# TC-040: Project name with newlines
project create --name $'Test\nProject'

# TC-041: Project name with tabs
project create --name $'Test\tProject'

# TC-042: Multiple concurrent create operations
project create --name "Concurrent1" &
project create --name "Concurrent2" &
wait

# TC-043: URL encoding edge cases
project list --name "Test%20Project"
project list --name "Test+Project"
project list --name "Test&Project"

# TC-044: Case sensitivity tests
project list --name "test"
project list --name "Test"
project list --name "TEST"
```

### 5. Integration Tests
```bash
# TC-045: Full project lifecycle
# Create -> List (verify) -> Update -> List (verify changes)
project create --name "Lifecycle Test"
project list --name "Lifecycle Test"
project update --id <new_project_id> --name "Updated Lifecycle Test"
project list --id <new_project_id>

# TC-046: Create and verify in different output formats
project create --name "Format Test"
project list --name "Format Test"
project list --name "Format Test" --json

# TC-047: Update and verify changes persist
project update --id <project_id> --name "Persistence Test"
project list --id <project_id>
project list --id <project_id> --json

# TC-048: Multiple operations on same project
project create --name "Multi Op Test"
project update --id <new_project_id> --name "Multi Op Test Updated"
project update --id <new_project_id> --name "Multi Op Test Final"
project list --id <new_project_id>

# TC-049: Verify subproject vs main project handling
project list  # Should show all projects including main
project list --json  # Verify proper JSON structure

# TC-050: Test all output formatting consistency
project list  # Detailed format
project list --json  # JSON format
project list --id <project_id>  # Single project detailed
project list --id <project_id> --json  # Single project JSON
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 400, 404, etc.)
- **Data Validation**: Verify project data matches input (friendly_name, sid, etc.)
- **Error Messages**: For failure cases, verify proper error messages are shown

## Test Environment Setup
```bash
# Save original projects for reference
project list --json > original_projects.json

# Get available projects for testing
project list --json | jq -r '.[] | .sid'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# After testing, clean up test projects if needed
# (Note: Be careful with project deletion - verify test projects before removing)
```

## Notes
- Projects are billable resources - exercise caution with create operations
- Some projects may be main accounts that cannot be deleted
- Friendly name changes affect project identification
- The Compatibility API uses form-encoded payloads (not JSON)
- Project IDs are UUIDs in the format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
- URL encoding is handled automatically for names with special characters
- Main projects have `subproject: false`, subprojects have `subproject: true`
- Always verify project changes after updates to ensure they were applied correctly

## API Endpoint Reference
- **Base URL**: `api/laml/2010-04-01/Accounts`
- **Methods**: GET (list), POST (create/update)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/x-www-form-urlencoded (Compatibility API)
- **Payload Format**: Form-encoded (e.g., `FriendlyName=value`)

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the project command.