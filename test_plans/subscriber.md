# Subscriber Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Fabric API
- Valid project/account with appropriate permissions

## Test Cases

### 1. Subscriber List Commands
```bash
# TC-001: List all Subscribers
subscriber list

# TC-002: List all Subscribers in JSON format
subscriber list --json

# TC-003: List specific Subscriber by ID
subscriber list --id <subscriber_id>

# TC-004: List specific Subscriber by ID in JSON format
subscriber list --id <subscriber_id> --json

# TC-005: List non-existent Subscriber by ID
subscriber list --id 00000000-0000-0000-0000-000000000000

# TC-006: List with invalid ID format
subscriber list --id "invalid-id"

# TC-007: List when no subscribers exist
subscriber list
```

### 2. Subscriber Create Commands
```bash
# TC-008: Create Subscriber with email and password only
subscriber create --email "test@example.com" --password "SecurePass123"

# TC-009: Create Subscriber with all parameters
subscriber create --email "full@example.com" --password "SecurePass123" \
    --first-name John --last-name Doe --display-name "John Doe" \
    --job-title "Engineer" --timezone "America/New_York" \
    --country "US" --region "NY" --company "Test Corp"

# TC-010: Create Subscriber with multi-word names
subscriber create --email "multi@example.com" --password "Pass123" \
    --first-name John William --last-name Doe Smith \
    --display-name John W Doe Smith

# TC-011: Create Subscriber without email (should fail)
subscriber create --password "Pass123"

# TC-012: Create Subscriber without password (should fail)
subscriber create --email "nopass@example.com"

# TC-013: Create Subscriber with invalid email format
subscriber create --email "invalid-email" --password "Pass123"

# TC-014: Create Subscriber with special characters in name
subscriber create --email "special@example.com" --password "Pass123" \
    --first-name "José" --last-name "O'Brien"

# TC-015: Create Subscriber with minimal parameters
subscriber create -e "min@example.com" -p "Pass123"

# TC-016: Create duplicate Subscriber (same email)
subscriber create --email "duplicate@example.com" --password "Pass123"
subscriber create --email "duplicate@example.com" --password "Pass456"

# TC-017: Create Subscriber with timezone
subscriber create --email "tz@example.com" --password "Pass123" \
    --timezone "Europe/London"

# TC-018: Create Subscriber with all optional fields
subscriber create --email "optional@example.com" --password "Pass123" \
    --first-name Test --last-name User --display-name "Test User" \
    --job-title "QA Engineer" --company "Testing Inc"
```

### 3. Subscriber Update Commands
```bash
# TC-019: Update Subscriber email
subscriber update --id <subscriber_id> --email "newemail@example.com"

# TC-020: Update Subscriber password
subscriber update --id <subscriber_id> --password "NewPass456"

# TC-021: Update Subscriber first name
subscriber update --id <subscriber_id> --first-name Jane

# TC-022: Update Subscriber last name
subscriber update --id <subscriber_id> --last-name Smith

# TC-023: Update Subscriber display name
subscriber update --id <subscriber_id> --display-name "Jane Smith"

# TC-024: Update Subscriber job title
subscriber update --id <subscriber_id> --job-title "Senior Engineer"

# TC-025: Update Subscriber timezone
subscriber update --id <subscriber_id> --timezone "America/Los_Angeles"

# TC-026: Update Subscriber country and region
subscriber update --id <subscriber_id> --country "CA" --region "ON"

# TC-027: Update Subscriber company
subscriber update --id <subscriber_id> --company "New Company Inc"

# TC-028: Update all Subscriber parameters
subscriber update --id <subscriber_id> --email "updated@example.com" \
    --first-name Updated --last-name User --display-name "Updated User" \
    --job-title "Manager" --timezone "UTC" --country "UK" --region "London"

# TC-029: Update Subscriber without ID (should fail)
subscriber update --email "noid@example.com"

# TC-030: Update Subscriber without any parameters (should fail)
subscriber update --id <subscriber_id>

# TC-031: Update non-existent Subscriber
subscriber update --id 00000000-0000-0000-0000-000000000000 --email "test@example.com"

# TC-032: Update with invalid ID format
subscriber update --id "invalid-id" --email "test@example.com"
```

