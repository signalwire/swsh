# AI Agent Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire REST API
- Valid project/account with AI Agent permissions
- Text editor available (pyvim or $EDITOR)
- Understanding of SWML (SignalWire Markup Language) structure

## Test Cases

### 1. List Commands
```bash
# TC-001: List all AI Agents
ai_agent list

# TC-002: List AI Agents in JSON format
ai_agent list --json

# TC-003: List specific AI Agent by ID
ai_agent list --id <agent_id>

# TC-004: List AI Agent by ID in JSON format
ai_agent list --id <agent_id> --json

# TC-005: List AI Agent by name
ai_agent list --name "Test Agent"

# TC-006: List AI Agent by multi-word name
ai_agent list --name My Test Agent

# TC-007: List non-existent AI Agent by ID
ai_agent list --id nonexistent-123-456

# TC-008: List with invalid agent ID format
ai_agent list --id invalid_id_format

# TC-009: List when no agents exist (new project)
ai_agent list

# TC-010: List by name with special characters
ai_agent list --name "Test-Agent_2024"

# TC-011: List by name with Unicode characters
ai_agent list --name "Test Agent"

# TC-012: List by partial name match
ai_agent list --name "Test"

# TC-013: List by name that doesn't exist
ai_agent list --name "NonExistentAgentName12345"
```

### 2. Create Commands
```bash
# TC-014: Create AI Agent with name only (opens editor)
ai_agent create --name "Editor Test Agent"

# TC-015: Create AI Agent with name and inline contents
ai_agent create --name "Inline Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"You are a helpful assistant"}}}]}}'

# TC-016: Create AI Agent with multi-word name
ai_agent create --name "Multi Word Agent Name"

# TC-017: Create AI Agent with complex SWML contents
ai_agent create --name "Complex Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"You are a customer service agent","temperature":0.7},"post_prompt":{"text":"Summarize the call"}}}]}}'

# TC-018: Create AI Agent with voice settings
ai_agent create --name "Voice Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Hello"},"voice":"en-US-Standard-A"}}]}}'

# TC-019: Create AI Agent with languages
ai_agent create --name "Multilingual Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Hello"},"languages":[{"name":"English","code":"en-US"}]}}]}}'

# TC-020: Create AI Agent with SWAIG functions
ai_agent create --name "Function Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"You can check order status"},"SWAIG":{"functions":[{"function":"check_order","purpose":"Check order status"}]}}}]}}'

# TC-021: Create AI Agent with special characters in name
ai_agent create --name "Test-Agent_2024" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Test"}}}]}}'

# TC-022: Create AI Agent without name (should fail)
ai_agent create --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Test"}}}]}}'

# TC-023: Create AI Agent with empty name (should fail)
ai_agent create --name ""

# TC-024: Create AI Agent and cancel in editor (quit without changes)
ai_agent create --name "Cancel Test"
# Quit editor without making changes - should cancel creation

# TC-025: Create AI Agent with malformed JSON (should fail)
ai_agent create --name "Malformed JSON" --contents '{invalid json content'

# TC-026: Create AI Agent with empty contents
ai_agent create --name "Empty Contents" --contents ""

# TC-027: Create AI Agent with very long name
ai_agent create --name "$(python3 -c "print('a'*100)")"

# TC-028: Create AI Agent with minimal SWML
ai_agent create --name "Minimal Agent" --contents '{"version":"1.0.0","sections":{"main":[]}}'

# TC-029: Create AI Agent with hints
ai_agent create --name "Hints Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Hello"},"hints":["product names","company info"]}}]}}'

# TC-030: Create AI Agent with params
ai_agent create --name "Params Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Hello"},"params":{"confidence":0.6,"barge_confidence":0.1}}}]}}'
```

### 3. Update Commands
```bash
# TC-031: Update AI Agent name by ID
ai_agent update --id <agent_id> --name "Updated Agent Name"

# TC-032: Update AI Agent contents by ID (opens editor)
ai_agent update --id <agent_id>

# TC-033: Update AI Agent contents inline
ai_agent update --id <agent_id> --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Updated prompt"}}}]}}'

# TC-034: Update AI Agent name and contents together
ai_agent update --id <agent_id> --name "Fully Updated Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Both updated"}}}]}}'

# TC-035: Update AI Agent with multi-word name
ai_agent update --id <agent_id> --name "Updated Multi Word Name"

# TC-036: Update AI Agent with special characters in name
ai_agent update --id <agent_id> --name "Updated-Agent_2024"

# TC-037: Update AI Agent and cancel in editor (quit without changes)
ai_agent update --id <agent_id>
# Quit editor without making changes - should cancel update

# TC-038: Update AI Agent without ID (should fail)
ai_agent update --name "Some Name"

# TC-039: Update AI Agent with invalid ID (should fail)
ai_agent update --id invalid-123-456 --name "Test"

# TC-040: Update AI Agent with non-existent ID (should fail)
ai_agent update --id 00000000-0000-0000-0000-000000000000 --name "Test"

# TC-041: Update AI Agent with malformed JSON (should fail)
ai_agent update --id <agent_id> --contents '{invalid json'

# TC-042: Update AI Agent back to original values
ai_agent update --id <agent_id> --name "Original Name" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Original"}}}]}}'
```

