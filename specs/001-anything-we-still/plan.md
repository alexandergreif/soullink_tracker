
# Implementation Plan: Specification Gap Analysis (Phase 1: Lua Memory Reading System)

**Branch**: `001-anything-we-still` | **Date**: 2025-10-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-anything-we-still/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from file system structure or context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code or `AGENTS.md` for opencode).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary

This feature implements the **Lua Memory Reading System** for DeSmuME emulator, enabling real-time Pokemon encounter detection in Heart Gold/Soul Silver. The system polls emulator memory every 1 second to detect wild Pokemon encounters, extracts species/level/HP data from encrypted Pokemon data structures, and exports encounters to JSON files for downstream processing. This is Phase 1 of the 6-phase Soullink Tracker project and is the constitutional priority ("Emulator Integration First").

## Technical Context
**Language/Version**: Lua 5.1 (DeSmuME embedded), Python 3.11+ (downstream processing)
**Primary Dependencies**: DeSmuME 0.9.11+ (Lua support), Lua stdlib only (no external libs)
**Storage**: JSON files (encounter queue), SQLite3 (downstream database)
**Testing**: Manual testing with HGSS ROM (automated mocking not feasible), contract tests for JSON schema (Python/pytest)
**Target Platform**: Windows-only (DeSmuME Lua support), Pokemon HGSS USA version
**Project Type**: Hybrid (Lua scripts + Python services + Web dashboard)
**Performance Goals**: 1-second polling interval, <1s JSON export latency, <3s end-to-end encounter detection
**Constraints**: No DeSmuME lag/crashes, offline-resilient (JSON queue), 3 concurrent players
**Scale/Scope**: MVP targets single-player validation, expand to 3-player coordination in Phase 7

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Emulator Integration First ✅ PASS
- **Requirement**: Memory reading validated before downstream components
- **Status**: This feature IS the memory reading layer (Phase 1)
- **Validation**: Manual testing with real ROM required before Phase 2 begins

### II. Incremental Validation ✅ PASS
- **Requirement**: Build one layer at a time
- **Status**: Lua memory reading is the first layer (no dependencies)
- **Next Gate**: JSON queue validated before Python watcher (Phase 3)

### III. Test-First Development ⚠️ PARTIAL
- **Requirement**: Tests written first, approved, must fail
- **Challenge**: Lua memory reading cannot be unit tested (DeSmuME dependency)
- **Mitigation**: Contract tests for JSON output schema (Python pytest), manual testing with ROM
- **Justification**: Emulator integration requires manual validation (constitutional acknowledgment: "Manual Testing Gates")

### IV. Manual Testing Gates ✅ PASS
- **Requirement**: Emulator changes tested with real ROM
- **Status**: Explicitly planned (see research.md § 11 Performance Validation)
- **Checklist**: 10+ encounters, stopwatch latency measurement, console error monitoring

### V. Simplicity Over Features ✅ PASS
- **Requirement**: MVP only, no scope creep
- **Status**: Tracking species/level/HP only (no IVs, natures, moves)
- **Deferred**: Location tracking (address unknown, not blocking)

### VI. Offline Resilience ✅ PASS
- **Requirement**: No data loss from crashes
- **Status**: JSON files persist encounters (survive Lua script/watcher crashes)
- **Design**: Single file per encounter (atomic writes)

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
emulator/
├── hgss_encounter_tracker.lua   # Main Lua script for DeSmuME
└── config_template.lua          # Configuration template (player name, paths)

src/
├── models/
│   ├── encounter.py             # Encounter entity (Pydantic model)
│   └── soullink_rules.py        # Duplicate detection rules
├── services/
│   ├── file_watcher.py          # Python watchdog service (Phase 3)
│   └── database.py              # SQLite operations (Phase 4)
└── api/
    └── main.py                  # FastAPI + WebSocket (Phase 5)

frontend/
├── index.html                   # Web dashboard (Phase 6)
├── styles.css                   # Tailwind CSS (CDN)
└── app.js                       # Vanilla JavaScript

tests/
├── contract/
│   └── test_encounter_json_schema.py  # Validate JSON output from Lua
├── integration/
│   └── test_encounter_pipeline.py     # End-to-end (mock JSON → DB)
└── unit/
    └── test_soullink_rules.py         # Duplicate detection logic

