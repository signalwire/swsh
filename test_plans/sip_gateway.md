# SIP Gateway Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Fabric API
- Valid project/account with appropriate permissions

## Test Cases

### 1. List Commands
```bash
# TC-001: List all SIP Gateways
sip_gateway list

# TC-002: List all SIP Gateways in JSON format
sip_gateway list --json

# TC-003: List specific SIP Gateway by ID
sip_gateway list --id <gateway_id>

# TC-004: List specific SIP Gateway by ID in JSON format
sip_gateway list --id <gateway_id> --json

# TC-005: List non-existent SIP Gateway by ID
sip_gateway list --id 00000000-0000-0000-0000-000000000000

# TC-006: List with invalid ID format
sip_gateway list --id "invalid-id"

# TC-007: List when no gateways exist
sip_gateway list
```

### 2. Create Commands
```bash
# TC-008: Create SIP Gateway with name and URI only
sip_gateway create --name "Test Gateway" --uri "test@example.com"

# TC-009: Create SIP Gateway with all parameters
sip_gateway create --name "Full Gateway" --uri "full@example.com" --encryption required --codecs OPUS G722 PCMU --ciphers AES_256_CM_HMAC_SHA1_80

# TC-010: Create SIP Gateway with encryption optional
sip_gateway create --name "Optional Encryption" --uri "opt@example.com" --encryption optional

# TC-011: Create SIP Gateway with encryption forbidden
sip_gateway create --name "No Encryption" --uri "noenc@example.com" --encryption forbidden

# TC-012: Create SIP Gateway without name (should fail)
sip_gateway create --uri "test@example.com"

# TC-013: Create SIP Gateway without URI (should fail)
sip_gateway create --name "No URI Gateway"

# TC-014: Create SIP Gateway with multi-word name
sip_gateway create --name Test Gateway With Long Name --uri "longname@example.com"

# TC-015: Create SIP Gateway with single codec
sip_gateway create --name "Single Codec" --uri "single@example.com" --codecs OPUS

# TC-016: Create SIP Gateway with all codecs
sip_gateway create --name "All Codecs" --uri "allcodecs@example.com" --codecs OPUS G722 PCMU PCMA VP8 H264

# TC-017: Create SIP Gateway with single cipher
sip_gateway create --name "Single Cipher" --uri "cipher@example.com" --ciphers AEAD_AES_256_GCM_8

# TC-018: Create SIP Gateway with all ciphers
sip_gateway create --name "All Ciphers" --uri "allciphers@example.com" --ciphers AEAD_AES_256_GCM_8 AES_256_CM_HMAC_SHA1_80 AES_CM_128_HMAC_SHA1_80 AES_256_CM_HMAC_SHA1_32 AES_CM_128_HMAC_SHA1_32

# TC-019: Create SIP Gateway with invalid codec (should fail)
sip_gateway create --name "Invalid Codec" --uri "test@example.com" --codecs INVALID

# TC-020: Create SIP Gateway with invalid cipher (should fail)
sip_gateway create --name "Invalid Cipher" --uri "test@example.com" --ciphers INVALID

# TC-021: Create SIP Gateway with invalid encryption value (should fail)
sip_gateway create --name "Invalid Enc" --uri "test@example.com" --encryption invalid

# TC-022: Create SIP Gateway with special characters in name
sip_gateway create --name "Test Gateway (v1.0)" --uri "special@example.com"

# TC-023: Create SIP Gateway with complex URI
sip_gateway create --name "Complex URI" --uri "user:password@sip.example.com:5060"

# TC-024: Create SIP Gateway with IP-based URI
sip_gateway create --name "IP Gateway" --uri "user@192.168.1.100"

# TC-025: Create duplicate gateway name (verify behavior)
sip_gateway create --name "Duplicate Test" --uri "dup1@example.com"
sip_gateway create --name "Duplicate Test" --uri "dup2@example.com"
```