### 4. Subscriber Delete Commands
```bash
# TC-033: Delete Subscriber with confirmation prompt
subscriber delete --id <subscriber_id>

# TC-034: Delete Subscriber with force flag
subscriber delete --id <subscriber_id> --force

# TC-035: Delete Subscriber without ID (should fail)
subscriber delete

# TC-036: Delete non-existent Subscriber
subscriber delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-037: Delete with invalid ID format
subscriber delete --id "invalid-id" --force

# TC-038: Cancel delete operation (choose 'no' when prompted)
subscriber delete --id <subscriber_id>

# TC-039: Delete with case variations in confirmation
subscriber delete --id <subscriber_id>  # Test 'Y', 'y', 'yes', 'Yes'
```

### 5. Subscriber Addresses Commands
```bash
# TC-040: List addresses for Subscriber
subscriber addresses --id <subscriber_id>

# TC-041: List addresses for Subscriber in JSON format
subscriber addresses --id <subscriber_id> --json

# TC-042: List addresses without subscriber ID (should fail)
subscriber addresses

# TC-043: List addresses for non-existent subscriber
subscriber addresses --id 00000000-0000-0000-0000-000000000000

# TC-044: List addresses for subscriber with no addresses
subscriber addresses --id <subscriber_with_no_addresses>
```

### 6. Token Create Commands
```bash
# TC-045: Create Subscriber Token with reference and password
subscriber token create --reference "test@example.com" --password "Pass123"

# TC-046: Create Subscriber Token with application ID
subscriber token create --reference "test@example.com" --password "Pass123" \
    --application-id "app-123"

# TC-047: Create Subscriber Token in JSON format
subscriber token create --reference "test@example.com" --password "Pass123" --json

# TC-048: Create Subscriber Token without reference (should fail)
subscriber token create --password "Pass123"

# TC-049: Create Subscriber Token without password (should fail)
subscriber token create --reference "test@example.com"

# TC-050: Create Subscriber Token with invalid credentials
subscriber token create --reference "nonexistent@example.com" --password "WrongPass"
```

### 7. Token Guest Commands
```bash
# TC-051: Create Guest Token
subscriber token guest

# TC-052: Create Guest Token with reference
subscriber token guest --reference "guest-user-123"

# TC-053: Create Guest Token in JSON format
subscriber token guest --json

# TC-054: Create Guest Token with custom reference
subscriber token guest --reference "custom-guest-ref"
```

### 8. Token Invite Commands
```bash
# TC-055: Create Invite Token with SAT
subscriber token invite --token "<subscriber_access_token>"

# TC-056: Create Invite Token in JSON format
subscriber token invite --token "<subscriber_access_token>" --json

# TC-057: Create Invite Token without token (should fail)
subscriber token invite

# TC-058: Create Invite Token with invalid token
subscriber token invite --token "invalid-token"
```

### 9. Token Refresh Commands
```bash
# TC-059: Refresh Token
subscriber token refresh --token "<refresh_token>"

# TC-060: Refresh Token in JSON format
subscriber token refresh --token "<refresh_token>" --json

# TC-061: Refresh Token without token (should fail)
subscriber token refresh

# TC-062: Refresh Token with invalid/expired token
subscriber token refresh --token "invalid-refresh-token"
```

### 10. SIP Endpoint List Commands
```bash
# TC-063: List all SIP Endpoints for Subscriber
subscriber sip list --id <subscriber_id>

# TC-064: List SIP Endpoints in JSON format
subscriber sip list --id <subscriber_id> --json

# TC-065: List specific SIP Endpoint
subscriber sip list --id <subscriber_id> --endpoint-id <endpoint_id>

# TC-066: List specific SIP Endpoint in JSON format
subscriber sip list --id <subscriber_id> --endpoint-id <endpoint_id> --json

# TC-067: List SIP Endpoints without subscriber ID (should fail)
subscriber sip list

# TC-068: List SIP Endpoints for non-existent subscriber
subscriber sip list --id 00000000-0000-0000-0000-000000000000

# TC-069: List non-existent SIP Endpoint
subscriber sip list --id <subscriber_id> --endpoint-id 00000000-0000-0000-0000-000000000000
```

