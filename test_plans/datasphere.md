# Datasphere Command Test Plan

## Prerequisites
- Valid SignalWire environment variables set
- Network connectivity to SignalWire API
- Access to SignalWire Datasphere API
- Valid project/account with Datasphere permissions
- Test documents (text content or accessible URLs) for upload testing

## Test Cases

### 1. List Commands
```bash
# TC-001: List all Datasphere Documents
datasphere list

# TC-002: List documents in JSON format
datasphere list --json

# TC-003: List specific document by ID
datasphere list --id <document_id>

# TC-004: List document by ID in JSON format
datasphere list --id <document_id> --json

# TC-005: List non-existent document by ID
datasphere list --id nonexistent-document-id

# TC-006: List with invalid document ID format
datasphere list --id "invalid_id_format"

# TC-007: List when no documents exist
datasphere list
```

### 2. Create Commands
```bash
# TC-008: Create document with name only
datasphere create --name "Test Document"

# TC-009: Create document with name and description
datasphere create --name "Test Document" --description "This is a test document"

# TC-010: Create document with multi-word name
datasphere create --name "My Multi Word Document Name"

# TC-011: Create document with URL source
datasphere create --name "URL Document" --url "https://example.com/document.txt"

# TC-012: Create document with text content
datasphere create --name "Text Document" --text "This is the content of my document"

# TC-013: Create document with multi-word text content
datasphere create --name "Long Text Doc" --text This is a longer piece of text content for testing

# TC-014: Create document with name, description, and URL
datasphere create --name "Full Document" --description "Complete document with all fields" --url "https://example.com/doc.txt"

# TC-015: Create document with name, description, and text
datasphere create --name "Full Text Doc" --description "Document with text content" --text "The actual content here"

# TC-016: Create document without name (should fail)
datasphere create --description "Missing name"

# TC-017: Create document with empty name (should fail)
datasphere create --name ""

# TC-018: Create document with special characters in name
datasphere create --name "Test-Document_2024" --text "Content"

# TC-019: Create document with URL containing special characters
datasphere create --name "Special URL" --url "https://example.com/docs/test%20file.txt?token=abc123"

# TC-020: Create document with invalid URL
datasphere create --name "Invalid URL" --url "not-a-valid-url"

# TC-021: Create document with non-existent URL
datasphere create --name "Missing URL" --url "https://example.com/nonexistent-file.txt"

# TC-022: Create document with very long name
datasphere create --name "$(python3 -c "print('a'*200)")" --text "Test"

# TC-023: Create document with Unicode characters
datasphere create --name "Unicode Doc" --text "Hello こんにちは Bonjour 你好"
```

### 3. Search Commands
```bash
# TC-024: Basic search query
datasphere search --query "test content"

# TC-025: Search with multi-word query
datasphere search --query what is the meaning of this document

# TC-026: Search with JSON output
datasphere search --query "test" --json

# TC-027: Search limited to specific document
datasphere search --query "content" --document-id <document_id>

# TC-028: Search with count limit
datasphere search --query "test" --count 5

# TC-029: Search with tags filter
datasphere search --query "content" --tags tag1 tag2

# TC-030: Search with distance threshold
datasphere search --query "semantic search" --distance 0.5

# TC-031: Search with all options
datasphere search --query "test" --document-id <doc_id> --count 10 --tags important --distance 0.8 --json

# TC-032: Search without query (should fail)
datasphere search

# TC-033: Search with empty query (should fail)
datasphere search --query ""

# TC-034: Search with non-existent document ID
datasphere search --query "test" --document-id nonexistent-id

# TC-035: Search with special characters in query
datasphere search --query "test@example.com & more"

# TC-036: Search with Unicode query
datasphere search --query "こんにちは"

# TC-037: Search with negative count (should handle gracefully)
datasphere search --query "test" --count -1

# TC-038: Search with zero count
datasphere search --query "test" --count 0

# TC-039: Search with very high count
datasphere search --query "test" --count 1000

# TC-040: Search with negative distance
datasphere search --query "test" --distance -0.5

# TC-041: Search with distance greater than 1
datasphere search --query "test" --distance 2.0
```

### 4. Update Commands
```bash
# TC-042: Update document name
datasphere update --id <document_id> --name "Updated Name"

# TC-043: Update document description
datasphere update --id <document_id> --description "Updated description"

# TC-044: Update both name and description
datasphere update --id <document_id> --name "New Name" --description "New description"

# TC-045: Update with multi-word name
datasphere update --id <document_id> --name "Updated Multi Word Name"

# TC-046: Update with multi-word description
datasphere update --id <document_id> --description "This is an updated description with multiple words"

# TC-047: Update without ID (should fail)
datasphere update --name "Test"

# TC-048: Update without any parameters (should fail)
datasphere update --id <document_id>

# TC-049: Update non-existent document
datasphere update --id nonexistent-id --name "Test"

# TC-050: Update with invalid ID format
datasphere update --id "invalid_format" --name "Test"

# TC-051: Update with special characters in name
datasphere update --id <document_id> --name "Updated-Name_2024"

# TC-052: Update with Unicode in description
datasphere update --id <document_id> --description "Updated description こんにちは"
```

