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
# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run Playwright tests
pytest tests/e2e/ --headed

# Start development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 9000

# Run linting
ruff check src/
ruff format src/

# Type checking  
mypy src/
```

### Documentation Sources
- Always use **Ref MCP server** before implementing to get latest docs
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- Playwright Python: https://playwright.dev/python/docs/intro
- SQLite WAL mode for concurrent access
- Use **repoprompt** for token optimization and structured prompts

### File Structure
```
src/
├── api/           # FastAPI routes and endpoints
├── core/          # Core business logic and rules engine  
├── db/            # Database models and migrations
├── events/        # Event processing and WebSocket handling
├── auth/          # Authentication and token management
└── utils/         # Shared utilities

tests/
├── unit/          # Unit tests
├── integration/   # Integration tests  
└── e2e/           # End-to-end Playwright tests

client/
├── lua/           # DeSmuME Lua scripts
└── watcher/       # Python event watchers
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

## Deployment Notes

### Development Setup
```bash
# Install Cloudflare tunnel
# Download cloudflared.exe for Windows

# Start tunnel (generates random *.trycloudflare.com URL)
cloudflared tunnel --url http://127.0.0.1:9000

# Start FastAPI server
uvicorn app.main:app --host 127.0.0.1 --port 9000

# SQLite WAL mode setup
# Add to database init: PRAGMA journal_mode=WAL;
```

### Idempotency & Reliability
- All POST endpoints require Idempotency-Key (UUIDv4)
- Server stores (key, request_hash, response) for replay protection
- Client implements retry with exponential backoff on 429 responses
- TTL cleanup of idempotency keys (24-72h)

## Development Workflow

1. **Always start with tests** - Write failing tests first
2. **Use Ref MCP server** to get latest documentation before coding
3. **Use repoprompt** for context management and token optimization  
4. **Use Playwright** for UI debugging and testing
5. **Run linting/typecheck** before committing any code
6. **Test coverage** must be maintained at ≥90%

## Important Notes
- EU region Pokemon HG/SS ROM required for Lua script calibration
- DeSmuME Lua scripting + RAM Watch/Search for encounter detection
- WebSocket connections require Bearer auth in headers
- CORS middleware only needed if UI served from different origin
- All timestamps in ISO 8601 UTC format
- Event processing is idempotent and supports retries