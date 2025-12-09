# Video Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Video API
- Valid project/account with Video scope permissions
- RTMP endpoint URL for stream testing (optional)

## Test Cases

### 1. Room List Commands
```bash
# TC-001: List all video rooms
video room list

# TC-002: List video rooms in JSON format
video room list --json

# TC-003: Get specific room by ID
video room list --id <room_id>

# TC-004: Get specific room by ID in JSON format
video room list --id <room_id> --json

# TC-005: Get room by unique name
video room list --name my-test-room

# TC-006: Get room by unique name in JSON format
video room list --name my-test-room --json

# TC-007: Get non-existent room by ID
video room list --id 00000000-0000-0000-0000-000000000000

# TC-008: Get non-existent room by name
video room list --name nonexistent-room-name
```

### 2. Room Create Commands
```bash
# TC-009: Create basic room with name only
video room create --name test-room-basic

# TC-010: Create room with display name
video room create --name test-room-display --display-name "Test Room Display"

# TC-011: Create room with max members
video room create --name test-room-members --max-members 10

# TC-012: Create room with 720p quality
video room create --name test-room-720p --quality 720p

# TC-013: Create room with 1080p quality
video room create --name test-room-1080p --quality 1080p

# TC-014: Create room with layout
video room create --name test-room-layout --layout grid-responsive

# TC-015: Create room with record on start
video room create --name test-room-record --record-on-start

# TC-016: Create room with room previews enabled
video room create --name test-room-previews --enable-room-previews

# TC-017: Create room with all parameters
video room create --name test-room-full --display-name "Full Featured Room" --max-members 20 --quality 1080p --layout grid-responsive --record-on-start --enable-room-previews

# TC-018: Create room without name (should fail)
video room create --display-name "No Name Room"

# TC-019: Create room with invalid quality (should fail)
video room create --name test-room-invalid --quality 480p

# TC-020: Create room with duplicate name (should fail)
video room create --name test-room-basic
video room create --name test-room-basic

# TC-021: Create room with very long name
video room create --name $(python3 -c "print('a'*200)")

# TC-022: Create room with special characters in name
video room create --name "test-room-special_123"

# TC-023: Create room with spaces in display name
video room create --name test-room-spaces --display-name "Room With Multiple Spaces"

# TC-024: Create room with zero max members
video room create --name test-room-zero --max-members 0

# TC-025: Create room with very high max members
video room create --name test-room-high --max-members 1000
```

### 3. Room Update Commands
```bash
# TC-026: Update room name
video room update --id <room_id> --name updated-room-name

# TC-027: Update room display name
video room update --id <room_id> --display-name "Updated Display Name"

# TC-028: Update room max members
video room update --id <room_id> --max-members 50

# TC-029: Update room quality
video room update --id <room_id> --quality 1080p

# TC-030: Update room layout
video room update --id <room_id> --layout speaker

# TC-031: Update room record on start
video room update --id <room_id> --record-on-start

# TC-032: Update room previews
video room update --id <room_id> --enable-room-previews

# TC-033: Update multiple room parameters
video room update --id <room_id> --name multi-update --display-name "Multi Update" --max-members 25

# TC-034: Update room without ID (should fail)
video room update --name some-name

# TC-035: Update room without any parameters (should fail)
video room update --id <room_id>

# TC-036: Update non-existent room (should fail)
video room update --id 00000000-0000-0000-0000-000000000000 --name test

# TC-037: Update room with invalid quality (should fail)
video room update --id <room_id> --quality invalid
```

### 4. Room Delete Commands
```bash
# TC-038: Delete room with confirmation prompt
video room delete --id <room_id>

# TC-039: Delete room with force flag
video room delete --id <room_id> --force

# TC-040: Delete room without ID (should fail)
video room delete

# TC-041: Delete non-existent room (should fail)
video room delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-042: Cancel delete operation (choose 'no' when prompted)
video room delete --id <room_id>

# TC-043: Delete with case variations in confirmation
video room delete --id <room_id>  # Test 'Y', 'y', 'yes', 'Yes'

# TC-044: Delete room that has active sessions
video room delete --id <active_room_id> --force
```