data/
├── encounters/                  # JSON queue directory
│   └── .gitkeep
└── soullink_tracker.db          # SQLite database (gitignored)
```

**Structure Decision**: Hybrid structure with emulator layer (Lua scripts) separate from Python backend and vanilla JS frontend. Lua scripts live in `emulator/` to avoid mixing with Python code. Single `src/` directory for Python components (models/services/api), single `tests/` directory mirroring source structure. Frontend is minimal (no build step, CDN dependencies).

## Phase 0: Outline & Research ✅ COMPLETE

**Research Performed**:
1. ✅ DeSmuME Lua API investigation (memory reading functions)
2. ✅ Pokemon Gen 4 data structure analysis (encryption, offsets)
3. ✅ HGSS memory address verification (party pointer, enemy offset)
4. ✅ Working Lua script examples (PokeStats, PokeLua, RNG scripts)
5. ✅ Encounter detection strategy (hybrid polling approach)
6. ✅ JSON export format design (single file per encounter)
7. ✅ Performance requirements validation (1s polling, <1s export)

**Key Findings** (see research.md for full details):
- DeSmuME uses `memory.readword()` / `memory.readdword()` (not `memory.read_u16_le`)
- Species ID requires decryption (PID-based block shuffling)
- Base pointer: `0x0211186C`, enemy offset: `+0x37970`
- Level/HP stored unencrypted at fixed offsets
- Location address unknown (deferred to future research, not blocking)

**Output**: ✅ research.md created with 14 technical decisions documented

## Phase 1: Design & Contracts ✅ COMPLETE

**Entities Extracted**:
1. ✅ **Encounter**: Core entity tracking Pokemon encounters (11 fields, state transitions)
2. ✅ **SoulinkRule**: Duplicate detection enforcement (3 fields, UNIQUE constraint)
3. ⏳ **SpeciesReference**: Species ID lookup table (deferred to Phase 4)
4. ⏳ **Player**: Multi-player coordination (deferred to Phase 7)

**Contracts Generated**:
- ✅ `contracts/encounter_json_schema.json`: JSON Schema (Draft 7) for Lua export format
- ✅ `contracts/README.md`: Contract documentation and testing strategy
- ⏳ `contracts/api_openapi_spec.yaml`: REST API specification (Phase 5)
- ⏳ `contracts/websocket_message_protocol.json`: WebSocket events (Phase 5)

**Integration Test Scenario**:
- ✅ `quickstart.md`: End-to-end test (manual ROM testing + automated Python tests)
- Manual test: DeSmuME → Lua → JSON validation
- Automated test: JSON → Python watcher → SQLite
- Test cases: Single encounter, duplicate detection, legendary exemption

**Agent Context Updated**:
- ✅ `CLAUDE.md` updated via `update-agent-context.sh claude`
- Added: Lua 5.1, DeSmuME, JSON queue, SQLite3
- Preserved: Constitutional principles, memory addresses

**Output**: ✅ data-model.md, contracts/, quickstart.md, CLAUDE.md updated

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
The `/tasks` command will generate a TDD-ordered task breakdown focusing on Phase 1 (Lua Memory Reading System):

**Lua Script Development** (Core Focus):
1. **Contract Test Tasks**:
   - Write contract test for JSON schema validation (Python pytest)
   - Test must fail initially (no JSON files exist yet)

2. **Lua Implementation Tasks**:
   - Task: Write Lua memory reading functions (PID, species, level, HP) [P]
   - Task: Write species ID decryption logic (block shuffle algorithm) [P]
   - Task: Write encounter detection loop (1-second polling) [P]
   - Task: Write JSON export function (file naming, formatting) [P]
   - Task: Integrate components into main script
   - Task: Add error handling and console logging

3. **Manual Testing Tasks**:
   - Task: Test with DeSmuME + HGSS ROM (10+ encounters)
   - Task: Validate JSON schema compliance (run contract tests)
   - Task: Measure performance (latency, no lag)
   - Task: Document memory addresses if discrepancies found

**Python Support Tasks** (Preparation for Phase 3):
4. **Data Model Tasks**:
   - Task: Create Pydantic `Encounter` model [P]
   - Task: Create Pydantic `SoulinkRule` model [P]
   - Task: Write unit tests for model validation [P]

5. **Infrastructure Tasks**:
   - Task: Create project directories (emulator/, src/, tests/, data/)
   - Task: Create requirements.txt (pydantic, pytest, jsonschema)
   - Task: Create .gitignore (*.db, data/encounters/*.json)

**Ordering Strategy**:
- Infrastructure first (directories, dependencies)
- Contract tests second (failing tests, TDD red phase)
- Lua implementation third (make tests pass, TDD green phase)
- Manual testing fourth (constitutional requirement)
- Python models fifth (preparation for Phase 3)

**Parallelization** [P]:
- Lua functions can be written in parallel (independent logic)
- Python models can be written in parallel (no dependencies)
- Manual testing is sequential (requires completed Lua script)

**Estimated Output**: 15-18 tasks in tasks.md (focused on Phase 1 only)

**Constitutional Gates**:
- Manual testing gate MUST pass before Phase 3 begins
- All contract tests MUST be green before Phase 2 completion

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Test-First (Partial) | Lua memory reading cannot be unit tested | DeSmuME Lua API requires emulator runtime, mocking infeasible |
| Manual Testing Required | Emulator integration validation | Constitutional acknowledgment: "Manual Testing Gates" principle |

**Justification**: The partial TDD violation is acknowledged by Constitutional Principle IV ("Manual Testing Gates"). Contract tests validate JSON output schema (automated), while memory reading logic requires manual ROM testing (unavoidable emulator dependency).

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS (with documented TDD partial exemption)
- [x] Post-Design Constitution Check: PASS (no new violations from design)
- [x] All NEEDS CLARIFICATION resolved (via Phase 0 research)
- [x] Complexity deviations documented (manual testing requirement)

**Artifacts Created**:
- [x] research.md (14 technical decisions, 12 sections)
- [x] data-model.md (4 entities, validation rules, data flow)
- [x] contracts/encounter_json_schema.json (JSON Schema Draft 7)
- [x] contracts/README.md (usage documentation)
- [x] quickstart.md (manual + automated test scenarios)
- [x] CLAUDE.md updated (Lua 5.1, DeSmuME, SQLite context)

**Ready for /tasks**: ✅ YES

---
*Based on Constitution v1.0.0 - See `.specify/memory/constitution.md`*
