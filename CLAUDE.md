# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Claude Code Specialized Agents

Claude Code has access to specialized agents that can be called with the Task tool using the appropriate `subagent_type`:

- **general-purpose**: Research complex questions, search for code, execute multi-step tasks. Use when searching for keywords/files across large codebases
- **statusline-setup**: Configure Claude Code status line settings (Tools: Read, Edit)
- **output-mode-setup**: Create Claude Code output modes (Tools: Read, Write, Edit, Glob, LS)
- **frontend-developer**: Build React components, responsive layouts, client-side state management. Use PROACTIVELY for UI components and frontend issues (Tools: *)
- **expert-troubleshooter**: Debug bugs, test failures, error messages, stack traces, performance regressions. Use for failing tests, Flask errors, database issues, linting failures (Tools: *)
- **ui-ux-designer**: Create interface designs, wireframes, design systems, user research, prototyping, accessibility. Use PROACTIVELY for design systems and user flows (Tools: *)
- **security-auditor**: Review code for vulnerabilities, secure authentication, OWASP compliance, JWT, OAuth2, CORS, CSP. Use PROACTIVELY for security reviews (Tools: *)
- **architect-reviewer**: Review code changes for architectural consistency, SOLID principles, proper layering. Use PROACTIVELY after structural changes (Tools: *)
- **test-automator**: Create comprehensive test suites, CI pipelines, mocking strategies, test data. Use PROACTIVELY for test coverage improvement (Tools: *)
- **code-reviewer**: Expert code review for quality, security, maintainability. Use PROACTIVELY immediately after writing/modifying code (Tools: *)

# Pokemon SoulLink HG/SS Tracker - Claude Project Context

## Project Overview
This is a **3-player Pokemon SoulLink tracker** for randomized HeartGold/SoulSilver runs. The application automatically tracks encounters, catches, and faints through DeSmuME Lua scripting and provides real-time updates via a web interface.

## Architecture Stack
- **Backend**: FastAPI + Uvicorn (ASGI)
- **Database**: SQLite with WAL mode
- **Real-time**: WebSockets for live updates
- **Networking**: Cloudflare Quick Tunnel (no port forwarding needed)
- **Client**: DeSmuME + Lua scripts + Python watchers
- **Testing**: pytest + Playwright for UI testing
- **Development**: Test-Driven Development (TDD)

## Key Requirements & Rules

### SoulLink Rules
1. **Global First-Encounter with Dupes Clause**: First encounter per route only becomes final when the evolution family hasn't been encountered/caught globally by any player
2. **Fishing Support**: Old/Good/Super Rod detection with proper encounter method tracking  
3. **Soul Link Bonds**: Pokemon caught on same route by different players are linked - if one faints, all linked pokemon are marked dead
4. **One Family Per Run**: Each evolution family can only be caught once across all players

### Technical Goals
- ≥95% correct automatic encounter/catch/faint detection
- <1s end-to-end latency for UI updates  
- <15min setup time per player
- 2+ hour session stability without event loss

## Development Guidelines

### Test-Driven Development
- **ALWAYS write tests first** before implementing features
- Use pytest for backend testing
- Use Playwright for UI/integration testing
- Test coverage should be ≥90%

### Commands to Know
```bash
# TDD Workflow with Quality Gates (Recommended)
pytest                    # 1. Run failing test first
ruff check src/          # 2. Check code style before implementing
# 3. Implement feature
ruff format src/         # 4. Format code after implementation
mypy src/               # 5. Type check
pytest                  # 6. Verify test passes

# Individual Commands
pytest                   # Run tests
pytest --cov=src --cov-report=html  # Run tests with coverage
pytest tests/e2e/ --headed          # Run Playwright tests

# Quality Checks (run before every commit)
ruff check src/          # Lint checking
ruff format src/         # Code formatting
mypy src/               # Type checking

# Full quality check (run before PR/merge)
ruff check src/ && ruff format src/ && mypy src/ && pytest

# Development server
uvicorn src.soullink_tracker.main:app --reload --host 127.0.0.1 --port 8000

# Build portable executable
python build_simple.py

# Run portable version
python soullink_portable.py
python soullink_portable.py --debug

# Pre-commit Setup (Automated Quality Gates)
pip install pre-commit      # Install pre-commit
pre-commit install          # Setup git hooks
pre-commit run --all-files  # Run on all files manually
```