### 5. Conference List Commands
```bash
# TC-045: List all video conferences
video conference list

# TC-046: List video conferences in JSON format
video conference list --json

# TC-047: Get specific conference by ID
video conference list --id <conference_id>

# TC-048: Get specific conference by ID in JSON format
video conference list --id <conference_id> --json

# TC-049: Get non-existent conference by ID
video conference list --id 00000000-0000-0000-0000-000000000000
```

### 6. Conference Create Commands
```bash
# TC-050: Create basic conference
video conference create --name test-conference-basic

# TC-051: Create conference with display name
video conference create --name test-conference-display --display-name "Test Conference"

# TC-052: Create conference with max members
video conference create --name test-conference-members --max-members 50

# TC-053: Create conference with quality
video conference create --name test-conference-quality --quality 1080p

# TC-054: Create conference with layout
video conference create --name test-conference-layout --layout grid-responsive

# TC-055: Create conference with record on start
video conference create --name test-conference-record --record-on-start

# TC-056: Create conference with all parameters
video conference create --name test-conference-full --display-name "Full Conference" --max-members 100 --quality 1080p --layout speaker --record-on-start

# TC-057: Create conference without name (should fail)
video conference create --display-name "No Name Conference"

# TC-058: Create conference with invalid quality (should fail)
video conference create --name test-conf-invalid --quality 480p
```

### 7. Conference Update Commands
```bash
# TC-059: Update conference name
video conference update --id <conference_id> --name updated-conference

# TC-060: Update conference display name
video conference update --id <conference_id> --display-name "Updated Conference"

# TC-061: Update conference max members
video conference update --id <conference_id> --max-members 75

# TC-062: Update conference quality
video conference update --id <conference_id> --quality 720p

# TC-063: Update conference layout
video conference update --id <conference_id> --layout highlight-1-5

# TC-064: Update multiple conference parameters
video conference update --id <conference_id> --name multi-conf --display-name "Multi Update" --max-members 30

# TC-065: Update conference without ID (should fail)
video conference update --name some-name

# TC-066: Update conference without any parameters (should fail)
video conference update --id <conference_id>

# TC-067: Update non-existent conference (should fail)
video conference update --id 00000000-0000-0000-0000-000000000000 --name test
```

### 8. Conference Delete Commands
```bash
# TC-068: Delete conference with confirmation prompt
video conference delete --id <conference_id>

# TC-069: Delete conference with force flag
video conference delete --id <conference_id> --force

# TC-070: Delete conference without ID (should fail)
video conference delete

# TC-071: Delete non-existent conference (should fail)
video conference delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-072: Cancel delete operation (choose 'no' when prompted)
video conference delete --id <conference_id>
```

### 9. Conference Token Commands
```bash
# TC-073: List conference tokens
video conference token list --conference-id <conference_id>

# TC-074: List conference tokens in JSON format
video conference token list --conference-id <conference_id> --json

# TC-075: List tokens without conference ID (should fail)
video conference token list

# TC-076: List tokens for non-existent conference
video conference token list --conference-id 00000000-0000-0000-0000-000000000000

# TC-077: Get conference token by ID
video conference token get --id <token_id>

# TC-078: Get conference token by ID in JSON format
video conference token get --id <token_id> --json

# TC-079: Get conference token without ID (should fail)
video conference token get

# TC-080: Get non-existent conference token
video conference token get --id 00000000-0000-0000-0000-000000000000

# TC-081: Reset conference token
video conference token reset --id <token_id>

# TC-082: Reset conference token without ID (should fail)
video conference token reset

# TC-083: Reset non-existent conference token
video conference token reset --id 00000000-0000-0000-0000-000000000000
```