### 11. SIP Endpoint Create Commands
```bash
# TC-070: Create SIP Endpoint with username and password
subscriber sip create --id <subscriber_id> --username "sipuser" --password "SipPass123"

# TC-071: Create SIP Endpoint with all parameters
subscriber sip create --id <subscriber_id> --username "fullsip" --password "SipPass123" \
    --send-as "+15551234567" --caller-id "Test User" \
    --encryption required --codecs OPUS G722 PCMU \
    --ciphers AES_256_CM_HMAC_SHA1_80

# TC-072: Create SIP Endpoint without subscriber ID (should fail)
subscriber sip create --username "sipuser" --password "SipPass123"

# TC-073: Create SIP Endpoint without username (should fail)
subscriber sip create --id <subscriber_id> --password "SipPass123"

# TC-074: Create SIP Endpoint without password (should fail)
subscriber sip create --id <subscriber_id> --username "sipuser"

# TC-075: Create SIP Endpoint with encryption optional
subscriber sip create --id <subscriber_id> --username "sipopt" --password "Pass123" \
    --encryption optional

# TC-076: Create SIP Endpoint with single codec
subscriber sip create --id <subscriber_id> --username "sipcodec" --password "Pass123" \
    --codecs OPUS

# TC-077: Create SIP Endpoint with all codecs
subscriber sip create --id <subscriber_id> --username "sipallcodec" --password "Pass123" \
    --codecs OPUS G722 PCMU PCMA VP8 H264

# TC-078: Create SIP Endpoint with all ciphers
subscriber sip create --id <subscriber_id> --username "sipcipher" --password "Pass123" \
    --ciphers AEAD_AES_256_GCM_8 AES_256_CM_HMAC_SHA1_80 AES_CM_128_HMAC_SHA1_80

# TC-079: Create SIP Endpoint with invalid codec (should fail)
subscriber sip create --id <subscriber_id> --username "sipbad" --password "Pass123" \
    --codecs INVALID

# TC-080: Create SIP Endpoint with invalid cipher (should fail)
subscriber sip create --id <subscriber_id> --username "sipbad" --password "Pass123" \
    --ciphers INVALID
```

### 12. SIP Endpoint Update Commands
```bash
# TC-081: Update SIP Endpoint username
subscriber sip update --id <subscriber_id> --endpoint-id <endpoint_id> --username "newuser"

# TC-082: Update SIP Endpoint password
subscriber sip update --id <subscriber_id> --endpoint-id <endpoint_id> --password "NewPass456"

# TC-083: Update SIP Endpoint send-as
subscriber sip update --id <subscriber_id> --endpoint-id <endpoint_id> --send-as "+15559876543"

# TC-084: Update SIP Endpoint caller-id
subscriber sip update --id <subscriber_id> --endpoint-id <endpoint_id> --caller-id "New Caller"

# TC-085: Update SIP Endpoint encryption
subscriber sip update --id <subscriber_id> --endpoint-id <endpoint_id> --encryption optional

# TC-086: Update SIP Endpoint codecs
subscriber sip update --id <subscriber_id> --endpoint-id <endpoint_id> --codecs G722 PCMA

# TC-087: Update SIP Endpoint ciphers
subscriber sip update --id <subscriber_id> --endpoint-id <endpoint_id> \
    --ciphers AES_CM_128_HMAC_SHA1_80

# TC-088: Update SIP Endpoint without subscriber ID (should fail)
subscriber sip update --endpoint-id <endpoint_id> --username "test"

# TC-089: Update SIP Endpoint without endpoint ID (should fail)
subscriber sip update --id <subscriber_id> --username "test"

# TC-090: Update SIP Endpoint without parameters (should fail)
subscriber sip update --id <subscriber_id> --endpoint-id <endpoint_id>

# TC-091: Update non-existent SIP Endpoint
subscriber sip update --id <subscriber_id> --endpoint-id 00000000-0000-0000-0000-000000000000 \
    --username "test"
```

### 13. SIP Endpoint Delete Commands
```bash
# TC-092: Delete SIP Endpoint with confirmation
subscriber sip delete --id <subscriber_id> --endpoint-id <endpoint_id>

# TC-093: Delete SIP Endpoint with force flag
subscriber sip delete --id <subscriber_id> --endpoint-id <endpoint_id> --force

# TC-094: Delete SIP Endpoint without subscriber ID (should fail)
subscriber sip delete --endpoint-id <endpoint_id>

# TC-095: Delete SIP Endpoint without endpoint ID (should fail)
subscriber sip delete --id <subscriber_id>

# TC-096: Delete non-existent SIP Endpoint
subscriber sip delete --id <subscriber_id> --endpoint-id 00000000-0000-0000-0000-000000000000 --force

# TC-097: Cancel SIP Endpoint delete (choose 'no')
subscriber sip delete --id <subscriber_id> --endpoint-id <endpoint_id>
```

