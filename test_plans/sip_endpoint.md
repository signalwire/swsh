  SIP Endpoint Command Test Plan

  Prerequisites

  - Valid SignalWire environment variables set
  - Test SIP endpoint credentials available
  - Network connectivity to SignalWire API

  Test Cases

  1. List Commands

  # TC-001: List all SIP endpoints
  sip_endpoint list

  # TC-002: List SIP endpoints in JSON format
  sip_endpoint list --json

  # TC-003: List specific SIP endpoint by ID
  sip_endpoint list --id <endpoint_id>

  # TC-004: Search SIP endpoints by username
  sip_endpoint list --name testuser

  # TC-005: Search with multi-word username
  sip_endpoint list --name "test user name"

  # TC-006: List non-existent endpoint
  sip_endpoint list --id nonexistent123

  2. Create Commands

  # TC-007: Create basic SIP endpoint
  sip_endpoint create -u testuser1 -p password123 -s +15551234567 -c "Test User"

  # TC-008: Create with optional parameters
  sip_endpoint create -u testuser2 -p password456 -s +15551234568 -c "Test User Two" --codecs OPUS G722 --encryption required

  # TC-009: Create with ciphers
  sip_endpoint create -u testuser3 -p password789 -s +15551234569 -c "Test User Three" --ciphers AES_256_CM_HMAC_SHA1_80

  # TC-010: Create without required username (should fail)
  sip_endpoint create -p password123 -s +15551234567 -c "Test User"

  # TC-011: Create without required password (should fail)
  sip_endpoint create -u testuser4 -s +15551234567 -c "Test User"

  # TC-012: Create without required send-as (should fail)
  sip_endpoint create -u testuser5 -p password123 -c "Test User"

  # TC-013: Create without required caller-id (should fail)
  sip_endpoint create -u testuser6 -p password123 -s +15551234567

  3. Update Commands

  # TC-014: Update SIP endpoint username
  sip_endpoint update --id <endpoint_id> -u newusername

  # TC-015: Update SIP endpoint password
  sip_endpoint update --id <endpoint_id> -p newpassword123

  # TC-016: Update multiple fields
  sip_endpoint update --id <endpoint_id> -u updateduser -p newpass456 --codecs PCMU PCMA

  # TC-017: Update with invalid encryption option (should fail)
  sip_endpoint update --id <endpoint_id> --encryption invalid

  # TC-018: Update without ID (should fail)
  sip_endpoint update -u someuser

  # TC-019: Update non-existent endpoint (should fail)
  sip_endpoint update --id nonexistent123 -u testuser

  4. Delete Commands

  # TC-020: Delete with confirmation prompt
  sip_endpoint delete --id <endpoint_id>

  # TC-021: Delete with force flag (no confirmation)
  sip_endpoint delete --id <endpoint_id> --force

  # TC-022: Delete without ID (should fail)
  sip_endpoint delete

  # TC-023: Delete non-existent endpoint (should fail)
  sip_endpoint delete --id nonexistent123

  # TC-024: Cancel delete operation (choose 'no' when prompted)
  sip_endpoint delete --id <endpoint_id>

  5. Edge Cases & Error Handling

  # TC-025: Invalid command (should show help)
  sip_endpoint invalid_command

  # TC-026: No subcommand (should show help)
  sip_endpoint

  # TC-027: Invalid codec option (should fail)
  sip_endpoint create -u test -p pass -s +1234 -c "Test" --codecs INVALID_CODEC

  # TC-028: Invalid cipher option (should fail)  
  sip_endpoint create -u test -p pass -s +1234 -c "Test" --ciphers INVALID_CIPHER

  # TC-029: Very long username (test limits)
  sip_endpoint create -u $(python3 -c "print('a'*1000)") -p pass -s +1234 -c "Test"

  # TC-030: Special characters in username
  sip_endpoint create -u "test@user.com" -p pass -s +1234 -c "Test User"

  6. Integration Tests

  # TC-031: Full lifecycle test
  # Create -> List -> Update -> List -> Delete
  sip_endpoint create -u lifecycle_test -p password123 -s +15559999999 -c "Lifecycle Test"
  sip_endpoint list --name lifecycle_test
  sip_endpoint update --id <created_id> -p newpassword456
  sip_endpoint list --id <created_id>
  sip_endpoint delete --id <created_id> --force

  Expected Results Template

  For each test case, document:
  - Expected Status: Success/Failure
  - Expected Output: Specific success/error messages
  - API Response: Expected HTTP status codes
  - Data Validation: Verify created/updated data matches input

  Test Environment Setup

  # Save original endpoints for cleanup
  sip_endpoint list --json > original_endpoints.json

  # After testing, cleanup test endpoints
  # (Remove any endpoints created during testing)

  This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the sip_endpoint command.