### 10. Room Token Create Commands
```bash
# TC-084: Create basic room token
video token create --room-name test-room --user-name testuser

# TC-085: Create room token in JSON format
video token create --room-name test-room --user-name testuser --json

# TC-086: Create room token with permissions
video token create --room-name test-room --user-name testuser --permissions room.self.audio_mute room.self.video_mute

# TC-087: Create room token with auto-create room
video token create --room-name new-auto-room --user-name testuser --auto-create-room

# TC-088: Create room token with join-from time
video token create --room-name test-room --user-name testuser --join-from "2024-01-01T00:00:00Z"

# TC-089: Create room token with join-until time
video token create --room-name test-room --user-name testuser --join-until "2024-12-31T23:59:59Z"

# TC-090: Create room token with time constraints
video token create --room-name test-room --user-name testuser --join-from "2024-01-01T00:00:00Z" --join-until "2024-12-31T23:59:59Z"

# TC-091: Create room token with all parameters
video token create --room-name test-room --user-name testuser --permissions room.self.audio_mute --auto-create-room --join-from "2024-01-01T00:00:00Z" --join-until "2024-12-31T23:59:59Z" --json

# TC-092: Create room token without room name (should fail)
video token create --user-name testuser

# TC-093: Create room token without user name (should fail)
video token create --room-name test-room

# TC-094: Create room token for non-existent room (without auto-create)
video token create --room-name nonexistent-room-12345 --user-name testuser

# TC-095: Create room token with invalid date format
video token create --room-name test-room --user-name testuser --join-from "invalid-date"
```

### 11. Session List Commands
```bash
# TC-096: List all room sessions
video session list

# TC-097: List room sessions in JSON format
video session list --json

# TC-098: Get specific session by ID
video session list --id <session_id>

# TC-099: Get specific session by ID in JSON format
video session list --id <session_id> --json

# TC-100: Get non-existent session by ID
video session list --id 00000000-0000-0000-0000-000000000000
```

### 12. Session Recordings Commands
```bash
# TC-101: List recordings for session
video session recordings --id <session_id>

# TC-102: List recordings for session in JSON format
video session recordings --id <session_id> --json

# TC-103: List recordings without session ID (should fail)
video session recordings

# TC-104: List recordings for non-existent session
video session recordings --id 00000000-0000-0000-0000-000000000000

# TC-105: List recordings for session with no recordings
video session recordings --id <session_without_recordings>
```

### 13. Session Members Commands
```bash
# TC-106: List members for session
video session members --id <session_id>

# TC-107: List members for session in JSON format
video session members --id <session_id> --json

# TC-108: List members without session ID (should fail)
video session members

# TC-109: List members for non-existent session
video session members --id 00000000-0000-0000-0000-000000000000

# TC-110: List members for session with no members
video session members --id <empty_session_id>
```

### 14. Recording List Commands
```bash
# TC-111: List all room recordings
video recording list

# TC-112: List room recordings in JSON format
video recording list --json

# TC-113: Get specific recording by ID
video recording list --id <recording_id>

# TC-114: Get specific recording by ID in JSON format
video recording list --id <recording_id> --json

# TC-115: Get non-existent recording by ID
video recording list --id 00000000-0000-0000-0000-000000000000
```

### 15. Recording Delete Commands
```bash
# TC-116: Delete recording with confirmation prompt
video recording delete --id <recording_id>

# TC-117: Delete recording with force flag
video recording delete --id <recording_id> --force

# TC-118: Delete recording without ID (should fail)
video recording delete

# TC-119: Delete non-existent recording (should fail)
video recording delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-120: Cancel delete operation (choose 'no' when prompted)
video recording delete --id <recording_id>
```

### 16. Stream List Commands
```bash
# TC-121: List stream by ID
video stream list --id <stream_id>

# TC-122: List stream by ID in JSON format
video stream list --id <stream_id> --json

# TC-123: List streams by room ID
video stream list --room-id <room_id>

# TC-124: List streams by room ID in JSON format
video stream list --room-id <room_id> --json

# TC-125: List streams by conference ID
video stream list --conference-id <conference_id>

# TC-126: List streams by conference ID in JSON format
video stream list --conference-id <conference_id> --json

# TC-127: List streams without any ID (should fail - mutually exclusive required)
video stream list

# TC-128: List streams with both room and conference ID (should fail - mutually exclusive)
video stream list --room-id <room_id> --conference-id <conference_id>

# TC-129: List streams for non-existent room
video stream list --room-id 00000000-0000-0000-0000-000000000000

# TC-130: List streams for non-existent conference
video stream list --conference-id 00000000-0000-0000-0000-000000000000
```

