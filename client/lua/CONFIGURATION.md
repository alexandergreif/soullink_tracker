# Lua Script Configuration Guide

## Quick Start

The Lua script needs proper configuration to connect to your SoulLink Tracker server. Without it, you'll see errors like:
- `Failed to load config from client/lua/config.lua`
- `MISSING_RUN_ID` / `MISSING_PLAYER_ID`
- `422 Unprocessable Entity` errors

## Configuration Methods

### Method 1: Automatic Configuration (Recommended)

Run the configuration generator script:

```bash
python scripts/generate_lua_config.py
```

This will:
1. Connect to your running SoulLink Tracker server
2. List existing runs or create a new one
3. List existing players or create a new one
4. Generate `config.lua` with correct UUIDs
5. Save your player token for the watcher

### Method 2: Manual Configuration

1. **Start the server:**
   ```bash
   python -m uvicorn src.soullink_tracker.main:app
   ```

2. **Open the admin panel:**
   http://127.0.0.1:8000/admin

3. **Create a run and player:**
   - Click "Create Run"
   - Enter a name and create
   - Note the Run ID (UUID)
   - Create a player for that run
   - Note the Player ID (UUID)
   - **SAVE THE PLAYER TOKEN** (shown only once!)

4. **Create config.lua:**
   ```bash
   cp client/lua/config_template.lua client/lua/config.lua
   ```

5. **Edit config.lua with your UUIDs:**
   ```lua
   run_id = "your-actual-run-uuid-here",
   player_id = "your-actual-player-uuid-here",
   ```

## Configuration File Structure

```lua
local config = {
    -- Server connection
    api_base_url = "http://127.0.0.1:8000",
    
    -- Your unique identifiers (GET THESE FROM ADMIN PANEL)
    run_id = "550e8400-e29b-41d4-a716-446655440000",
    player_id = "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    
    -- Where to save event JSON files
    output_dir = "C:/temp/soullink_events/",  -- Windows
    -- output_dir = "/tmp/soullink_events/",  -- Linux/Mac
    
    -- Script settings
    poll_interval = 60,    -- Check every 60 frames (1 second)
    debug = true,          -- Show debug messages
    max_runtime = 3600,    -- Stop after 1 hour
    memory_profile = "US"  -- Use "EU" for European ROMs
}
```

## Troubleshooting

### "Failed to load config.lua"
- Make sure `config.lua` exists (not just `config_template.lua`)
- Check file is in `client/lua/` directory
- Verify Lua syntax is correct (no typos)

### "MISSING_RUN_ID" or "MISSING_PLAYER_ID"
- You're using the template placeholders
- Replace with actual UUIDs from the admin panel
- UUIDs must be in format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

### "422 Unprocessable Entity"
- Your UUIDs are not valid format
- The run/player doesn't exist in the database
- Check UUIDs match exactly what's shown in admin panel

### "Invalid UUID format"
Valid UUID example: `550e8400-e29b-41d4-a716-446655440000`
- 8 chars - 4 chars - 4 chars - 4 chars - 12 chars
- Only hexadecimal characters (0-9, a-f)
- Separated by hyphens

## Complete Setup Checklist

- [ ] SoulLink Tracker server is running
- [ ] Created a run in the admin panel
- [ ] Created a player for that run
- [ ] Saved the player token (shown only once!)
- [ ] Generated or created `config.lua` file
- [ ] Replaced placeholder UUIDs with actual values
- [ ] Output directory exists and is writable
- [ ] Lua script loads without errors in DeSmuME

## Need Help?

1. Check server is running: http://127.0.0.1:8000/health
2. View admin panel: http://127.0.0.1:8000/admin
3. Run config generator: `python scripts/generate_lua_config.py`
4. Check logs in DeSmuME Lua console for specific errors