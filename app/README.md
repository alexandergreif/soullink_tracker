# Soullink Tracker Application

Automated Pokemon encounter tracking system for Soullink runs using DeSmuME emulator (Pokemon Soul Silver/Heart Gold).

## Overview

This application monitors real-time Pokemon encounters from DeSmuME emulator and enforces Soullink rules across multiple players. The core rule: once a Pokemon species is caught by any player, no other player can catch that species.

### Architecture

```
DeSmuME (Lua) → JSON Files → Python Watcher → SQLite → FastAPI/WebSocket → Web Dashboard
```

### Technology Stack

- **Backend**: FastAPI, Python watchdog, SQLite3, Pydantic
- **Frontend**: HTML5 + Vanilla JavaScript, Tailwind CSS (CDN), WebSocket client
- **Emulator Integration**: DeSmuME Lua API for memory reading
- **Target**: Windows-only, Pokemon HGSS (USA version), 3 concurrent players

## Directory Structure

```
app/
├── src/                  # Application source code
│   ├── models/          # Pydantic models for data validation
│   │   ├── encounter.py         # Encounter entity model
│   │   ├── soullink_rule.py     # Soullink rule model
│   │   └── species_reference.py # Pokemon species reference
│   └── services/        # Business logic services
│
├── tests/               # Test suite
│   ├── unit/           # Unit tests for models
│   ├── integration/    # Integration tests for pipeline
│   └── contract/       # Contract tests for JSON schemas
│
├── data/               # Runtime data
│   └── encounters/     # JSON files from DeSmuME Lua scripts
│
├── emulator/           # DeSmuME integration
│   ├── hgss_encounter_tracker.lua  # Lua script for memory reading
│   └── config_template.lua         # Configuration template
│
└── requirements.txt    # Python dependencies
```

## Setup

### Prerequisites

- Python 3.10+
- DeSmuME emulator (Windows)
- Pokemon Soul Silver or Heart Gold ROM (USA version)

### Installation

1. **Create and activate virtual environment:**

```bash
cd app
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure DeSmuME Lua script:**

Copy `emulator/config_template.lua` and configure player name and output path.

## Running the Application

### 1. Start DeSmuME Emulator

1. Launch DeSmuME
2. Load Pokemon Soul Silver or Heart Gold ROM
3. Load Lua script: Tools → Lua Scripting → `emulator/hgss_encounter_tracker.lua`

### 2. Start Python Services

```bash
# Activate virtual environment first
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Start file watcher service
python src/services/watcher.py

# Start FastAPI server (in another terminal)
uvicorn src.main:app --reload
```

### 3. Access Dashboard

Open browser: `http://localhost:8000`

## Testing

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test Suites

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Contract tests only
pytest tests/contract/

# Run specific test file
pytest tests/unit/test_encounter_model.py -v
```

## Critical Memory Addresses (HGSS USA)

```
Pokemon Data Range: 0x002C0BC2 - 0x002D5780
Pokemon Structure: 128 bytes (0x80 hex) per Pokemon
Species ID: Offset 0x00-0x01
Level: Offset 0x34
Current HP: Offset 0x4C-0x4D
Personality ID: Offset 0x68-0x6B
Game Language: 0x02FFFE0F
Seed Offset: 0xAC0
```

## Database Schema

### Encounters Table

- `timestamp`, `player_name`
- `species_id`, `species_name`, `level`, `location`
- `status` (encountered/caught/ko/run)
- `is_duplicate` flag

### Soullink Rules Table

- `species_id` (unique)
- `caught_by_player`
- `caught_at` timestamp

## Performance Requirements

- **End-to-end latency**: < 3 seconds for encounter updates
- **Database queries**: < 100ms response time
- **Memory polling**: Every 1 second
- **Offline buffer**: JSON files persist during connection loss

## Development Principles

- **KISS Principle**: Keep everything simple
- **MVP First**: Encounter detection before advanced features
- **Iterative Development**: Expand features gradually
- **Manual Fallbacks**: User can override automation
- **TDD Workflow**: Tests written → approved → fail → implement

## Configuration

Environment variables and configuration files:

- `emulator/config_template.lua` - Lua script configuration
- Database location: `data/soullink.db` (auto-created)
- Encounter JSON output: `data/encounters/`

## Troubleshooting

### Lua Script Not Working

- Ensure DeSmuME Lua Scripting is enabled
- Verify ROM is USA version of HGSS
- Check memory addresses match your ROM version

### Connection Issues

- Verify file watcher service is running
- Check JSON files are being created in `data/encounters/`
- Ensure FastAPI server is accessible on port 8000

### Database Errors

- Delete `data/soullink.db` to reset database
- Check SQLite3 is available (bundled with Python)

## License

[Specify license here]

## Contributors

[Specify contributors here]