### 17. Stream Create Commands
```bash
# TC-131: Create stream for room
video stream create --room-id <room_id> --url rtmp://example.com/live/stream1

# TC-132: Create stream for conference
video stream create --conference-id <conference_id> --url rtmp://example.com/live/stream2

# TC-133: Create stream without parent ID (should fail - mutually exclusive required)
video stream create --url rtmp://example.com/live/stream

# TC-134: Create stream with both room and conference ID (should fail - mutually exclusive)
video stream create --room-id <room_id> --conference-id <conference_id> --url rtmp://example.com/live/stream

# TC-135: Create stream without URL (should fail)
video stream create --room-id <room_id>

# TC-136: Create stream for non-existent room
video stream create --room-id 00000000-0000-0000-0000-000000000000 --url rtmp://example.com/live/stream

# TC-137: Create stream for non-existent conference
video stream create --conference-id 00000000-0000-0000-0000-000000000000 --url rtmp://example.com/live/stream

# TC-138: Create stream with invalid URL format
video stream create --room-id <room_id> --url "not-a-valid-url"

# TC-139: Create stream with RTMPS URL
video stream create --room-id <room_id> --url rtmps://example.com/live/secure-stream
```

### 18. Stream Update Commands
```bash
# TC-140: Update stream URL
video stream update --id <stream_id> --url rtmp://example.com/live/updated-stream

# TC-141: Update stream without ID (should fail)
video stream update --url rtmp://example.com/live/stream

# TC-142: Update stream without any parameters (should fail)
video stream update --id <stream_id>

# TC-143: Update non-existent stream (should fail)
video stream update --id 00000000-0000-0000-0000-000000000000 --url rtmp://example.com/live/stream
```

### 19. Stream Delete Commands
```bash
# TC-144: Delete stream with confirmation prompt
video stream delete --id <stream_id>

# TC-145: Delete stream with force flag
video stream delete --id <stream_id> --force

# TC-146: Delete stream without ID (should fail)
video stream delete

# TC-147: Delete non-existent stream (should fail)
video stream delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-148: Cancel delete operation (choose 'no' when prompted)
video stream delete --id <stream_id>
```

### 20. Edge Cases & Error Handling
```bash
# TC-149: Invalid subcommand (should show help)
video invalid_command

# TC-150: No subcommand (should show help)
video

# TC-151: Help for video command
video --help

# TC-152: Help for room subcommand
video room --help

# TC-153: Help for conference subcommand
video conference --help

# TC-154: Help for token subcommand
video token --help

# TC-155: Help for session subcommand
video session --help

# TC-156: Help for recording subcommand
video recording --help

# TC-157: Help for stream subcommand
video stream --help

# TC-158: Help for conference token subcommand
video conference token --help

# TC-159: Help for specific actions
video room list --help
video room create --help
video room update --help
video room delete --help

# TC-160: Room subcommand without action (should show help)
video room

# TC-161: Conference subcommand without action (should show help)
video conference

# TC-162: Token subcommand without action (should show help)
video token

# TC-163: Session subcommand without action (should show help)
video session

# TC-164: Recording subcommand without action (should show help)
video recording

# TC-165: Stream subcommand without action (should show help)
video stream

# TC-166: Conference token subcommand without action (should show help)
video conference token

# TC-167: Very long room name (test limits)
video room create --name $(python3 -c "print('a'*500)")

# TC-168: Unicode characters in room name
video room create --name "测试房间"

# TC-169: Special characters in display name
video room create --name test-special --display-name "Room <with> 'special' \"chars\" & symbols"
```