### 14. Edge Cases & Error Handling
```bash
# TC-098: Invalid subcommand
subscriber invalid_command

# TC-099: No subcommand (should show help)
subscriber

# TC-100: Help command
subscriber --help

# TC-101: Help for specific subcommands
subscriber list --help
subscriber create --help
subscriber update --help
subscriber delete --help
subscriber addresses --help
subscriber token --help
subscriber token create --help
subscriber token guest --help
subscriber token invite --help
subscriber token refresh --help
subscriber sip --help
subscriber sip list --help
subscriber sip create --help
subscriber sip update --help
subscriber sip delete --help

# TC-102: Very long email address
subscriber create --email "$(python3 -c "print('a' * 200 + '@example.com')")" --password "Pass123"

# TC-103: Password with special characters
subscriber create --email "special@example.com" --password "P@ss!w0rd#$%^&*()"

# TC-104: Unicode characters in names
subscriber create --email "unicode@example.com" --password "Pass123" \
    --first-name "北京" --last-name "東京"
```

### 15. Integration Tests
```bash
# TC-105: Full Subscriber lifecycle
# Create -> List -> Update -> Get Token -> Create SIP -> List SIP -> Delete SIP -> Delete
subscriber create --email "lifecycle@example.com" --password "LifePass123" \
    --first-name Life --last-name Cycle
subscriber list --json  # Find the new subscriber ID
subscriber list --id <created_id>
subscriber update --id <created_id> --display-name "Lifecycle Test User"
subscriber token create --reference "lifecycle@example.com" --password "LifePass123"
subscriber sip create --id <created_id> --username "lifecyclesip" --password "SipPass123"
subscriber sip list --id <created_id>
subscriber sip delete --id <created_id> --endpoint-id <sip_id> --force
subscriber delete --id <created_id> --force

# TC-106: Token workflow
# Create Subscriber -> Get Token -> Refresh Token -> Create Invite
subscriber create --email "tokenflow@example.com" --password "TokenPass123"
subscriber token create --reference "tokenflow@example.com" --password "TokenPass123" --json
# Use the refresh_token from above
subscriber token refresh --token "<refresh_token>" --json
# Use the access_token for invite
subscriber token invite --token "<access_token>" --json
subscriber delete --id <subscriber_id> --force

# TC-107: SIP Endpoint full lifecycle
subscriber create --email "siplife@example.com" --password "SipLife123"
subscriber sip create --id <subscriber_id> --username "siplifesip" --password "SipPass" \
    --encryption required --codecs OPUS G722
subscriber sip list --id <subscriber_id> --json
subscriber sip update --id <subscriber_id> --endpoint-id <endpoint_id> \
    --encryption optional --codecs PCMU PCMA
subscriber sip list --id <subscriber_id> --endpoint-id <endpoint_id>
subscriber sip delete --id <subscriber_id> --endpoint-id <endpoint_id> --force
subscriber delete --id <subscriber_id> --force

# TC-108: Bulk subscriber creation and cleanup
subscriber create --email "bulk1@example.com" --password "Bulk123"
subscriber create --email "bulk2@example.com" --password "Bulk123"
subscriber create --email "bulk3@example.com" --password "Bulk123"
subscriber list --json
# Cleanup
subscriber delete --id <bulk1_id> --force
subscriber delete --id <bulk2_id> --force
subscriber delete --id <bulk3_id> --force

# TC-109: Verify JSON output structure
subscriber list --json | jq '.'
subscriber list --id <subscriber_id> --json | jq '.'
subscriber addresses --id <subscriber_id> --json | jq '.'
subscriber token create --reference "<email>" --password "<pass>" --json | jq '.'
subscriber sip list --id <subscriber_id> --json | jq '.'

# TC-110: Guest token workflow
subscriber token guest --json
subscriber token guest --reference "guest-123" --json
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 401, 404, 422, etc.)
- **Data Validation**: Verify subscriber/token/endpoint data matches input
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **Token Validity**: Verify tokens are properly formatted and can be used
- **JSON Structure**: For --json output, verify proper JSON formatting

## Test Environment Setup
```bash
# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
test -n "$REST_API_TOKEN" && echo "REST_API_TOKEN is set"

