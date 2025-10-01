# Project Status and Next Steps

**Project**: Soullink Tracker - Phase 1 (Lua Memory Reading System)
**Branch**: `001-anything-we-still`
**Date**: 2025-10-01

## Current Status

### ✅ Completed Work

1. **Task Breakdown Generated**: `specs/001-anything-we-still/tasks.md` created with 26 tasks
   - Setup tasks (T001-T004)
   - TDD test workflow (T005-T008)
   - Python models (T009-T011)
   - Lua script development (T012-T015)
   - Contract validation (T016)
   - Manual testing (T017)
   - Database services (T018-T020)
   - Integration testing (T021)
   - Polish tasks (T022-T026)

2. **Manual Testing Enhancement**: Added automated capture tooling
   - **T004a**: Setup Playwright MCP for debugging/tracing
   - **T016a**: Create automated testing capture script
   - **T017** (Enhanced): Manual ROM testing with automated capture integration

3. **Tasks.md Structure Updated**:
   - Dependencies section updated
   - Parallel execution markers [P] added for 11 concurrent tasks
   - Estimated completion times: 20-24 hours total

### 🔄 Pending Work

**Priority Task**: Create `tests/capture_manual_test.py`

**Purpose**: Automated monitoring tool for manual ROM testing (T016a)

**Features to Implement**:
- `TestCaptureHandler` class (extends `FileSystemEventHandler` from watchdog)
- Real-time JSON file monitoring in `data/encounters/` directory
- Automatic schema validation using `jsonschema` + Pydantic models
- Performance metric capture:
  - Latency: Battle screen appearance → JSON file creation
  - File creation timestamps
  - Validation pass/fail tracking
- Playwright MCP integration (placeholder for screenshot capture)
- Debug report generation: `tests/debug_logs/capture_report.json`
- CLI interface: `python tests/capture_manual_test.py --start`

**Output Format** (AI-friendly debug report):
```json
{
  "test_session": {
    "start_time": "2025-10-01T14:30:00Z",
    "end_time": "2025-10-01T15:15:00Z",
    "duration_seconds": 2700
  },
  "summary": {
    "total_encounters": 12,
    "valid_encounters": 11,
    "failed_validations": 1,
    "avg_latency_seconds": 1.8,
    "max_latency_seconds": 2.4
  },
  "events": [
    {
      "timestamp": "2025-10-01T14:32:15Z",
      "filepath": "encounter_20251001_143215_TestPlayer.json",
      "validation_status": "valid",
      "latency_seconds": 1.6,
      "species_id": 19,
      "level": 3
    }
  ]
}
```

## Next Steps

### Immediate Actions

1. **Create the capture script**:
   ```bash
   # This will be created as: tests/capture_manual_test.py
   # Status: Ready to implement (was interrupted during creation)
   ```

2. **Begin implementation workflow** (after capture script is ready):
   ```bash
   # Execute tasks in dependency order:
   # T001-T004 → Setup tasks (sequential)
   # T004a → Playwright MCP setup
   # T005-T008 → Write tests (TDD red phase)
   # T009-T011 → Python models (can run in parallel)
   # T012-T015 → Lua script (sequential, single file)
   # T016 → Contract validation
   # T016a → Run capture script setup
   # T017 → Manual ROM testing with capture
   ```

### Implementation Order

**Phase 1: Infrastructure** (Sequential - 2 hours)
- T001: Project directories
- T002: Requirements.txt
- T003: .gitignore
- T004: Config template
- T004a: Playwright MCP

**Phase 2: Tests First** (Parallel - 3 hours)
- T005 [P]: Contract test (encounter JSON schema)
- T006 [P]: Integration test skeleton
- T007 [P]: Unit test (Soullink rules)
- T008 [P]: Unit test (species reference)

**Phase 3: Models** (Parallel - 2 hours)
- T009 [P]: Encounter model (Pydantic)
- T010 [P]: SoulinkRule model (Pydantic)
- T011 [P]: SpeciesReference stub

**Phase 4: Lua Implementation** (Sequential - 6 hours)
- T012: Memory reading functions
- T013: Species decryption
- T014: Encounter detection loop
- T015: JSON export

**Phase 5: Validation Gate** (Sequential - 3 hours)
- T016: Contract test validation (must be green)
- T016a: Capture script execution
- T017: **CONSTITUTIONAL GATE** - Manual ROM testing (10+ encounters)

**Phase 6: Database Layer** (After T017 passes - 4 hours)
- T018 [P]: Database service (SQLite)
- T019 [P]: Database tests
- T020: File watcher service

**Phase 7: Integration & Polish** (4 hours)
- T021: End-to-end integration test
- T022-T026: Logging, docs, performance, code review

## Key Technical Details

### Memory Addresses (HGSS USA)
```
Base Pointer: 0x0211186C (party pointer)
Enemy Offset: +0x37970
Species ID: Requires PID-based decryption (block shuffle)
Level: Offset 0x34 (unencrypted)
Current HP: Offset 0x4C-0x4D (unencrypted)
Max HP: Offset 0x4E-0x4F (unencrypted)
Personality ID: Offset 0x68-0x6B (32-bit)
```

### DeSmuME Lua API
```lua
-- Memory reading functions
memory.readword(address)     -- Read 16-bit value
memory.readdword(address)    -- Read 32-bit value
memory.readbyte(address)     -- Read 8-bit value
```

### Constitutional Requirements

**Manual Testing Gate (T017)**: MUST pass before database work begins
- Minimum 10 wild encounters tested
- All JSON files valid (schema compliance)
- Performance targets met:
  - Polling: 1 second intervals
  - JSON export: <1 second latency
  - No DeSmuME lag/crashes

**Test-First Development**: Tests written → approved → fail → implement

**Offline Resilience**: JSON queue survives crashes (single file per encounter)

## Development Environment

**Required Tools**:
- DeSmuME 0.9.11+ (Windows)
- Pokemon HGSS ROM (USA version)
- Python 3.11+
- VSCode + Claude Code
- Playwright MCP (for debugging/tracing)

**Python Dependencies** (requirements.txt):
```
pydantic==2.5.0
pytest==7.4.3
jsonschema==4.20.0
watchdog==3.0.0
fastapi==0.104.1
uvicorn==0.24.0
python-dotenv==1.0.0
```

## Questions to Resolve

**None currently** - all clarifications completed during planning phase.

## References

- **Specification**: `specs/001-anything-we-still/spec.md`
- **Implementation Plan**: `specs/001-anything-we-still/plan.md`
- **Technical Research**: `specs/001-anything-we-still/research.md`
- **Data Model**: `specs/001-anything-we-still/data-model.md`
- **Task Breakdown**: `specs/001-anything-we-still/tasks.md`
- **Integration Tests**: `specs/001-anything-we-still/quickstart.md`
- **JSON Contract**: `specs/001-anything-we-still/contracts/encounter_json_schema.json`
- **Constitution**: `.specify/memory/constitution.md`

---

**Status**: Ready to create `tests/capture_manual_test.py` and begin implementation workflow.