### 3. Update Commands
```bash
# TC-026: Update SIP Gateway name
sip_gateway update --id <gateway_id> --name "Updated Gateway Name"

# TC-027: Update SIP Gateway URI
sip_gateway update --id <gateway_id> --uri "updated@example.com"

# TC-028: Update SIP Gateway encryption
sip_gateway update --id <gateway_id> --encryption optional

# TC-029: Update SIP Gateway codecs
sip_gateway update --id <gateway_id> --codecs OPUS PCMU

# TC-030: Update SIP Gateway ciphers
sip_gateway update --id <gateway_id> --ciphers AES_256_CM_HMAC_SHA1_80 AES_CM_128_HMAC_SHA1_80

# TC-031: Update all SIP Gateway parameters
sip_gateway update --id <gateway_id> --name "Fully Updated" --uri "fullyupdated@example.com" --encryption required --codecs G722 --ciphers AEAD_AES_256_GCM_8

# TC-032: Update SIP Gateway without ID (should fail)
sip_gateway update --name "New Name"

# TC-033: Update SIP Gateway without any parameters (should show error)
sip_gateway update --id <gateway_id>

# TC-034: Update non-existent SIP Gateway
sip_gateway update --id 00000000-0000-0000-0000-000000000000 --name "Test"

# TC-035: Update with invalid ID format
sip_gateway update --id "invalid-id" --name "Test"

# TC-036: Update with multi-word name
sip_gateway update --id <gateway_id> --name Updated Multi Word Name

# TC-037: Update encryption to forbidden
sip_gateway update --id <gateway_id> --encryption forbidden

# TC-038: Update with invalid codec (should fail)
sip_gateway update --id <gateway_id> --codecs INVALID

# TC-039: Update with invalid cipher (should fail)
sip_gateway update --id <gateway_id> --ciphers INVALID
```

### 4. Delete Commands
```bash
# TC-040: Delete SIP Gateway with confirmation prompt
sip_gateway delete --id <gateway_id>

# TC-041: Delete SIP Gateway with force flag (no confirmation)
sip_gateway delete --id <gateway_id> --force

# TC-042: Delete SIP Gateway without ID (should fail)
sip_gateway delete

# TC-043: Delete non-existent SIP Gateway
sip_gateway delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-044: Delete with invalid ID format
sip_gateway delete --id "invalid-id" --force

# TC-045: Cancel delete operation (choose 'no' when prompted)
sip_gateway delete --id <gateway_id>

# TC-046: Delete with case variations in confirmation
sip_gateway delete --id <gateway_id>  # Test 'Y', 'y', 'yes', 'Yes'

# TC-047: Delete with invalid confirmation responses
sip_gateway delete --id <gateway_id>  # Test 'maybe', '1', 'sure'
```

### 5. Addresses Commands
```bash
# TC-048: List addresses for SIP Gateway
sip_gateway addresses --id <gateway_id>

# TC-049: List addresses for SIP Gateway in JSON format
sip_gateway addresses --id <gateway_id> --json

# TC-050: List addresses without gateway ID (should fail)
sip_gateway addresses

# TC-051: List addresses for non-existent gateway
sip_gateway addresses --id 00000000-0000-0000-0000-000000000000

# TC-052: List addresses for gateway with no addresses
sip_gateway addresses --id <gateway_with_no_addresses>

# TC-053: List addresses with invalid ID format
sip_gateway addresses --id "invalid-id"
```

### 6. Edge Cases & Error Handling
```bash
# TC-054: Invalid subcommand (should show help)
sip_gateway invalid_command

# TC-055: No subcommand (should show help)
sip_gateway

# TC-056: Help command
sip_gateway --help

# TC-057: Help for specific subcommands
sip_gateway list --help
sip_gateway create --help
sip_gateway update --help
sip_gateway delete --help
sip_gateway addresses --help

# TC-058: SIP Gateway ID boundary testing
sip_gateway list --id "$(python3 -c "print('a' * 100)")"

# TC-059: Name with leading/trailing whitespace
sip_gateway create --name "  Trimmed Name  " --uri "trim@example.com"

# TC-060: Very long gateway name
sip_gateway create --name "$(python3 -c "print('A' * 200)")" --uri "long@example.com"

# TC-061: Empty name
sip_gateway create --name "" --uri "empty@example.com"

# TC-062: URI with special characters
sip_gateway create --name "Special URI" --uri "user+tag@sip.example.com;transport=tcp"

# TC-063: URI without domain
sip_gateway create --name "No Domain" --uri "useronly"
```