### 4. Delete Commands
```bash
# TC-043: Delete AI Agent with confirmation prompt
ai_agent delete --id <agent_id>

# TC-044: Delete AI Agent with force flag (no confirmation)
ai_agent delete --id <agent_id> --force

# TC-045: Delete AI Agent without ID (should fail)
ai_agent delete

# TC-046: Delete AI Agent with invalid ID (should fail)
ai_agent delete --id invalid-123-456 --force

# TC-047: Delete AI Agent with non-existent ID (should fail)
ai_agent delete --id 00000000-0000-0000-0000-000000000000 --force

# TC-048: Cancel delete operation (choose 'no' when prompted)
ai_agent delete --id <agent_id>

# TC-049: Delete with case variations in confirmation
ai_agent delete --id <agent_id>  # Test 'Y', 'y', 'yes', 'Yes'

# TC-050: Delete with invalid confirmation responses
ai_agent delete --id <agent_id>  # Test 'maybe', '1', 'sure'
```

### 5. Edge Cases & Error Handling
```bash
# TC-051: Invalid command (should show help)
ai_agent invalid_command

# TC-052: No subcommand (should show help)
ai_agent

# TC-053: Help command
ai_agent --help

# TC-054: Help for specific subcommands
ai_agent create --help
ai_agent update --help
ai_agent list --help
ai_agent delete --help

# TC-055: AI Agent name with newlines
ai_agent create --name $'Test\nAgent'

# TC-056: AI Agent name with tabs
ai_agent create --name $'Test\tAgent'

# TC-057: Multiple concurrent create operations
ai_agent create --name "Concurrent1" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"1"}}}]}}' &
ai_agent create --name "Concurrent2" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"2"}}}]}}' &
wait

# TC-058: URL encoding edge cases in name
ai_agent create --name "Test%20Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Test"}}}]}}'
ai_agent create --name "Test+Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Test"}}}]}}'
ai_agent create --name "Test&Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Test"}}}]}}'

# TC-059: Case sensitivity tests for names
ai_agent create --name "test" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"lower"}}}]}}'
ai_agent create --name "Test" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"title"}}}]}}'
ai_agent create --name "TEST" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"upper"}}}]}}'

# TC-060: SWML with nested structures
ai_agent create --name "Nested Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Hello","temperature":0.7,"top_p":0.9},"SWAIG":{"functions":[{"function":"test","purpose":"Test function","argument":{"type":"object","properties":{"id":{"type":"string"}}}}]}}}]}}'

# TC-061: Editor environment variable test
EDITOR=vim ai_agent create --name "Vim Editor Test"
EDITOR=nano ai_agent create --name "Nano Editor Test"

# TC-062: Non-existent editor
EDITOR=nonexistent_editor ai_agent create --name "Bad Editor Test"

# TC-063: SWML with Unicode in prompt
ai_agent create --name "Unicode Agent" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Hello! Bonjour! Hola! こんにちは!"}}}]}}'
```

### 6. Integration Tests
```bash
# TC-064: Full AI Agent lifecycle
# Create -> List (verify) -> Update -> List (verify changes) -> Delete
ai_agent create --name "Lifecycle Test" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Original"}}}]}}'
ai_agent list --name "Lifecycle Test"
ai_agent update --id <new_agent_id> --name "Updated Lifecycle Test" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Updated"}}}]}}'
ai_agent list --id <new_agent_id>
ai_agent delete --id <new_agent_id> --force

# TC-065: Create and verify in different output formats
ai_agent create --name "Format Test" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Format"}}}]}}'
ai_agent list --id <new_agent_id>
ai_agent list --id <new_agent_id> --json

# TC-066: Update and verify changes persist
ai_agent update --id <agent_id> --name "Persistence Test"
ai_agent list --id <agent_id>
ai_agent list --id <agent_id> --json

# TC-067: Multiple operations on same AI Agent
ai_agent create --name "Multi Op Test" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Initial"}}}]}}'
ai_agent update --id <new_agent_id> --name "Multi Op Test Updated"
ai_agent update --id <new_agent_id> --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Second update"}}}]}}'
ai_agent update --id <new_agent_id> --name "Multi Op Test Final" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Final"}}}]}}'
ai_agent list --id <new_agent_id>

# TC-068: Test all output formatting consistency
ai_agent list  # Default format
ai_agent list --json  # JSON format
ai_agent list --id <agent_id>  # Single agent default
ai_agent list --id <agent_id> --json  # Single agent JSON

# TC-069: Bulk operations testing
ai_agent create --name "Bulk Test 1" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Bulk 1"}}}]}}'
ai_agent create --name "Bulk Test 2" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Bulk 2"}}}]}}'
ai_agent create --name "Bulk Test 3" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Bulk 3"}}}]}}'
ai_agent list --json  # Verify all created
ai_agent delete --id <bulk1_id> --force
ai_agent delete --id <bulk2_id> --force
ai_agent delete --id <bulk3_id> --force

# TC-070: Test SWML validation by API
ai_agent create --name "SWML Validation" --contents '{"version":"1.0.0","sections":{"main":[{"ai":{"prompt":{"text":"Test"},"invalid_field":"value"}}]}}'
# Check if API accepts or rejects invalid SWML fields
```

