<!--
Sync Impact Report:
- Version change: N/A (initial constitution) → 1.0.0
- Modified principles: N/A (initial version)
- Added sections: All core principles, Technical Standards, Development Workflow, Governance
- Removed sections: None
- Templates requiring updates:
  ✅ .specify/templates/plan-template.md (Constitution Check section will reference these principles)
  ✅ .specify/templates/spec-template.md (Aligned with testability and clarity requirements)
  ✅ .specify/templates/tasks-template.md (Aligned with TDD and incremental validation principles)
  ✅ .claude/commands/*.md (Generic guidance maintained, no agent-specific constraints)
- Follow-up TODOs: None
- Notes: Initial constitution based on project requirements for Pokemon Soullink Tracker with emphasis on emulator data extraction reliability after previous implementation challenges.
-->

# Soullink Tracker Constitution

## Core Principles

### I. Emulator Integration First (CRITICAL)
Memory reading from DeSmuME is the foundation of this system. All data extraction MUST be validated before downstream components are built.

**Non-Negotiable Rules**:
- Memory address correctness MUST be verified against known working examples
- Species ID, level, HP, and location data MUST match in-game values within 1 polling cycle
- Lua scripts MUST continue running after encounter detection (no crashes/hangs)
- JSON export MUST complete within 1 second of encounter detection
- Data extraction MUST be manually tested with real ROM before integration work begins

**Rationale**: Previous implementation attempts failed primarily at the emulator data extraction layer. No downstream feature (database, API, UI) has value if the source data is corrupted or missing.

### II. Incremental Validation (NON-NEGOTIABLE)
Build and validate one layer at a time. Never proceed to the next component until the current one is proven working.

**Non-Negotiable Rules**:
- Lua memory reading validated standalone before JSON export
- JSON file format validated before Python watcher integration
- Database insertion validated before API development
- API endpoints validated before WebSocket implementation
- WebSocket delivery validated before UI development

**Rationale**: The previous implementation attempted to build multiple layers concurrently, making it impossible to isolate where data corruption occurred. Sequential validation creates clear fault boundaries.

### III. Test-First Development (NON-NEGOTIABLE)
Tests are written first, approved by user, must fail, then implementation proceeds.

**Non-Negotiable Rules**:
- Contract tests written for every API endpoint before implementation
- Integration tests written for every user scenario before implementation
- Unit tests written for critical logic (duplicate detection, memory parsing)
- Tests MUST fail initially (red phase)
- Implementation proceeds only after test approval
- Green phase achieved through minimal code
- Refactoring only after tests pass

**Rationale**: TDD enforces clear requirements and prevents scope creep. Red-Green-Refactor cycle ensures implementations are driven by specifications, not assumptions.

### IV. Manual Testing Gates
Automated tests cannot validate emulator memory reading or real-time encounter detection. Manual testing is required.

**Non-Negotiable Rules**:
- Every Lua script change MUST be tested with DeSmuME + real ROM
- Memory address reads MUST be verified against known Pokemon encounters
- JSON output MUST be manually inspected for correct species/level/location
- End-to-end latency (encounter → UI display) MUST be measured with stopwatch
- Multi-player scenarios MUST be tested with 3 concurrent users before release

**Rationale**: This system interfaces with binary memory structures that cannot be mocked. Real-world validation is mandatory.

### V. Simplicity Over Features
MVP focuses on core Soullink rule: one species per group. Advanced features come later.

**Non-Negotiable Rules**:
- No IV/nature/moves tracking in MVP
- No automated death tracking in MVP
- No partnership matching in MVP
- SQLite over cloud databases initially
- Vanilla JavaScript over React/Vue frameworks
- Manual action buttons (catch/KO/run) over full automation

**Rationale**: Previous attempts likely suffered from scope creep. A working simple system beats a broken complex one.

### VI. Offline Resilience
Players should never lose encounter data due to network issues or crashes.

**Non-Negotiable Rules**:
- JSON files act as persistent queue (survive Python watcher crashes)
- SQLite database ensures local data persistence
- WebSocket disconnections MUST NOT lose buffered encounters
- Emulator restarts MUST be handled gracefully (Lua script reload)

**Rationale**: Soullink runs can last 20+ hours. Data loss would invalidate the entire run.

## Technical Standards

### Memory Address Correctness
- Use verified HGSS USA memory addresses from projectpokemon.org
- Document source for every memory offset used
- Cross-reference with working GitHub examples
- Test with multiple ROM versions if discrepancies found

### Performance Requirements
- Memory polling: Every 1 second (no faster to avoid overhead)
- JSON export: < 1 second from encounter trigger
- Database queries: < 100ms response time
- End-to-end latency: < 3 seconds (encounter → UI update)
- WebSocket message size: < 5KB per encounter

### Error Handling
- Lua scripts MUST log errors to DeSmuME console
- Python watcher MUST log file I/O errors with timestamps
- Database operations MUST use transactions (rollback on failure)
- API endpoints MUST return structured error responses
- WebSocket errors MUST trigger reconnection logic

### Code Organization
- Single project structure (src/, tests/ at repo root)
- Separate concerns: models/, services/, api/, cli/
- Tests mirror source structure: tests/unit/, tests/integration/, tests/contract/
- Lua scripts in emulator/ directory (not mixed with Python)

## Development Workflow

### Specification-Driven Development
1. Feature described in plain language (/specify command)
2. Ambiguities resolved through clarification (/clarify command)
3. Technical plan created with research phase (/plan command)
4. Tasks generated with TDD ordering (/tasks command)
5. Implementation follows task sequence with validation gates

### TDD Workflow (Mandatory)
1. Write test (red phase)
2. User approves test logic
3. Verify test fails for right reason
4. Write minimal implementation (green phase)
5. Refactor if needed (maintain green)
6. Commit with test + implementation together

### Manual Testing Checkpoints
- Lua script changes: Test in DeSmuME immediately
- Python watcher changes: Test with real JSON files
- Database changes: Verify with SQLite CLI queries
- API changes: Test with curl/Postman before UI
- UI changes: Test in browser with real WebSocket connection

### Version Control
- Feature branches: `###-feature-name` format
- Atomic commits: One task = one commit
- Commit messages: Imperative mood ("Add species duplicate check")
- No force pushes to main/master
- Pull requests require constitution compliance verification

## Governance

### Amendment Process
1. Proposed change documented with rationale
2. Impact analysis on existing features
3. Template updates identified (plan, spec, tasks)
4. Version bump determined (MAJOR/MINOR/PATCH)
5. Constitution updated with sync impact report
6. Dependent artifacts updated to maintain consistency

### Versioning Policy
- **MAJOR**: Principle removal or incompatible governance change
- **MINOR**: New principle added or existing principle significantly expanded
- **PATCH**: Clarifications, typo fixes, non-semantic improvements

### Compliance Review
- All feature plans MUST pass Constitution Check gates
- Complexity deviations MUST be documented with justification
- Manual testing gates MUST be completed before feature approval
- TDD violations result in implementation rejection

### Constitution Authority
This constitution supersedes all other development practices. When conflicts arise between this document and external conventions, constitutional principles take precedence. Justified exceptions must be documented in the Complexity Tracking section of implementation plans.

**Version**: 1.0.0 | **Ratified**: 2025-10-01 | **Last Amended**: 2025-10-01