### Pre-commit Hooks (Automated Quality)
The project uses pre-commit hooks to automatically run quality checks before commits:
- **ruff check + format** - Code linting and formatting
- **mypy** - Type checking
- **pytest unit tests** - Fast unit tests only
- **File checks** - Trailing whitespace, file endings, YAML/JSON validation

Hooks run automatically on `git commit`. To bypass (not recommended): `git commit --no-verify`

### Documentation Sources
- Always use **Ref MCP server** before implementing to get latest docs
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- Playwright Python: https://playwright.dev/python/docs/intro
- SQLite WAL mode for concurrent access
- Use **repoprompt** for token optimization and structured prompts
- Use **repoprompt** for complex planning tasks where we need advanced reasoning

### File Structure
```
src/
└── soullink_tracker/
    ├── main.py          # FastAPI app entry point
    ├── config.py        # Auto-configuration management
    ├── launcher.py      # Portable mode launcher
    ├── api/            # FastAPI routes and endpoints
    ├── core/           # Core business logic and rules engine  
    ├── db/             # Database models and migrations
    ├── events/         # Event processing and WebSocket handling
    ├── auth/           # Authentication and token management
    └── utils/          # Shared utilities

tests/
├── unit/          # Unit tests
├── integration/   # Integration tests  
└── e2e/           # End-to-end Playwright tests

client/
└── lua/           # DeSmuME Lua scripts

web/               # Static web dashboard
data/              # CSV data files (routes, species)
```

## Event Types & Data Models

### Core Events
```json
// encounter event
{
  "type": "encounter",
  "run_id": "uuid", 
  "player_id": "uuid",
  "time": "2025-08-01T18:23:05Z",
  "route_id": 31,
  "species_id": 1,
  "family_id": 1, 
  "level": 7,
  "shiny": false,
  "encounter_method": "fish", // grass|surf|fish|static|unknown
  "rod_kind": "good"          // old|good|super (fish only)
}

// catch_result event  
{
  "type": "catch_result",
  "run_id": "uuid",
  "player_id": "uuid", 
  "time": "2025-08-01T18:24:40Z",
  "encounter_ref": {"route_id": 31, "species_id": 1},
  "status": "caught"  // caught|fled|ko|failed
}

// faint event
{
  "type": "faint",
  "run_id": "uuid",
  "player_id": "uuid",
  "time": "2025-08-01T18:59:12Z", 
  "pokemon_key": "personality_or_hash",
  "party_index": 2
}
```

### Database Schema
- `runs(id, name, rules_json, created_at)`
- `players(id, run_id, name, game, region, token_hash, created_at)` 
- `species(id, name, family_id)` 
- `routes(id, label, region)`
- `encounters(id, run_id, player_id, route_id, species_id, family_id, level, shiny, method, rod_kind, time, status, dupes_skip, fe_finalized)`
- `links(id, run_id, route_id)`; `link_members(link_id, player_id, encounter_id)`
- `blocklist(run_id, family_id, origin, created_at)`
- `party_status(run_id, player_id, pokemon_key, alive, last_update)` 
- `idempotency_keys(key, run_id, player_id, request_hash, response_json, created_at)`

## API Design

### Authentication
- Bearer token per player
- Admin endpoints for token generation/rotation
- Rate limiting: 10 req/s burst, 60 req/min sustained

### Key Endpoints
- `POST /v1/events` - Single event ingestion (with Idempotency-Key)
- `POST /v1/events:batch` - Batch event ingestion  
- `GET /v1/runs/{run_id}/routes/status` - Route matrix view
- `GET /v1/runs/{run_id}/encounters` - Query encounters
- `GET /v1/runs/{run_id}/blocklist` - Global family blocks
- `GET /v1/runs/{run_id}/links` - Soul link trios
- `GET /v1/ws?run_id=...` - WebSocket endpoint for real-time updates

### Error Handling
- Use RFC 9457 Problem Details format (`application/problem+json`)
- OpenAPI 3.1 specification
- Proper HTTP status codes (202, 429, 413, 401, 403)

## Configuration Management

The project uses auto-configuration via `src/soullink_tracker/config.py`:
- **Development Mode**: Auto-detected when running from source
- **Portable Mode**: Auto-detected when compiled as executable
- Environment variables: `SOULLINK_PORTABLE`, `SOULLINK_DEBUG`, `SOULLINK_*_DIR`
- Config file: `data/config.json` (auto-created)

## Testing Strategy

### pytest Configuration
- Test markers: `unit`, `integration`, `e2e`, `slow`, `api`, `db`, `ws`
- Coverage requirement: ≥90% (`--cov-fail-under=90`)
- Async test support via `pytest-asyncio`

