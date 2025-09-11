# SIP Profile Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Test SIP profile domain identifiers available
- Network connectivity to SignalWire API

## Test Cases

### 1. List Commands
```bash
# TC-001: List all SIP profiles
sip_profile list

# TC-002: List SIP profiles in JSON format
sip_profile list --json
```

### 2. Update Commands
```bash
# TC-003: Update SIP profile send-as
sip_profile update --domain-identifier <domain_id> --send-as +15551234567

# TC-004: Update SIP profile encryption
sip_profile update --domain-identifier <domain_id> --encryption required

# TC-005: Update SIP profile encryption to optional
sip_profile update --domain-identifier <domain_id> --encryption optional

# TC-006: Update SIP profile codecs (single)
sip_profile update --domain-identifier <domain_id> --codecs OPUS

# TC-007: Update SIP profile codecs (multiple)
sip_profile update --domain-identifier <domain_id> --codecs OPUS G722 PCMU

# TC-008: Update SIP profile ciphers (single)
sip_profile update --domain-identifier <domain_id> --ciphers AES_256_CM_HMAC_SHA1_80

# TC-009: Update SIP profile ciphers (multiple)
sip_profile update --domain-identifier <domain_id> --ciphers AES_256_CM_HMAC_SHA1_80 AES_CM_128_HMAC_SHA1_80

# TC-010: Update multiple fields simultaneously
sip_profile update --domain-identifier <domain_id> --send-as +15559876543 --encryption required --codecs OPUS G722

# TC-011: Update without domain identifier (should fail)
sip_profile update --send-as +15551234567

# TC-012: Update non-existent profile (should fail)
sip_profile update --domain-identifier nonexistent123 --encryption required

# TC-013: Update with invalid encryption option (should fail)
sip_profile update --domain-identifier <domain_id> --encryption invalid

# TC-014: Update with invalid codec option (should fail)
sip_profile update --domain-identifier <domain_id> --codecs INVALID_CODEC

# TC-015: Update with invalid cipher option (should fail)
sip_profile update --domain-identifier <domain_id> --ciphers INVALID_CIPHER
```

### 3. Edge Cases & Error Handling
```bash
# TC-016: Invalid command (should show help)
sip_profile invalid_command

# TC-017: No subcommand (should show help)
sip_profile

# TC-018: Valid codec choices test
sip_profile update --domain-identifier <domain_id> --codecs OPUS
sip_profile update --domain-identifier <domain_id> --codecs G722
sip_profile update --domain-identifier <domain_id> --codecs PCMU
sip_profile update --domain-identifier <domain_id> --codecs PCMA
sip_profile update --domain-identifier <domain_id> --codecs VP8
sip_profile update --domain-identifier <domain_id> --codecs H264

# TC-019: Valid cipher choices test
sip_profile update --domain-identifier <domain_id> --ciphers AEAD_AES_256_GCM_8
sip_profile update --domain-identifier <domain_id> --ciphers AES_256_CM_HMAC_SHA1_80
sip_profile update --domain-identifier <domain_id> --ciphers AES_CM_128_HMAC_SHA1_80
sip_profile update --domain-identifier <domain_id> --ciphers AES_256_CM_HMAC_SHA1_32
sip_profile update --domain-identifier <domain_id> --ciphers AES_CM_128_HMAC_SHA1_32

# TC-020: Empty values test
sip_profile update --domain-identifier <domain_id> --send-as ""

# TC-021: Special characters in domain identifier
sip_profile update --domain-identifier "test-domain.example.com" --encryption required
```

### 4. Integration Tests
```bash
# TC-022: Full workflow test
# List -> Update -> List (verify changes)
sip_profile list --json > before_update.json
sip_profile update --domain-identifier <domain_id> --encryption required --codecs OPUS G722
sip_profile list --json > after_update.json
# Compare files to verify update was applied

# TC-023: Multiple update sequence
sip_profile update --domain-identifier <domain_id> --encryption required
sip_profile update --domain-identifier <domain_id> --codecs OPUS
sip_profile update --domain-identifier <domain_id> --ciphers AES_256_CM_HMAC_SHA1_80
sip_profile list --json  # Verify all changes persisted
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes
- **Data Validation**: Verify updated profile data matches input

## Test Environment Setup
```bash
# Save original profiles for cleanup
sip_profile list --json > original_profiles.json

# Get available domain identifiers for testing
sip_profile list --json | jq -r '.[] | .domain_identifier'

# After testing, restore original settings if needed
# (Restore any profiles modified during testing)
```

## Notes
- SIP profiles typically have one profile per SignalWire space
- Domain identifier is usually the space name with `.pstn.signalwire.com` suffix
- Profile updates affect all SIP endpoints in that profile
- Changes may take a few moments to propagate to active endpoints
- Always verify profile settings after updates to ensure they were applied correctly