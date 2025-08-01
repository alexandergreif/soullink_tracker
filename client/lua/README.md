# DeSmuME Lua Scripts for SoulLink Tracker

This directory contains Lua scripts for integrating Pokemon HeartGold/SoulSilver with the SoulLink Tracker backend via DeSmuME.

## Files

- **`pokemon_tracker.lua`** - Main monitoring script that detects encounters, catches, and faints
- **`memory_addresses.lua`** - Memory address definitions for different game versions
- **`config_template.lua`** - Configuration template (copy and customize per player)

## Setup Instructions

### 1. Install DeSmuME

Download and install DeSmuME with Lua support:
- Windows: [DeSmuME 0.9.11+](http://desmume.org/download/)
- Ensure Lua support is enabled (most recent builds include it)

### 2. Configure the Scripts

1. Copy `config_template.lua` to `config_player1.lua`, `config_player2.lua`, `config_player3.lua`
2. Edit each config file with player-specific settings:

```lua
-- Example config_player1.lua
local PLAYER_CONFIG = {
    player_name = "AlexPlayer",           -- Your player name
    game_version = "HeartGold",           -- HeartGold or SoulSilver
    region = "EU",                        -- US, EU, or JP
    api_base_url = "http://127.0.0.1:9000", -- Your API server
    player_token = "jwt-token-from-init",  -- From database init script
    output_dir = "C:/temp/soullink_events/", -- Event output directory
    debug_mode = true
}
```

### 3. Initialize Database

Run the database initialization script to get player tokens:

```bash
python scripts/init_database.py
```

This creates `test_config.json` with player tokens. Copy the token for your player into your config file.

### 4. Start the API Server

```bash
uvicorn src.soullink_tracker.main:app --host 127.0.0.1 --port 9000
```

### 5. Load Script in DeSmuME

1. Open Pokemon HeartGold/SoulSilver ROM in DeSmuME
2. Go to **Tools** → **Lua Script Console**
3. Click **Browse** and select `pokemon_tracker.lua`
4. The script will auto-detect your game version and start monitoring

## How It Works

### Event Detection

The script monitors memory addresses to detect:

1. **Encounters** - When wild Pokemon appear in battle
2. **Catch Results** - Whether Pokemon were caught or fled
3. **Faints** - When party Pokemon HP reaches 0

### Data Flow

```
DeSmuME ROM → Lua Script → JSON Files → Python Watcher → API Server
```

1. Lua script reads ROM memory every second
2. Events are written as JSON files to output directory
3. Python watcher script monitors directory and sends events to API
4. API processes events according to SoulLink rules
5. WebSocket updates notify all connected clients

### Memory Monitoring

The script tracks:
- **Party Pokemon**: Species, level, HP, status, personality values
- **Wild Encounters**: Species, level, shiny status, encounter method
- **Battle State**: In battle, battle type, battle result
- **Location Data**: Current route, map, coordinates
- **Game State**: Menu/overworld status, time

### Supported Games

- Pokemon HeartGold (IPKE - US, IPKP - EU, IPKJ - JP)
- Pokemon SoulSilver (IPGE - US, IPGP - EU, IPGJ - JP)

Memory addresses are automatically selected based on detected ROM version.

## Configuration Options

### Basic Settings

```lua
player_name = "Player1"        -- Unique player identifier
game_version = "HeartGold"     -- Game being played
region = "EU"                  -- ROM region
api_base_url = "http://..."    -- API server URL
player_token = "jwt-token"     -- Authentication token
```

### Performance Settings

```lua
poll_interval = 60           -- Check memory every N frames (60 = 1 second)
debug_mode = true           -- Enable detailed logging
log_encounters = true       -- Log all encounters
```

### Event Detection

```lua
detect_fishing = true       -- Monitor fishing encounters
detect_surfing = true       -- Monitor surfing encounters
enable_shiny_detection = true  -- Flag shiny Pokemon
skip_duplicate_encounters = false  -- Filter duplicate events
```

### Advanced Settings

```lua
connection_timeout = 5000   -- API timeout (ms)
retry_attempts = 3          -- API retry count
max_events_per_minute = 30  -- Rate limiting
```

## Troubleshooting

### Script Not Loading
- Ensure DeSmuME has Lua support enabled
- Check that all `.lua` files are in the same directory
- Verify ROM is fully loaded before running script

### Memory Address Issues
- Different ROM versions use different addresses
- Script auto-detects most versions
- For unsupported ROMs, manually configure addresses in config file

### Event Detection Problems
- Enable `debug_mode = true` for detailed logging
- Check DeSmuME console output for error messages
- Verify output directory exists and is writable

### API Connection Issues
- Ensure API server is running on correct port
- Check player token is valid (from database init)
- Verify firewall/network connectivity

## Output Files

Events are written as JSON files in the output directory:

```
event_1641234567_1234.json
```

Example encounter event:
```json
{
    "type": "encounter",
    "timestamp": "2024-01-01T12:00:00Z",
    "player_name": "Player1",
    "game_version": "HeartGold",
    "region": "EU",
    "route_id": 31,
    "species_id": 1,
    "level": 5,
    "shiny": false,
    "method": "grass"
}
```

## Performance Notes

- Script polls memory every 60 frames (1 second) by default
- Minimal performance impact on DeSmuME
- JSON file writing is asynchronous
- Memory usage is low (~1MB)

## Compatibility

- **DeSmuME**: 0.9.11+ with Lua support
- **Operating Systems**: Windows, macOS, Linux
- **ROM Languages**: English, Japanese (addresses may vary)
- **ROM Regions**: US, EU, JP versions supported

## Next Steps

After setting up the Lua scripts, you'll need:

1. **Python Watcher Script** - To monitor JSON files and send to API
2. **Web UI** - To view real-time run progress
3. **Deployment Setup** - For running on multiple machines

See the main project documentation for complete setup instructions.