### 5. Delete Commands
```bash
# TC-053: Delete document with confirmation prompt
datasphere delete --id <document_id>

# TC-054: Delete document with force flag
datasphere delete --id <document_id> --force

# TC-055: Delete without ID (should fail)
datasphere delete

# TC-056: Delete with invalid ID
datasphere delete --id "invalid_id" --force

# TC-057: Delete non-existent document
datasphere delete --id nonexistent-id --force

# TC-058: Cancel delete operation (choose 'no')
datasphere delete --id <document_id>

# TC-059: Delete with various confirmation responses
datasphere delete --id <document_id>  # Test 'Y', 'y', 'yes', 'Yes'

# TC-060: Delete with invalid confirmation
datasphere delete --id <document_id>  # Test 'maybe', '1', 'sure'
```

### 6. Chunks List Commands
```bash
# TC-061: List chunks for a document
datasphere chunks list --document-id <document_id>

# TC-062: List chunks in JSON format
datasphere chunks list --document-id <document_id> --json

# TC-063: List chunks without document ID (should fail)
datasphere chunks list

# TC-064: List chunks for non-existent document
datasphere chunks list --document-id nonexistent-id

# TC-065: List chunks for document with no chunks
datasphere chunks list --document-id <empty_document_id>

# TC-066: List chunks with invalid document ID format
datasphere chunks list --document-id "invalid_format"
```

### 7. Chunks Get Commands
```bash
# TC-067: Get specific chunk
datasphere chunks get --document-id <document_id> --chunk-id <chunk_id>

# TC-068: Get chunk in JSON format
datasphere chunks get --document-id <document_id> --chunk-id <chunk_id> --json

# TC-069: Get chunk without document ID (should fail)
datasphere chunks get --chunk-id <chunk_id>

# TC-070: Get chunk without chunk ID (should fail)
datasphere chunks get --document-id <document_id>

# TC-071: Get chunk with non-existent document ID
datasphere chunks get --document-id nonexistent-doc --chunk-id <chunk_id>

# TC-072: Get chunk with non-existent chunk ID
datasphere chunks get --document-id <document_id> --chunk-id nonexistent-chunk

# TC-073: Get chunk with both invalid IDs
datasphere chunks get --document-id invalid --chunk-id invalid
```

### 8. Chunks Delete Commands
```bash
# TC-074: Delete chunk with confirmation prompt
datasphere chunks delete --document-id <document_id> --chunk-id <chunk_id>

# TC-075: Delete chunk with force flag
datasphere chunks delete --document-id <document_id> --chunk-id <chunk_id> --force

# TC-076: Delete chunk without document ID (should fail)
datasphere chunks delete --chunk-id <chunk_id> --force

# TC-077: Delete chunk without chunk ID (should fail)
datasphere chunks delete --document-id <document_id> --force

# TC-078: Delete chunk with non-existent IDs
datasphere chunks delete --document-id nonexistent --chunk-id nonexistent --force

# TC-079: Cancel chunk delete operation
datasphere chunks delete --document-id <document_id> --chunk-id <chunk_id>
# Choose 'no' when prompted

# TC-080: Delete chunk - verify document still exists
datasphere chunks delete --document-id <document_id> --chunk-id <chunk_id> --force
datasphere list --id <document_id>  # Document should still exist
```

### 9. Edge Cases & Error Handling
```bash
# TC-081: Invalid command (should show help)
datasphere invalid_command

# TC-082: No subcommand (should show help)
datasphere

# TC-083: Help command
datasphere --help

# TC-084: Help for specific subcommands
datasphere list --help
datasphere create --help
datasphere search --help
datasphere update --help
datasphere delete --help
datasphere chunks --help
datasphere chunks list --help
datasphere chunks get --help
datasphere chunks delete --help

# TC-085: Document name with newlines
datasphere create --name $'Test\nDocument'

# TC-086: Document name with tabs
datasphere create --name $'Test\tDocument'

# TC-087: Multiple concurrent operations
datasphere create --name "Concurrent1" --text "Content1" &
datasphere create --name "Concurrent2" --text "Content2" &
wait

# TC-088: Very long text content
datasphere create --name "Long Content" --text "$(python3 -c "print('word ' * 10000)")"

# TC-089: Search with very long query
datasphere search --query "$(python3 -c "print('search term ' * 100)")"
```

