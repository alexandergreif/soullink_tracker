# Tasks: Lua Memory Reading System

**Feature**: Specification Gap Analysis (Phase 1: Lua Memory Reading System)
**Branch**: `001-anything-we-still`
**Input**: Design documents from `/specs/001-anything-we-still/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/encounter_json_schema.json

## Execution Flow

This tasks.md implements Phase 1 of the Soullink Tracker project: **Lua Memory Reading System** for DeSmuME emulator integration. Following TDD workflow and constitutional requirements.

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- File paths are absolute or relative to repository root

## Phase 3.1: Setup

- [X] **T001** Create project directory structure
  - Create: `emulator/`, `src/models/`, `src/services/`, `tests/contract/`, `tests/integration/`, `tests/unit/`, `data/encounters/`
  - Create: `.gitkeep` files in empty directories
  - **Files**: Repository root structure
  - **Dependencies**: None

- [X] **T002** Initialize Python project dependencies
  - Create: `requirements.txt` with dependencies (pydantic, pytest, jsonschema, watchdog, fastapi, uvicorn, sqlite3)
  - Run: `pip install -r requirements.txt`
  - **Files**: `requirements.txt`
  - **Dependencies**: T001

- [X] **T003** [P] Create .gitignore file
  - Ignore: `*.db`, `data/encounters/*.json`, `__pycache__/`, `.pytest_cache/`, `*.pyc`, `venv/`
  - **Files**: `.gitignore`
  - **Dependencies**: T001

- [X] **T004** [P] Create Lua configuration template
  - Create: `emulator/config_template.lua` with CONFIG table (player_name, json_output_dir, polling_interval, enable_logging, track_legendaries)
  - Include: Comments explaining each configuration parameter
  - **Files**: `emulator/config_template.lua`
  - **Dependencies**: T001

- [X] **T004a** [P] Setup Playwright MCP for manual testing automation
  - Prerequisites: Windows PC with VSCode + Claude Code installed
  - Install: Playwright MCP server (`npm install -g @playwright/mcp-server` or equivalent)
  - Configure: VSCode settings to enable Playwright MCP integration
  - Create: `tests/debug_logs/` directory for capture artifacts
  - Create: `tests/debug_logs/screenshots/` subdirectory
  - Verify: Playwright can capture screenshots and interact with Windows applications
  - **Files**: MCP configuration, `tests/debug_logs/` directories
  - **Dependencies**: T001
  - **Note**: Environment-documented on macOS; full Playwright MCP setup requires Windows environment

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3

**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

- [X] **T005** [P] Contract test for encounter JSON schema validation
  - Create: `tests/contract/test_encounter_json_schema.py`
  - Test: Load `contracts/encounter_json_schema.json` and validate sample valid/invalid JSON against schema
  - Test cases:
    - Valid encounter JSON (wild Pokemon)
    - Valid legendary encounter JSON
    - Invalid: species_id out of range (0, 494)
    - Invalid: level out of range (0, 101)
    - Invalid: missing required fields
    - Invalid: current_hp > max_hp
    - Invalid: status not in enum values
  - Expected: All tests FAIL (no JSON files exist yet)
  - **Files**: `tests/contract/test_encounter_json_schema.py`
  - **Dependencies**: T002

- [X] **T006** [P] Integration test for encounter pipeline (JSON → Database)
  - Create: `tests/integration/test_encounter_pipeline.py`
  - Test cases:
    - Single player encounter tracking (JSON file → SQLite insert)
    - Soullink duplicate detection (Alice catches Pikachu, Bob's attempt fails)
    - Legendary exemption (multiple players catch same legendary)
    - Status transitions (encountered → caught/ko/run)
  - Expected: All tests FAIL (no implementation exists)
  - **Files**: `tests/integration/test_encounter_pipeline.py`
  - **Dependencies**: T002

- [X] **T007** [P] Unit tests for Pydantic Encounter model validation
  - Create: `tests/unit/test_encounter_model.py`
  - Test cases:
    - Valid Encounter model instantiation
    - Field validation (species_id range, level range, hp constraints)
    - Optional fields (location_id, species_name can be None)
    - Type coercion (string timestamp → datetime)
  - Expected: All tests FAIL (model not implemented)
  - **Files**: `tests/unit/test_encounter_model.py`
  - **Dependencies**: T002

- [X] **T008** [P] Unit tests for Pydantic SoulinkRule model validation
  - Create: `tests/unit/test_soullink_rule_model.py`
  - Test cases:
    - Valid SoulinkRule model instantiation
    - Required fields validation (species_id, caught_by_player, caught_at)
    - Type validation (timestamp format)
  - Expected: All tests FAIL (model not implemented)
  - **Files**: `tests/unit/test_soullink_rule_model.py`
  - **Dependencies**: T002

## Phase 3.3: Core Implementation (ONLY after tests are failing)

**Python Data Models** (Parallel - different files)

- [X] **T009** [P] Implement Encounter Pydantic model
  - Create: `src/models/encounter.py`
  - Fields: timestamp, player_name, species_id, species_name (optional), level, current_hp, max_hp, location_id (optional), location_name (optional), encounter_type, status, personality_value
  - Validators: species_id [1,493], level [1,100], current_hp ≤ max_hp, encounter_type enum, status enum
  - **Files**: `src/models/encounter.py`
  - **Dependencies**: T007 (test must be failing)
  - **Makes Pass**: T007

- [X] **T010** [P] Implement SoulinkRule Pydantic model
  - Create: `src/models/soullink_rule.py`
  - Fields: species_id, caught_by_player, caught_at
  - Validators: species_id [1,493], timestamp format validation
  - **Files**: `src/models/soullink_rule.py`
  - **Dependencies**: T008 (test must be failing)
  - **Makes Pass**: T008

- [X] **T011** [P] Create species reference data (embedded table)
  - Create: `src/models/species_reference.py`
  - Data: Dictionary mapping species_id [1-493] → species_name (Gen 4 National Dex)
  - Include: Legendary species list (18 species: Articuno, Zapdos, Moltres, Mewtwo, Raikou, Entei, Suicune, Lugia, Ho-Oh, Latias, Latios, Kyogre, Groudon, Rayquaza, Dialga, Palkia, Giratina, Arceus)
  - Functions: `get_species_name(species_id)`, `is_legendary(species_id)`
  - **Files**: `src/models/species_reference.py`
  - **Dependencies**: T001

**Lua Memory Reading Script** (Sequential - single file)

- [X] **T012** Implement Lua memory reading functions
  - Create: `emulator/hgss_encounter_tracker.lua`
  - Implement:
    - `read_personality_value(pokemon_addr)` - Read PID at offset 0x00
    - `calculate_block_shuffle(pid)` - Calculate block order from PID
    - `decrypt_species_id(pokemon_addr, pid)` - Decrypt Block A, extract species ID
    - `read_level(pokemon_addr)` - Read level at offset 0x8C
    - `read_hp(pokemon_addr)` - Read current_hp (0x8E), max_hp (0x90)
  - Memory addresses: PARTY_POINTER_ADDR = 0x0211186C, ENEMY_OFFSET = 0x37970
  - Error handling: Validate memory.isvalid(), range checks
  - **Files**: `emulator/hgss_encounter_tracker.lua`
  - **Dependencies**: T004

- [X] **T013** Implement encounter detection and classification logic
  - Add to: `emulator/hgss_encounter_tracker.lua`
  - Implement:
    - `check_enemy_pokemon_exists()` - Check if enemy pointer is non-null
    - `classify_encounter_type(species_id)` - Return "wild" or "legendary" based on species list
    - `detect_new_encounter()` - State machine to detect new encounters (avoid re-exporting same encounter)
  - State tracking: Store last exported PID to prevent duplicates
  - **Files**: `emulator/hgss_encounter_tracker.lua`
  - **Dependencies**: T012

- [X] **T014** Implement JSON export functionality
  - Add to: `emulator/hgss_encounter_tracker.lua`
  - Implement:
    - `generate_timestamp()` - ISO 8601 format (UTC timezone)
    - `generate_filename(timestamp, player_name)` - Format: encounter_YYYYMMDD_HHMMSS_PlayerName.json
    - `build_encounter_json(pokemon_data)` - Construct JSON structure matching schema
    - `write_json_file(filepath, encounter_json)` - Write JSON to file (error handling)
  - JSON fields: All fields from `contracts/encounter_json_schema.json`, status="encountered"
  - Error handling: Log to DeSmuME console with [INFO]/[ERROR] prefixes
  - **Files**: `emulator/hgss_encounter_tracker.lua`
  - **Dependencies**: T013

- [X] **T015** Implement polling loop and configuration validation
  - Add to: `emulator/hgss_encounter_tracker.lua`
  - Implement:
    - `validate_config()` - Check player_name not empty, json_output_dir exists
    - `main_loop()` - Poll every CONFIG.polling_interval seconds
    - Error handling: Graceful degradation, console logging
  - Integration: Call detect_new_encounter() → extract data → write JSON
  - Console logging: Startup message, encounter detection messages, error messages
  - **Files**: `emulator/hgss_encounter_tracker.lua`
  - **Dependencies**: T014

- [X] **T016** Validate Lua script meets contract test requirements
  - Run: `pytest tests/contract/test_encounter_json_schema.py`
  - Manual: Generate sample JSON files using Lua script (create test_encounter.json manually if needed)
  - Verify: All contract tests pass
  - **Files**: `tests/contract/test_encounter_json_schema.py` (validation only)
  - **Dependencies**: T015, T005
  - **Makes Pass**: T005

- [X] **T016a** [P] Create automated testing capture script
  - Create: `tests/capture_manual_test.py`
  - Implement:
    - `TestCaptureHandler(FileSystemEventHandler)` - Monitor JSON file creation
    - `validate_encounter_json(filepath)` - Real-time schema validation
    - `capture_performance_metrics()` - Measure latency (battle screen → JSON file)
    - `save_capture_report()` - Export debug data to `capture_report.json`
  - Integration: Use watchdog for filesystem monitoring
  - Integration: Use Playwright MCP for DeSmuME window screenshots (if available)
  - Output artifacts:
    - `tests/debug_logs/capture_report.json` - Encounter events with timestamps, latencies, validation results
    - `tests/debug_logs/screenshots/` - Battle screen captures (if Playwright available)
    - `tests/debug_logs/lua_console.txt` - Console output (manual copy-paste)
  - CLI: `python tests/capture_manual_test.py --start`
  - **Files**: `tests/capture_manual_test.py`
  - **Dependencies**: T002, T009, T005

## Phase 3.4: Manual Testing (Constitutional Requirement)

**GATE: Do NOT proceed to Phase 3.5 until manual testing passes**

- [ ] **T017** Manual testing with DeSmuME + HGSS ROM (Enhanced with automated capture)
  - Prerequisites:
    - DeSmuME 0.9.11+ with Pokemon HGSS (USA) ROM, save file near tall grass
    - Windows PC with VSCode + Claude Code installed
    - Playwright MCP configured (T004a) - optional but recommended
  - Automated capture setup:
    1. Run: `python tests/capture_manual_test.py --start`
    2. Script monitors `data/encounters/` and captures real-time data
    3. Load `emulator/hgss_encounter_tracker.lua` in DeSmuME Lua window
    4. Configure player_name and json_output_dir in script header
    5. Trigger 10+ wild encounters in game (capture script auto-records)
    6. Press CTRL+C to stop capture and save report
  - Test procedure (with automated capture):
    - Capture script automatically measures latency for each encounter
    - Real-time JSON schema validation (instant feedback on errors)
    - Optional: Playwright captures DeSmuME window screenshots at key moments
    - Manual: Copy DeSmuME Lua console output to `tests/debug_logs/lua_console.txt`
  - Generated artifacts (auto-saved):
    - `tests/debug_logs/capture_report.json` - All encounter events with metrics
    - `tests/debug_logs/screenshots/encounter_*.png` - Battle screens (if Playwright enabled)
    - `tests/debug_logs/lua_console.txt` - Console output (manual copy)
  - Success criteria:
    - No DeSmuME lag or frame drops (observed manually)
    - No Lua script errors in console output
    - All JSON files valid per schema (verified by capture script)
    - Species ID, level, HP match in-game Pokemon (manual verification)
    - Average latency <2 seconds (measured by capture script)
    - `capture_report.json` shows 10+ successful encounters with valid=true
  - AI-assisted debugging:
    - Feed `capture_report.json` to Claude Code for analysis
    - Claude identifies: Invalid species IDs, decryption failures, performance issues
    - Claude suggests: Memory address corrections, logic fixes in Lua script
  - Document: Test results summary in `tests/manual_testing_results.md`
  - **Files**: `tests/debug_logs/capture_report.json`, `tests/manual_testing_results.md`
  - **Dependencies**: T016, T016a
  - **Constitutional Gate**: MUST PASS before proceeding

## Phase 3.5: Integration (Database Preparation for Phase 3)

**Python Services** (Prepare for Phase 3: File Watcher)

- [ ] **T018** [P] Implement SQLite database initialization
  - Create: `src/services/database.py`
  - Implement:
    - `create_encounters_table()` - Schema from data-model.md (composite primary key: timestamp, player_name, personality_value)
    - `create_soullink_rules_table()` - Schema with UNIQUE constraint on species_id
    - `init_database()` - Create database file at `data/soullink_tracker.db`
    - CLI flag: `python src/services/database.py --init`
  - Indexes: species_id, player_name, status
  - **Files**: `src/services/database.py`
  - **Dependencies**: T009, T010

- [ ] **T019** [P] Implement database insert operations
  - Add to: `src/services/database.py`
  - Implement:
    - `insert_encounter(encounter: Encounter)` - Insert encounter, handle IntegrityError
    - `insert_soullink_rule(rule: SoulinkRule)` - Insert if NOT legendary, catch UNIQUE constraint violation
    - `query_encounters(**filters)` - Query with optional filters (player, species, status)
    - `check_duplicate_species(species_id)` - Check if species exists in soullink_rules
  - Error handling: Log constraint violations, return error status
  - **Files**: `src/services/database.py`
  - **Dependencies**: T018

- [ ] **T020** [P] Implement Python file watcher service (watchdog)
  - Create: `src/services/file_watcher.py`
  - Implement:
    - `EncounterFileHandler(FileSystemEventHandler)` - Handle on_created events
    - `process_encounter_file(filepath)` - Parse JSON, validate schema, insert to DB
    - `determine_soullink_action(encounter)` - If status="caught" AND NOT legendary → insert soullink_rule
    - CLI: `python src/services/file_watcher.py --watch <dir>`
  - Error handling: Malformed JSON, validation errors, database errors
  - Logging: Encounter processed, duplicate detected, errors
  - **Files**: `src/services/file_watcher.py`
  - **Dependencies**: T009, T019

## Phase 3.6: Integration Testing

- [ ] **T021** Run integration tests (JSON → Database)
  - Run: `pytest tests/integration/test_encounter_pipeline.py`
  - Prerequisites: Database initialized (T018), file watcher implemented (T020)
  - Test cases:
    - Create JSON file → watcher processes → encounter in DB
    - Alice catches Pikachu → soullink rule created
    - Bob tries to catch Pikachu → IntegrityError logged
    - Alice catches Lugia (legendary) → no soullink rule created
    - Bob catches Lugia → both encounters in DB
  - Verify: All integration tests pass
  - **Files**: `tests/integration/test_encounter_pipeline.py` (validation only)
  - **Dependencies**: T020, T006
  - **Makes Pass**: T006

## Phase 3.7: Polish

- [ ] **T022** [P] Add comprehensive logging to Lua script
  - Edit: `emulator/hgss_encounter_tracker.lua`
  - Add: Detailed console logging for all state transitions, errors, data validation
  - Format: `[INFO]`/`[ERROR]` prefixes with context (species ID, memory addresses)
  - **Files**: `emulator/hgss_encounter_tracker.lua`
  - **Dependencies**: T017

- [ ] **T023** [P] Add logging to Python services
  - Edit: `src/services/database.py`, `src/services/file_watcher.py`
  - Add: Python `logging` module with console output
  - Levels: INFO (encounters processed), WARNING (duplicates), ERROR (validation failures)
  - **Files**: `src/services/database.py`, `src/services/file_watcher.py`
  - **Dependencies**: T019, T020

- [ ] **T024** [P] Create README with launch sequence
  - Create: `README.md`
  - Content:
    - Project overview and Soullink rule explanation
    - Prerequisites (DeSmuME, HGSS ROM, Python 3.11+)
    - Setup instructions (install dependencies, initialize database)
    - Launch sequence (from CLAUDE.md § Launch Sequence)
    - Configuration guide (edit Lua script header)
    - Troubleshooting common errors
  - **Files**: `README.md`
  - **Dependencies**: T017, T021

- [ ] **T025** [P] Performance validation
  - Test: End-to-end latency (encounter detection → database insert)
  - Measure:
    - Lua polling interval (verify 1 second)
    - JSON export latency (target <1 second)
    - Python watcher processing (target <100ms)
    - Database query performance (target <100ms)
  - Success criteria: End-to-end <3 seconds
  - Document: Performance results in `tests/performance_results.md`
  - **Files**: `tests/performance_results.md`
  - **Dependencies**: T021

- [ ] **T026** Code cleanup and refactoring
  - Review: Remove debug print statements (keep logging only)
  - Review: Check for code duplication in Lua script
  - Review: Consistent error handling patterns
  - Review: Type hints in Python code
  - **Files**: All implementation files
  - **Dependencies**: T022, T023

## Dependencies

### Critical Path
```
Setup (T001-T004, T004a)
  → Tests Written (T005-T008) [MUST FAIL]
  → Python Models (T009-T011) [Make T007-T008 pass]
  → Lua Implementation (T012-T015) [Sequential in single file]
  → Contract Validation (T016) [Make T005 pass]
  → Capture Script (T016a) [Parallel with T016]
  → Manual Testing (T017) [CONSTITUTIONAL GATE - uses capture script]
  → Database Services (T018-T020) [Prepare for Phase 3]
  → Integration Tests (T021) [Make T006 pass]
  → Polish (T022-T027)
```

### Parallel Opportunities
- **T003, T004, T004a**: Different files/systems, no dependencies
- **T005-T008**: All test files, different files
- **T009-T011**: All model files, different files
- **T016, T016a**: Contract validation and capture script (independent)
- **T018-T019**: Different parts of database.py (T019 depends on T018)
- **T018, T020**: Database init and file watcher (T020 depends on T019, not T018)
- **T022-T024**: Different files (Lua, Python services, README)

### Blocking Dependencies
- T012-T015: Sequential (same Lua script file)
- T017: Blocks T018-T027 (constitutional gate)
- T016a → T017 (capture script enables enhanced manual testing)
- T018 → T019 (database must exist before insert operations)
- T019 → T020 (watcher needs insert operations)
- T006 → T021 (integration tests written first, validated after implementation)

## Parallel Execution Examples

### Example 1: Setup tasks in parallel
```bash
# Launch T003, T004, T004a together (different files/systems):
Task(prompt="Create .gitignore file with Python, database, and JSON file patterns")
Task(prompt="Create Lua configuration template in emulator/config_template.lua")
Task(prompt="Setup Playwright MCP for manual testing automation with screenshot capture")
```

### Example 2: Write all tests in parallel
```bash
# Launch T005-T008 together (all test files, independent):
Task(prompt="Write contract test for encounter JSON schema in tests/contract/test_encounter_json_schema.py")
Task(prompt="Write integration test for encounter pipeline in tests/integration/test_encounter_pipeline.py")
Task(prompt="Write unit tests for Encounter model in tests/unit/test_encounter_model.py")
Task(prompt="Write unit tests for SoulinkRule model in tests/unit/test_soullink_rule_model.py")
```

### Example 3: Implement Python models in parallel
```bash
# Launch T009-T011 together (all model files, independent):
Task(prompt="Implement Encounter Pydantic model in src/models/encounter.py")
Task(prompt="Implement SoulinkRule Pydantic model in src/models/soullink_rule.py")
Task(prompt="Create species reference data in src/models/species_reference.py")
```

### Example 4: Contract validation and capture script in parallel
```bash
# Launch T016, T016a together (independent tasks):
Task(prompt="Validate Lua script meets contract test requirements by running pytest")
Task(prompt="Create automated testing capture script in tests/capture_manual_test.py with watchdog and Playwright integration")
```

### Example 5: Polish tasks in parallel
```bash
# Launch T022-T024 together (different files):
Task(prompt="Add comprehensive logging to Lua script emulator/hgss_encounter_tracker.lua")
Task(prompt="Add logging to Python services src/services/database.py and src/services/file_watcher.py")
Task(prompt="Create README.md with launch sequence and troubleshooting")
```

## Task Validation Checklist

- [x] All contracts have corresponding tests (T005 for encounter_json_schema.json)
- [x] All entities have model tasks (T009 Encounter, T010 SoulinkRule, T011 SpeciesReference)
- [x] All tests come before implementation (T005-T008 before T009-T015)
- [x] Parallel tasks truly independent ([P] marks verified for different files)
- [x] Each task specifies exact file path (all tasks include file paths)
- [x] No task modifies same file as another [P] task (Lua script is sequential T012-T015)
- [x] Constitutional requirements met (Manual testing gate T017, TDD workflow enforced)

## Notes

- **TDD Workflow**: Tests T005-T008 MUST be written first and MUST FAIL before implementation
- **Constitutional Gate**: T017 (manual testing) MUST PASS before proceeding to database work
- **Single Lua File**: T012-T015 are sequential (same file: hgss_encounter_tracker.lua)
- **Phase 1 Focus**: This tasks.md covers only Phase 1 (Lua Memory Reading). Phase 2-6 specifications will be created separately.
- **Commit Strategy**: Commit after each task completion for incremental validation
- **Performance Targets**: All tasks must respect constitutional performance requirements (1s polling, <1s export, <3s end-to-end)

## Estimated Task Completion Times

- **Setup (T001-T004, T004a)**: 1 hour (project structure + Playwright MCP setup)
- **Tests (T005-T008)**: 2 hours (4 test files)
- **Python Models (T009-T011)**: 1.5 hours (3 model files)
- **Lua Script (T012-T016)**: 6 hours (complex memory reading, decryption logic)
- **Capture Script (T016a)**: 1 hour (automated testing capture with watchdog)
- **Manual Testing (T017)**: 1.5 hours (ROM setup, 10+ encounters with automated capture - faster than manual)
- **Database Services (T018-T020)**: 3 hours (SQLite schema, watchdog integration)
- **Integration Testing (T021)**: 1 hour (run tests, debug failures)
- **Polish (T022-T026)**: 2 hours (logging, docs, cleanup)

**Total Estimated Time**: 19 hours for Phase 1 completion (1 hour saved on T017 due to automation, 1 hour added for Playwright setup + capture script)