# Save original subscribers for reference
subscriber list --json > original_subscribers.json

# Get available subscribers for testing
subscriber list --json | jq -r '.data[]? | .id'

# After testing, cleanup test subscribers
# Delete only what this plan created, one id at a time (never by a name or number pattern):
subscriber delete --id <id> --force
```

## Notes
- Subscribers use the Fabric API at `api/fabric/resources/subscribers`
- Subscriber IDs are UUIDs in the format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
- The API uses JSON payloads for create/update operations
- Delete operations return 204 No Content on success
- Token endpoints have different base paths:
  - Subscriber tokens: `api/fabric/subscribers/tokens`
  - Guest tokens: `api/fabric/guests/tokens`
  - Invite tokens: `api/fabric/subscriber/invites`
  - Refresh tokens: `api/fabric/subscribers/tokens/refresh`
- SIP Endpoints are nested under subscribers: `/subscribers/:id/sip_endpoints`
- Access tokens are valid for 2 hours
- Refresh tokens are valid for 2 hours and 5 minutes
- Subscriber fields (first_name, last_name, display_name, etc.) are optional

## API Endpoint Reference
### Subscriber CRUD
- **List Subscribers**: GET `/resources/subscribers`
- **Get Subscriber**: GET `/resources/subscribers/:id`
- **Create Subscriber**: POST `/resources/subscribers`
- **Update Subscriber**: PUT `/resources/subscribers/:id`
- **Delete Subscriber**: DELETE `/resources/subscribers/:id`
- **List Addresses**: GET `/resources/subscribers/:id/addresses`

### Token Operations
- **Create Token**: POST `/subscribers/tokens`
- **Create Guest Token**: POST `/guests/tokens`
- **Create Invite Token**: POST `/subscriber/invites`
- **Refresh Token**: POST `/subscribers/tokens/refresh`

### SIP Endpoints
- **List SIP Endpoints**: GET `/resources/subscribers/:id/sip_endpoints`
- **Get SIP Endpoint**: GET `/resources/subscribers/:id/sip_endpoints/:endpoint_id`
- **Create SIP Endpoint**: POST `/resources/subscribers/:id/sip_endpoints`
- **Update SIP Endpoint**: PATCH `/resources/subscribers/:id/sip_endpoints/:endpoint_id`
- **Delete SIP Endpoint**: DELETE `/resources/subscribers/:id/sip_endpoints/:endpoint_id`

## Command Reference
```
# Subscriber CRUD
subscriber list [-i ID] [-j]
subscriber create -e EMAIL -p PASSWORD [--first-name NAME] [--last-name NAME] [-d DISPLAY_NAME] [--job-title TITLE] [--timezone TZ] [--country CODE] [--region REGION] [--company NAME]
subscriber update -i ID [-e EMAIL] [-p PASSWORD] [--first-name NAME] [--last-name NAME] [-d DISPLAY_NAME] [--job-title TITLE] [--timezone TZ] [--country CODE] [--region REGION] [--company NAME]
subscriber delete -i ID [-f]
subscriber addresses -i ID [-j]

# Token Commands
subscriber token create -r REFERENCE -p PASSWORD [-a APP_ID] [-j]
subscriber token guest [-r REFERENCE] [-j]
subscriber token invite -t TOKEN [-j]
subscriber token refresh -t TOKEN [-j]

# SIP Endpoint Commands
subscriber sip list -i SUBSCRIBER_ID [-e ENDPOINT_ID] [-j]
subscriber sip create -i SUBSCRIBER_ID -u USERNAME -p PASSWORD [-s SEND_AS] [-c CALLER_ID] [--encryption ENC] [--codecs CODECS...] [--ciphers CIPHERS...]
subscriber sip update -i SUBSCRIBER_ID -e ENDPOINT_ID [-u USERNAME] [-p PASSWORD] [-s SEND_AS] [-c CALLER_ID] [--encryption ENC] [--codecs CODECS...] [--ciphers CIPHERS...]
subscriber sip delete -i SUBSCRIBER_ID -e ENDPOINT_ID [-f]
```