### 7. Editor Integration Tests
```bash
# TC-071: Create agent - make changes in editor - verify saved
ai_agent create --name "Editor Save Test"
# In editor: Modify the prompt text and save
ai_agent list --name "Editor Save Test"  # Verify contents

# TC-072: Create agent - quit editor without changes - verify cancelled
ai_agent create --name "Editor Cancel Test"
# In editor: Quit without saving
# Should output: "AI Agent creation cancelled"
ai_agent list --name "Editor Cancel Test"  # Should not exist

# TC-073: Update agent - make changes in editor - verify saved
ai_agent update --id <agent_id>
# In editor: Modify content and save
ai_agent list --id <agent_id>  # Verify updated contents

# TC-074: Update agent - quit editor without changes - verify cancelled
ai_agent update --id <agent_id>
# In editor: Quit without saving
# Should output: "AI Agent update cancelled"

# TC-075: Update agent with only name - should not open editor
ai_agent update --id <agent_id> --name "Name Only Update"
# Should update immediately without opening editor

# TC-076: Verify editor loads current contents for update
ai_agent update --id <agent_id>
# In editor: Verify the current SWML is loaded, not the default template
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 404, etc.)
- **Data Validation**: Verify agent data matches input (name, contents, id)
- **Error Messages**: For failure cases, verify proper error messages are shown
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **Editor Behavior**: For create/update without inline contents, verify editor opens and changes are detected
- **JSON Validation**: Verify SWML contents are valid JSON before sending to API

## Test Environment Setup
```bash
# Save original AI Agents for reference
ai_agent list --json > original_ai_agents.json

# Get available AI Agents for testing
ai_agent list --json | jq -r '.[].id'

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# Check editor setting
echo $EDITOR

# After testing, clean up test AI Agents
ai_agent list --json | jq -r '.[] | select(.name | test("^Test|^Lifecycle|^Format|^Bulk|^Multi|^Editor")) | .id' | while read id; do
    ai_agent delete --id $id --force
done
```

## Notes
- AI Agents use SWML (SignalWire Markup Language) for configuration
- SWML contents must be valid JSON
- The `contents` field stores the complete SWML document as a JSON string
- Editor opens with .swml file extension for syntax highlighting (if supported)
- Default SWML template includes basic AI prompt structure
- The REST API uses JSON payloads (not form-encoded like Compatibility API)
- Agent IDs are UUIDs in the format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
- Name filtering is case-sensitive
- Always verify agent changes after updates
- Delete operations require confirmation unless --force flag is used
- Editor defaults to `pyvim` if `$EDITOR` environment variable is not set
- Invalid JSON in contents will be rejected before sending to API

## SWML Reference

### Basic Structure
```json
{
  "version": "1.0.0",
  "sections": {
    "main": [
      {
        "ai": {
          "prompt": {
            "text": "Your prompt here"
          }
        }
      }
    ]
  }
}
```

### Common AI Parameters
- `prompt.text` - The main instruction for the AI
- `prompt.temperature` - Response creativity (0.0-1.0)
- `post_prompt.text` - Instructions after call ends
- `voice` - TTS voice to use
- `languages` - Supported languages array
- `hints` - Array of words/phrases for recognition
- `params` - Recognition parameters (confidence, barge_confidence, etc.)
- `SWAIG.functions` - Custom functions the AI can call

## API Endpoint Reference
- **Base URL**: `api/fabric/resources/ai_agents`
- **Methods**: GET (list/retrieve), POST (create), PATCH (update), DELETE (delete)
- **Documentation**: https://developer.signalwire.com/rest/signalwire-rest/endpoints/fabric/ai-agents-create/
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/json
- **Response Format**: JSON with `data` array for list, single object for get/create/update
- **Delete Response**: 204 No Content on successful deletion

## Command Reference
```
ai_agent list [-n NAME] [-i ID] [-j]
ai_agent create -n NAME [--contents CONTENTS]
ai_agent update -i ID [-n NAME] [--contents CONTENTS]
ai_agent delete -i ID [-f]
```

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the ai_agent command.