### 7. Integration Tests
```bash
# TC-064: Full SIP Gateway lifecycle
# Create -> List -> Update -> List -> Delete
sip_gateway create --name "Lifecycle Test" --uri "lifecycle@example.com" --encryption optional --codecs OPUS
sip_gateway list --json  # Find the new gateway ID
sip_gateway list --id <created_id>
sip_gateway update --id <created_id> --name "Updated Lifecycle" --encryption required
sip_gateway list --id <created_id>
sip_gateway delete --id <created_id> --force

# TC-065: Create gateway and check addresses
sip_gateway create --name "Address Test" --uri "addrtest@example.com"
sip_gateway addresses --id <created_id>
sip_gateway delete --id <created_id> --force

# TC-066: Bulk gateway creation and cleanup
sip_gateway create --name "Bulk Test 1" --uri "bulk1@example.com"
sip_gateway create --name "Bulk Test 2" --uri "bulk2@example.com"
sip_gateway create --name "Bulk Test 3" --uri "bulk3@example.com"
sip_gateway list --json  # Verify all created
# Cleanup
sip_gateway delete --id <bulk1_id> --force
sip_gateway delete --id <bulk2_id> --force
sip_gateway delete --id <bulk3_id> --force

# TC-067: Verify JSON output structure
sip_gateway list --json | jq '.'
sip_gateway list --id <gateway_id> --json | jq '.'
sip_gateway addresses --id <gateway_id> --json | jq '.'

# TC-068: Create and immediately delete
sip_gateway create --name "Quick Delete" --uri "quickdel@example.com"
sip_gateway delete --id <just_created_id> --force

# TC-069: Update non-existent gateway while another exists
sip_gateway create --name "Existing Gateway" --uri "existing@example.com"
sip_gateway update --id 00000000-0000-0000-0000-000000000000 --name "Should Fail"
sip_gateway delete --id <existing_id> --force

# TC-070: Test all encryption modes
sip_gateway create --name "Enc Required" --uri "req@example.com" --encryption required
sip_gateway list --id <id> --json  # Verify encryption setting
sip_gateway delete --id <id> --force

sip_gateway create --name "Enc Optional" --uri "opt@example.com" --encryption optional
sip_gateway list --id <id> --json  # Verify encryption setting
sip_gateway delete --id <id> --force

sip_gateway create --name "Enc Forbidden" --uri "forb@example.com" --encryption forbidden
sip_gateway list --id <id> --json  # Verify encryption setting
sip_gateway delete --id <id> --force
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, 422, etc.)
- **Data Validation**: Verify gateway data matches input (name, uri, encryption, codecs, ciphers)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **JSON Structure**: For --json output, verify proper JSON formatting

## Test Environment Setup
```bash
# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
test -n "$REST_API_TOKEN" && echo "REST_API_TOKEN is set"

# Save original gateways for reference
sip_gateway list --json > original_gateways.json

# Get available gateways for testing
sip_gateway list --json | jq -r '.data[]? | .id'

# After testing, cleanup test gateways
# Delete only what this plan created, one id at a time (never by a name or number pattern):
sip_gateway delete --id <id> --force

# Cleanup bulk test gateways
# Delete only what this plan created, one id at a time (never by a name or number pattern):
sip_gateway delete --id <id> --force
```

## Notes
- SIP Gateways use the Fabric API at `api/fabric/resources/sip_gateways`
- Gateway IDs are UUIDs in the format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
- The API uses JSON payloads for create/update operations
- Delete operations return 204 No Content on success
- Addresses endpoint returns Fabric Addresses associated with the gateway
- SIP Gateways forward calls to external SIP addresses
- Encryption options: required, optional, forbidden
- Codecs available: OPUS, G722, PCMU, PCMA, VP8, H264
- Ciphers available: AEAD_AES_256_GCM_8, AES_256_CM_HMAC_SHA1_80, AES_CM_128_HMAC_SHA1_80, AES_256_CM_HMAC_SHA1_32, AES_CM_128_HMAC_SHA1_32

## API Endpoint Reference
- **Base URL**: `api/fabric/resources/sip_gateways`
- **List Gateways**: GET `/resources/sip_gateways`
- **Get Gateway**: GET `/resources/sip_gateways/:id`
- **Create Gateway**: POST `/resources/sip_gateways`
- **Update Gateway**: PATCH `/resources/sip_gateways/:id`
- **Delete Gateway**: DELETE `/resources/sip_gateways/:id`
- **List Addresses**: GET `/resources/sip_gateways/:id/addresses`
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/json

## Command Reference
```
sip_gateway list [-i ID] [-j]
sip_gateway create -n NAME -u URI [-e ENCRYPTION] [--codecs CODECS...] [--ciphers CIPHERS...]
sip_gateway update -i ID [-n NAME] [-u URI] [-e ENCRYPTION] [--codecs CODECS...] [--ciphers CIPHERS...]
sip_gateway delete -i ID [-f]
sip_gateway addresses -i ID [-j]
```