### 10. Integration Tests
```bash
# TC-090: Full document lifecycle
datasphere create --name "Lifecycle Test" --text "Test content for lifecycle"
datasphere list --name "Lifecycle Test"  # Note: may need --id from create output
datasphere list --id <new_document_id>
datasphere update --id <new_document_id> --name "Updated Lifecycle Test" --description "Added description"
datasphere list --id <new_document_id>
datasphere search --query "lifecycle"
datasphere chunks list --document-id <new_document_id>
datasphere delete --id <new_document_id> --force

# TC-091: Document with chunks workflow
datasphere create --name "Chunks Test" --text "This is content that should be chunked into multiple pieces for testing purposes"
datasphere list --id <document_id>
datasphere chunks list --document-id <document_id>
datasphere chunks get --document-id <document_id> --chunk-id <first_chunk_id>
datasphere chunks delete --document-id <document_id> --chunk-id <chunk_id> --force
datasphere chunks list --document-id <document_id>  # Verify chunk removed
datasphere delete --id <document_id> --force

# TC-092: Search accuracy test
datasphere create --name "Search Test 1" --text "The quick brown fox jumps over the lazy dog"
datasphere create --name "Search Test 2" --text "A slow red cat sleeps under the active cat"
datasphere search --query "quick fox"  # Should match first document
datasphere search --query "slow cat"  # Should match second document
datasphere search --query "animal"  # May match both with semantic search

# TC-093: URL document workflow
datasphere create --name "URL Test" --url "https://example.com/test-document.txt"
datasphere list --id <document_id>
datasphere search --query "content from url"
datasphere chunks list --document-id <document_id>

# TC-094: Multiple document management
datasphere create --name "Multi Doc 1" --text "First document content"
datasphere create --name "Multi Doc 2" --text "Second document content"
datasphere create --name "Multi Doc 3" --text "Third document content"
datasphere list --json
datasphere search --query "document content"
datasphere delete --id <doc1_id> --force
datasphere delete --id <doc2_id> --force
datasphere delete --id <doc3_id> --force

# TC-095: Search with document filter
datasphere create --name "Filtered Search" --text "Unique content for filtering"
datasphere search --query "content" --document-id <document_id>  # Should find
datasphere search --query "content" --document-id <other_document_id>  # Should not find

# TC-096: Output format consistency
datasphere list  # Default format
datasphere list --json
datasphere list --id <document_id>
datasphere list --id <document_id> --json
datasphere search --query "test"
datasphere search --query "test" --json
datasphere chunks list --document-id <document_id>
datasphere chunks list --document-id <document_id> --json
```

## Expected Results Template
For each test case, document:
- **Expected Status**: Success/Failure
- **Expected Output**: Specific success/error messages
- **API Response**: Expected HTTP status codes (200, 201, 204, 400, 401, 404, 422)
- **Data Validation**: Verify document/chunk data matches input
- **Error Messages**: For failure cases, verify proper error messages
- **Confirmation Prompts**: For delete operations, verify proper confirmation behavior
- **Search Results**: For search operations, verify relevance of returned results

## Test Environment Setup
```bash
# Save original documents for reference
datasphere list --json > original_documents.json

# Verify environment variables are set
echo $SIGNALWIRE_SPACE
echo $PROJECT_ID
echo $REST_API_TOKEN

# Create test documents
datasphere create --name "Test Doc 1" --text "Content for testing purposes"
datasphere create --name "Test Doc 2" --description "Another test" --text "More test content"

# After testing, clean up test documents
datasphere list --json | jq -r '.[] | select(.name | test("^Test|^Lifecycle|^Search|^Multi|^URL|^Chunks|^Filtered")) | .id' | while read id; do
    datasphere delete --id $id --force
done
```

## Notes
- Datasphere is an AI-powered document search API
- Documents are automatically chunked for efficient semantic search
- Search uses vector embeddings for semantic matching, not just keyword search
- The `distance` parameter controls semantic similarity threshold (lower = more similar)
- Chunks are read-only fragments created by the system during document processing
- Deleting a document also deletes all its chunks
- Deleting individual chunks may affect search results
- URL-based documents fetch content from the specified URL during creation
- Large documents may take time to process and chunk
- Document IDs are UUIDs
- The API uses JSON payloads and responses

## API Endpoint Reference
- **Base URL**: `api/datasphere/documents`
- **Documents**:
  - `GET /documents` - List all documents
  - `GET /documents/:id` - Get single document
  - `POST /documents` - Create document
  - `POST /documents/search` - Search documents
  - `PATCH /documents/:id` - Update document
  - `DELETE /documents/:id` - Delete document (204 No Content)
- **Chunks**:
  - `GET /documents/:documentId/chunks` - List chunks
  - `GET /documents/:documentId/chunks/:chunkId` - Get chunk
  - `DELETE /documents/:documentId/chunks/:chunkId` - Delete chunk (204 No Content)
- **Authentication**: HTTP Basic Auth with project_id:rest_api_token
- **Content-Type**: application/json

## Command Reference
```
datasphere list [-i ID] [-j]
datasphere create -n NAME [-d DESCRIPTION] [--url URL] [--text TEXT]
datasphere search -q QUERY [--document-id ID] [--count N] [--tags TAG...] [--distance D] [-j]
datasphere update -i ID [-n NAME] [-d DESCRIPTION]
datasphere delete -i ID [-f]
datasphere chunks list --document-id ID [-j]
datasphere chunks get --document-id ID --chunk-id ID [-j]
datasphere chunks delete --document-id ID --chunk-id ID [-f]
```

This test plan covers all functionality, edge cases, and error conditions for comprehensive validation of the datasphere command.
