# SoulLink Tracker - Playtest Guide

A comprehensive guide to setting up and running a 3-player Pokemon SoulLink playtest using the SoulLink Tracker system.

## Overview

The SoulLink Tracker monitors Pokemon HeartGold/SoulSilver games in real-time, tracking encounters, catches, faints, and automatically enforcing SoulLink rules across multiple players.

### System Architecture

```
DeSmuME ROM → Lua Script → JSON Files → Python Watcher → API Server → WebSocket → Web Dashboard
```

## Prerequisites

### System Requirements

- **Python 3.9+** 
- **DeSmuME** (0.9.11+ with Lua support)
- **Pokemon HeartGold/SoulSilver ROMs** (preferably randomized)
- **Modern web browser** (Chrome, Firefox, Safari, Edge)

### Hardware Requirements

- **3 computers** (one per player) OR **1 powerful computer** capable of running 3 DeSmuME instances
- **Stable internet connection** for API communication
- **At least 4GB RAM** recommended per DeSmuME instance

## Quick Start (5 Minutes)

### 1. Install Dependencies

```bash
# Clone or download the project
cd SoulLink_Tracker

# Install Python dependencies
pip install -r requirements.txt
pip install -r client/watcher/requirements.txt

# Or install core packages manually
pip install fastapi uvicorn sqlalchemy aiohttp watchdog aiofiles requests
```

### 2. Initialize System

```bash
# Run the automated playtest setup
python scripts/start_playtest.py
```

This script will:
- ✅ Initialize the database with sample data
- ✅ Create player configurations
- ✅ Start the API server
- ✅ Open the web dashboard
- ✅ Provide setup instructions for manual components

### 3. Configure DeSmuME (Per Player)

1. **Open DeSmuME** and load your Pokemon HeartGold/SoulSilver ROM
2. **Start a new game** and get to the overworld
3. **Open Lua Script Console**: Tools → Lua Script Console
4. **Load the tracking script**:
   - Click "Browse" 
   - Navigate to `client/lua/pokemon_tracker.lua`
   - The script will auto-detect your game version
5. **Verify tracking**: You should see console messages indicating the script is running

### 4. Start Event Watchers (Per Player)

Open separate terminal windows and run:

```bash
# Player 1
python client/watcher/event_watcher.py client/watcher/configs/player1_config.json

# Player 2  
python client/watcher/event_watcher.py client/watcher/configs/player2_config.json

# Player 3
python client/watcher/event_watcher.py client/watcher/configs/player3_config.json
```

### 5. Start Playing!

- 🎮 **Play Pokemon normally** in DeSmuME
- 👁️ **Encounters are automatically detected** and sent to the tracker
- 🌐 **Monitor progress** on the web dashboard
- 🔗 **Soul links form automatically** when players catch Pokemon on the same route

## Detailed Setup Guide

### Database Initialization

The database stores all run data, player information, and events.

```bash
# Initialize with sample data
python scripts/init_database.py

# This creates:
# - soullink_tracker.db (SQLite database)
# - test_config.json (player tokens and run ID)
# - Sample species and route data
```

### Player Configuration

Each player needs unique configuration files for both the Lua script and Python watcher.

```bash
# Generate all player configurations
python client/watcher/player_config.py

# This creates:
# - client/watcher/configs/player1_config.json
# - client/watcher/configs/player2_config.json  
# - client/watcher/configs/player3_config.json
# - client/lua/configs/player1_config.lua
# - client/lua/configs/player2_config.lua
# - client/lua/configs/player3_config.lua
```

### Manual Configuration

If you need to customize player settings:

#### Lua Configuration (`client/lua/configs/playerX_config.lua`)

```lua
local PLAYER_CONFIG = {
    player_name = "PlayerName",           -- Unique player identifier
    game_version = "HeartGold",           -- "HeartGold" or "SoulSilver"
    region = "EU",                        -- ROM region (US, EU, JP)
    output_dir = "C:/temp/events/",       -- Event output directory
    debug_mode = true,                    -- Enable debug logging
    poll_interval = 60,                   -- Frames between memory checks
}
```

#### Watcher Configuration (`client/watcher/configs/playerX_config.json`)

```json
{
    "player_name": "PlayerName",
    "api_base_url": "http://127.0.0.1:9000",
    "player_token": "jwt-token-from-database-init",
    "watch_directory": "/path/to/events",
    "debug": true
}
```

### API Server

The FastAPI server processes events and serves the web dashboard.

```bash
# Start server manually
uvicorn src.soullink_tracker.main:app --host 127.0.0.1 --port 9000 --reload

# Test server
curl http://127.0.0.1:9000/health

# API documentation
open http://127.0.0.1:9000/docs

# Web dashboard  
open http://127.0.0.1:9000/dashboard
```

### Web Dashboard

The dashboard provides real-time monitoring of your SoulLink run.

**Features:**
- 📊 **Run statistics** (encounters, catches, faints)
- 👥 **Player status** and party information  
- 📅 **Recent events** with timestamps
- 🔗 **Soul link visualization**
- 🔴 **Real-time updates** via WebSocket

**URL:** `http://127.0.0.1:9000/dashboard?run=<RUN_ID>`

## Game Rules and Mechanics

### SoulLink Rules

The tracker automatically enforces these rules:

1. **Dupes Clause**: Only the first encounter of each species family counts
2. **Species Clause**: Each player can only have one of each species family
3. **Soul Links**: Pokemon caught on the same route are soul-linked
4. **Family Blocking**: Catching a Pokemon blocks its evolution family for all players

### Supported Encounter Methods

