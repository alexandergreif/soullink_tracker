# API Contracts

This directory contains contracts (schemas, interface definitions) for the Soullink Tracker system.

## Files

### `encounter_json_schema.json`
JSON Schema (Draft 7) defining the structure of encounter data exported by the DeSmuME Lua script.

**Purpose**: Validate that JSON files written by `hgss_encounter_tracker.lua` conform to the expected format before Python watcher processes them.

**Usage**:
```python
import json
import jsonschema

# Load schema
with open('contracts/encounter_json_schema.json') as f:
    schema = json.load(f)

# Validate encounter JSON
with open('data/encounters/encounter_20251001_143052_Alice.json') as f:
    encounter = json.load(f)

jsonschema.validate(encounter, schema)  # Raises ValidationError if invalid
```

**Contract Test**: `tests/contract/test_encounter_json_schema.py` validates sample JSON files against this schema.

## Future Contracts (Phase 5: FastAPI)

### `api_openapi_spec.yaml` (Not yet created)
OpenAPI 3.0 specification for REST API endpoints:
- `GET /encounters` - List encounters (with filters: player, species, status)
- `POST /encounters/{id}/status` - Update encounter status (caught/ko/run)
- `GET /soullink/rules` - List species caught by any player

### `websocket_message_protocol.json` (Not yet created)
JSON schema for WebSocket messages pushed to connected clients:
- `encounter.created` event (new encounter detected)
- `encounter.status_updated` event (user action applied)
- `soullink.rule_added` event (species caught, duplicate blocked)

## Testing Strategy

1. **Contract Tests** (Phase 1): Validate JSON schema with sample data
2. **Integration Tests** (Phase 2): Test end-to-end (Lua → JSON → Python → DB)
3. **API Tests** (Phase 5): Validate OpenAPI spec with Postman/pytest

**Constitutional Requirement**: Tests written first, approved, must fail, then implement (TDD).
