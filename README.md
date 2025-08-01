# Pokemon SoulLink HG/SS Tracker

A real-time tracker for 3-player Pokemon SoulLink runs in randomized HeartGold/SoulSilver.

## Features

- **Automatic Detection**: DeSmuME Lua scripts detect encounters, catches, and faints
- **Real-time Updates**: WebSocket-based live updates across all players  
- **SoulLink Rules**: Enforces global first-encounter and dupes clause
- **Fishing Support**: Detects Old/Good/Super Rod encounters
- **Soul Bonds**: Links Pokemon caught on same route, propagates faints
- **Web Interface**: Route matrix, live feed, blocklist management

## Quick Start

### Prerequisites
- Python 3.10+
- DeSmuME emulator (Windows)
- Pokemon HG/SS ROM (EU region)
- Cloudflare tunnel (cloudflared.exe)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd SoulLink_Tracker

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install

# Run tests
pytest

# Start development server
uvicorn src.soullink_tracker.main:app --reload --host 127.0.0.1 --port 9000
```

### Development Commands

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest tests/unit/ -m unit

# Run E2E tests (requires server running)
pytest tests/e2e/ -m e2e --headed

# Linting and formatting
ruff check src/
ruff format src/

# Type checking
mypy src/
```

## Architecture

- **Backend**: FastAPI + Uvicorn (ASGI)
- **Database**: SQLite with WAL mode
- **Real-time**: WebSockets for live updates
- **Client**: DeSmuME + Lua scripts + Python watchers
- **Testing**: pytest + Playwright for UI testing

## Project Structure

```
src/soullink_tracker/
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

## API Usage

### Authentication
All requests require a Bearer token per player:
```
Authorization: Bearer <player_token>
```

### Key Endpoints
- `POST /v1/events` - Submit encounter/catch/faint events
- `GET /v1/runs/{run_id}/routes/status` - Route matrix
- `GET /v1/ws?run_id=...` - WebSocket for real-time updates

### Event Format
```json
{
  "type": "encounter",
  "run_id": "uuid",
  "player_id": "uuid", 
  "time": "2025-08-01T18:23:05Z",
  "route_id": 31,
  "species_id": 1,
  "level": 7,
  "encounter_method": "fish",
  "rod_kind": "good"
}
```

## Development

This project follows **Test-Driven Development (TDD)**:

1. Write failing tests first
2. Implement minimal code to pass tests
3. Refactor while keeping tests green
4. Maintain ≥90% test coverage

### Testing Strategy
- **Unit tests**: Core business logic, rules engine
- **Integration tests**: Database operations, API endpoints  
- **E2E tests**: Full user workflows with Playwright

## Deployment

### Local Development
```bash
# Start server
uvicorn src.soullink_tracker.main:app --reload --host 127.0.0.1 --port 9000

# Start Cloudflare tunnel (in separate terminal)
cloudflared tunnel --url http://127.0.0.1:9000
```

### Production Notes
- Enable SQLite WAL mode: `PRAGMA journal_mode=WAL;`
- Use Cloudflare Quick Tunnel for external access
- Configure rate limiting and authentication properly
- Set up proper logging and monitoring

## Contributing

1. Create feature branch
2. Write tests first (TDD approach)
3. Implement functionality
4. Ensure all tests pass and coverage ≥90%
5. Run linting: `ruff check src/`
6. Submit pull request

## License

MIT License - see LICENSE file for details.