### 21. Integration Tests
```bash
# TC-170: Full room lifecycle
# Create -> List -> Update -> List -> Delete
video room create --name lifecycle-test-room --display-name "Lifecycle Test"
video room list --name lifecycle-test-room
video room update --id <created_id> --display-name "Updated Lifecycle Test"
video room list --id <created_id>
video room delete --id <created_id> --force

# TC-171: Full conference lifecycle
# Create -> List -> Update -> List -> Delete
video conference create --name lifecycle-test-conf --display-name "Lifecycle Test Conference"
video conference list --id <created_id>
video conference update --id <created_id> --display-name "Updated Conference"
video conference list --id <created_id>
video conference delete --id <created_id> --force

# TC-172: Room with token creation
video room create --name token-test-room
video token create --room-name token-test-room --user-name test-user
video room delete --id <room_id> --force

# TC-173: Room with token and auto-create
video token create --room-name auto-created-room --user-name test-user --auto-create-room
video room list --name auto-created-room
video room delete --id <room_id> --force

# TC-174: Stream lifecycle with room
video room create --name stream-test-room
video stream create --room-id <room_id> --url rtmp://example.com/live/test
video stream list --room-id <room_id>
video stream update --id <stream_id> --url rtmp://example.com/live/updated
video stream delete --id <stream_id> --force
video room delete --id <room_id> --force

# TC-175: Stream lifecycle with conference
video conference create --name stream-test-conf
video stream create --conference-id <conf_id> --url rtmp://example.com/live/conf-test
video stream list --conference-id <conf_id>
video stream delete --id <stream_id> --force
video conference delete --id <conf_id> --force

# TC-176: Conference with token operations
video conference create --name conf-token-test
video conference token list --conference-id <conf_id>
# If tokens exist:
video conference token get --id <token_id>
video conference token reset --id <token_id>
video conference delete --id <conf_id> --force

# TC-177: Session and recording workflow
# Note: Requires active room session with recording enabled
video room create --name recording-test-room --record-on-start
# Join room and create session (external action required)
video session list
video session recordings --id <session_id>
video session members --id <session_id>
video recording list
video recording delete --id <recording_id> --force
video room delete --id <room_id> --force

# TC-178: Bulk room creation and cleanup
video room create --name bulk-test-1
video room create --name bulk-test-2
video room create --name bulk-test-3
video room list --json
video room delete --id <bulk1_id> --force
video room delete --id <bulk2_id> --force
video room delete --id <bulk3_id> --force

# TC-179: Conference with multiple streams
video conference create --name multi-stream-conf
video stream create --conference-id <conf_id> --url rtmp://example.com/stream1
video stream create --conference-id <conf_id> --url rtmp://example.com/stream2
video stream list --conference-id <conf_id>
video stream delete --id <stream1_id> --force
video stream delete --id <stream2_id> --force
video conference delete --id <conf_id> --force

# TC-180: Verify JSON output structure
video room list --json | jq '.'
video conference list --json | jq '.'
video session list --json | jq '.'
video recording list --json | jq '.'
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, 422, etc.)
- **Data Validation**: Verify created/updated data matches input
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **JSON Structure**: For --json output, verify proper JSON formatting

## Test Environment Setup
```bash
# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# Save original resources for reference
video room list --json > original_rooms.json
video conference list --json > original_conferences.json
video recording list --json > original_recordings.json

# Get available resources for testing
video room list --json | jq -r '.[] | .id'
video conference list --json | jq -r '.[] | .id'

# After testing, cleanup test resources
# Rooms
video room list --json | jq -r '.[] | select(.name | startswith("test-")) | .id' | while read id; do
    video room delete --id $id --force
done

# Conferences
video conference list --json | jq -r '.[] | select(.name | startswith("test-")) | .id' | while read id; do
    video conference delete --id $id --force
done
```

## Notes
- Video resources are billed based on usage - exercise caution with room sessions
- Streams require valid RTMP endpoints for full functionality testing
- Room sessions are created when users join rooms - requires external client
- Recordings are generated from room sessions with recording enabled
- Conference tokens are auto-generated when conferences are created
- Room tokens expire based on join-from and join-until parameters
- Delete operations require confirmation unless --force flag is used
- Room names must be unique within a project
- Some operations may take time to reflect in the API (eventual consistency)
- Streams to inactive rooms/conferences will fail
- Max members limit may vary based on account tier

## API Endpoint Reference
- **Base URL**: `api/video`
- **Rooms**: `/rooms`, `/rooms/:id`
- **Conferences**: `/conferences`, `/conferences/:id`
- **Room Tokens**: `/room_tokens`
- **Room Sessions**: `/room_sessions`, `/room_sessions/:id`
- **Room Recordings**: `/room_recordings`, `/room_recordings/:id`
- **Streams**: `/streams/:id`, `/rooms/:id/streams`, `/conferences/:id/streams`
- **Conference Tokens**: `/conferences/:id/conference_tokens`, `/conference_tokens/:id`, `/conference_tokens/:id/reset`
- **Session Recordings**: `/room_sessions/:id/recordings`
- **Session Members**: `/room_sessions/:id/members`
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/json
- **Delete Response**: 204 No Content on successful deletion

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the video command.