- 🌱 **Grass encounters** (walking in tall grass)
- 🌊 **Water encounters** (surfing)
- 🎣 **Fishing encounters** (old rod, good rod, super rod)
- 🌳 **Headbutt encounters** (headbutt trees)
- 🪨 **Rock Smash encounters** (smashing rocks)

### Event Types

The system tracks these events:

- **Encounter**: Wild Pokemon appeared
- **Catch Result**: Pokemon was caught or fled
- **Faint**: Party Pokemon fainted
- **Soul Link**: New soul link formed
- **Admin Override**: Manual rule overrides

## Troubleshooting

### Common Issues

#### "Lua script not working"
- ✅ Ensure DeSmuME has Lua support enabled
- ✅ Check ROM version matches config (US/EU/JP)
- ✅ Verify output directory exists and is writable
- ✅ Look for error messages in DeSmuME console

#### "Python watcher not connecting"
- ✅ Check API server is running (`curl http://127.0.0.1:9000/health`)
- ✅ Verify player token in config file
- ✅ Ensure event directory exists
- ✅ Check firewall/network connectivity

#### "Web dashboard not loading"
- ✅ Verify API server is running
- ✅ Check run ID in URL matches database
- ✅ Try refreshing the page
- ✅ Check browser console for errors

#### "Events not appearing"
- ✅ Verify JSON files are being created in event directory
- ✅ Check watcher logs for processing errors  
- ✅ Ensure idempotency keys are unique
- ✅ Verify player authentication

### Health Check

Run comprehensive system diagnostics:

```bash
# Check all system components
python scripts/health_check.py

# Save detailed report
python scripts/health_check.py --save-report
```

### Quick Test

Test core functionality:

```bash
# Run functional tests
python scripts/quick_test.py

# This tests:
# - API connectivity
# - Authentication
# - Event processing
# - SoulLink rules
# - WebSocket functionality
```

### Debug Mode

Enable detailed logging:

1. **Lua Script**: Set `debug_mode = true` in config
2. **Python Watcher**: Set `"debug": true` in config  
3. **API Server**: Add `--log-level debug` to uvicorn command

### Log Files

Check these locations for logs:

- **API Server**: Console output
- **Python Watcher**: `logs/watcher_playerX.log`
- **DeSmuME**: Console window
- **Health Checks**: `logs/health_check_*.json`

## Advanced Configuration

### Custom ROM Memory Addresses

If your ROM version isn't auto-detected:

```lua
-- In client/lua/config_playerX.lua
local MEMORY_OVERRIDES = {
    party_pokemon = 0x02234804,     -- Custom address
    wild_pokemon = 0x0223AB00,      -- Custom address
    battle_state = 0x02226E18,      -- Custom address
}
```

### Network Configuration

For multi-computer setups:

1. **Configure API server host**:
   ```bash
   uvicorn src.soullink_tracker.main:app --host 0.0.0.0 --port 9000
   ```

2. **Update player configs**:
   ```json
   {
       "api_base_url": "http://MAIN_COMPUTER_IP:9000"
   }
   ```

3. **Port forwarding** (if needed):
   - Forward port 9000 for API
   - Consider using Cloudflare Tunnel for easy setup

### Performance Tuning

For better performance:

```json
{
    "poll_interval": 1,              // Faster event processing
    "max_events_per_minute": 60,     // Higher rate limit
    "connection_timeout": 15,        // Longer timeout
    "batch_processing": true         // Process events in batches
}
```

## Deployment Options

### Single Computer Setup

Run all components on one machine:
- 3 DeSmuME instances
- 3 Python watchers  
- 1 API server
- 1 web dashboard

### Multi-Computer Setup

Distribute across multiple machines:
- Each player runs DeSmuME + Watcher
- One machine runs API server
- Web dashboard accessible from anywhere

### Cloud Deployment

Deploy API server to cloud:
- Use Docker for containerization
- PostgreSQL for production database
- Redis for caching and WebSocket scaling
- Load balancer for high availability

## File Structure Reference

```
SoulLink_Tracker/
├── src/soullink_tracker/           # Main application code
│   ├── api/                        # API endpoints
│   ├── auth/                       # Authentication
│   ├── core/                       # Business logic
│   ├── db/                         # Database models
│   └── events/                     # WebSocket handling
├── client/                         # Client-side components
│   ├── lua/                        # DeSmuME Lua scripts
│   └── watcher/                    # Python event watchers
├── web/                           # Web dashboard
│   ├── css/                       # Stylesheets
│   └── js/                        # JavaScript
├── scripts/                       # Utility scripts
├── data/                          # Reference data (species, routes)
├── tests/                         # Test suite
└── docs/                          # Documentation
```

## Getting Help

### Community Resources

- **GitHub Issues**: Report bugs and feature requests
- **Discord**: Real-time community support
- **Documentation**: Comprehensive guides and API docs

### Debug Information

When reporting issues, include:

1. **System info**: OS, Python version, DeSmuME version
2. **Configuration files**: Player configs (remove tokens)
3. **Log files**: Recent error messages
4. **Health check report**: `python scripts/health_check.py --save-report`

### Contributing

Contributions welcome! See `CONTRIBUTING.md` for guidelines.

---

## Ready to Play!

Once everything is set up:

1. 🎮 **Start your Pokemon games** in DeSmuME
2. 👀 **Watch the dashboard** for real-time updates  
3. 🔗 **Coordinate with teammates** on soul links
4. 📊 **Monitor your progress** throughout the run
5. 🏆 **Complete your SoulLink challenge!**

**Good luck, trainers! May your Pokemon be strong and your soul links unbroken! 🔗✨**