### Test Structure
- `tests/conftest.py`: Shared fixtures including test database, test client
- `tests/unit/`: Fast unit tests for individual modules  
- `tests/integration/`: API integration tests
- `tests/e2e/`: Playwright browser tests

### Key Testing Patterns
```python
# API endpoint testing with auth
def test_api_endpoint(client, sample_data):
    token = create_access_token(player_id)
    response = client.post("/v1/events", 
        json=event_data,
        headers={"Authorization": f"Bearer {token}"})

# WebSocket testing
async def test_websocket(async_client):
    async with async_client.websocket_connect("/v1/ws") as websocket:
        await websocket.send_json(data)
```

## Deployment Notes

### Development Setup
```bash
# Start FastAPI server
uvicorn src.soullink_tracker.main:app --host 127.0.0.1 --port 8000

# Setup Cloudflare tunnel (generates random *.trycloudflare.com URL)
cloudflared tunnel --url http://127.0.0.1:8000
```

### Portable Build
- Entry point: `soullink_portable.py`
- Build script: `build_simple.py` (GitHub Actions compatible)
- Creates standalone executable with embedded web assets

### Idempotency & Reliability
- All POST endpoints require Idempotency-Key (UUIDv4)
- Server stores (key, request_hash, response) for replay protection
- Client implements retry with exponential backoff on 429 responses
- TTL cleanup of idempotency keys (24-72h)

## Development Workflow

1. **Always start with tests** - Write failing tests first
2. **Use Ref MCP server** to get latest documentation before coding
3. **Always use repoprompt** for context management and token optimization and file operations like read, write, update etc.
4. **Use Playwright** for UI debugging and testing
5. **Run linting/typecheck** before committing any code
6. **Test coverage** must be maintained at ≥90%

## Project Roadmap & Active Development

### Current Version: v2.x (Portable)
The project is actively being developed with major architectural improvements planned for v3:

### v3-alpha Milestone (Event-Driven Architecture)
**Key initiatives from `new_features_and_issues.md`:**

1. **Event Store Architecture** (Issue 1)
   - Append-only `events` table with projections (`route_progress`, `blocklist`)
   - Domain-driven design with typed contracts in `domain/events.py`
   - Feature flag: `FEATURE_V3_EVENTSTORE`
   - Admin rebuild endpoint for deterministic state reconstruction

2. **Hardened API Contracts** (Issue 2)
   - Idempotency-Key headers (UUID v4) with database persistence
   - Event ID + sequence number returns for encounter events
   - RFC 9457 Problem Details error format
   - Request size limits (16KB body, 100 events/64KB batches)

3. **WebSocket Real-time System** (Issue 3)
   - Per-run WebSocket rooms with sequence-based broadcasting
   - Catch-up via REST: `GET /v1/events?since_seq=...`
   - Heartbeat/ping and clean connection handling

4. **Secure Player Token System** (Issue 4)
   - SHA-256 + salt token hashing (no plaintext storage)
   - One-time token display during creation
   - Token rotation with invalidation of old connections
   - Admin endpoints: `POST /v1/runs/{run_id}/players`

5. **Production Watcher** (Issue 5)
   - Spool queue with retry policy (exponential backoff + jitter)
   - Persistent idempotency keys per record
   - CLI: `--base-url`, `--from-file fixtures.ndjson`, `--dev`
   - Windows spool directory: `C:\ProgramData\SoulLinkWatcher\spool\`

### Development & Testing Tools
- **Fixtures & Simulator** (Issue 6): NDJSON test data for encounter scenarios
- **Rule Engine** (Issue 7): Pure functions with property-based tests (Hypothesis)
- **Database Constraints** (Issue 8): Race condition prevention via unique constraints
- **Admin Dashboard** (Issue 9): Health/ready endpoints, rebuild functionality

### Key Architectural Patterns
- **Event Sourcing**: All state changes recorded as immutable events
- **CQRS**: Command/Query separation with projections for read models
- **Idempotency**: All operations safe to retry via persistent keys
- **Domain-Driven Design**: Core business logic isolated in `domain/` layer

## Important Notes
- EU region Pokemon HG/SS ROM required for Lua script calibration
- DeSmuME Lua scripting + RAM Watch/Search for encounter detection
- WebSocket connections require Bearer auth in headers
- CORS middleware only needed if UI served from different origin
- All timestamps in ISO 8601 UTC format
- Event processing is idempotent and supports retries
- use repoprompt to read and write files for better token usage.