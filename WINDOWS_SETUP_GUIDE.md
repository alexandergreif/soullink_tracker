# SoulLink Tracker - Windows Setup Guide

## Quick Start (5 Minutes)

### Step 1: Start the Server
1. Double-click `start_server.bat`
2. The server will start at http://127.0.0.1:8000
3. Keep this window open

### Step 2: Create a Run (Admin)
1. Open http://127.0.0.1:8000/admin in your browser
2. Click "Create New Run"
3. Fill in:
   - Run Name: `TestRun` (or any name)
   - Password: `test123` (or any password)
4. Click "Create Run"
5. Add players:
   - Click "Add Player" 
   - Enter player name: `Player1`
   - Copy the generated Player ID and Run ID

### Step 3: Join as Player
1. Open http://127.0.0.1:8000/player in a new tab
2. Enter:
   - Run Name: `TestRun` (what you created above)
   - Player Name: `Player1` 
   - Password: `test123`
3. Click "Join Run"
4. You'll see "Connected!" with your IDs

### Step 4: Configure Lua Script
After logging in as a player, you need to configure the Lua script:

1. **Copy the template config:**
   ```
   cd client\lua
   copy config_template.lua config.lua
   ```

2. **Edit `client\lua\config.lua`** with Notepad and add your IDs:
   ```lua
   local config = {
       api_base_url = "http://127.0.0.1:8000",
       run_id = "YOUR_RUN_ID_HERE",      -- From admin panel or player login
       player_id = "YOUR_PLAYER_ID_HERE", -- From admin panel or player login
       output_dir = "C:/temp/soullink_events/",
       poll_interval = 60,
       debug = true,
       memory_profile = "US"
   }
   ```

### Step 5: Start the Watcher
1. Double-click `start_watcher.bat`
2. This monitors events from the Lua script
3. Keep this window open

### Step 6: Load Lua Script in DeSmuME
1. Open DeSmuME emulator
2. Load your Pokemon HeartGold/SoulSilver ROM
3. Go to: Tools → Lua Scripting → New Lua Script Window
4. Click "Browse" and select: `client\lua\pokemon_tracker_v3_fixed.lua`
5. The script will show:
   ```
   [SoulLink V3] === Pokemon SoulLink Tracker V3 (Fixed) ===
   [SoulLink V3] Initialization complete, monitoring for events...
   ```

### Step 7: View Dashboard
1. Open http://127.0.0.1:8000/dashboard
2. You'll see live updates as you play!

---

## What Each Component Does

### Server (`start_server.bat`)
- Runs the FastAPI backend
- Handles all API requests
- Manages the database
- Serves the web interface

### Watcher (`start_watcher.bat`)
- Monitors `C:\temp\soullink_events\` folder
- Reads JSON files created by the Lua script
- Sends events to the server API
- Handles retries and errors

### Lua Script (`pokemon_tracker_v3_fixed.lua`)
- Runs inside DeSmuME
- Monitors game memory for encounters/catches/faints
- Writes events to JSON files
- **REQUIRES** proper `config.lua` with your IDs

### Web Interface
- `/admin` - Create runs and manage players
- `/player` - Player login page
- `/dashboard` - Live tracking dashboard

---

## Common Issues & Solutions

### "Failed to load config from client/lua/config.lua"
**Solution:** You need to create the config file:
1. Copy `config_template.lua` to `config.lua`
2. Edit it with your run_id and player_id from the admin panel

### "Events will fail with 422 errors"
**Cause:** The Lua script doesn't have valid IDs
**Solution:** Update `config.lua` with your actual run_id and player_id

### "Cannot connect to server"
**Solution:** Make sure `start_server.bat` is running first

### "Das System kann den angegebenen Pfad nicht finden"
**Translation:** "The system cannot find the specified path"
**Solution:** This is a DeSmuME warning, you can ignore it

### Lua script stops when loading ROM
**Solution:** This is normal. Restart the Lua script after the game loads.

---

## File Locations

- **Server Database:** `soullink_tracker.db` (created automatically)
- **Lua Config:** `client\lua\config.lua` (you create this)
- **Event Files:** `C:\temp\soullink_events\` (created automatically)
- **Logs:** Check console windows for real-time logs

---

## Testing Your Setup

1. **Test encounter detection:**
   - Walk in grass until you encounter a Pokemon
   - Check the dashboard - it should show immediately

2. **Test catch detection:**
   - Catch a Pokemon
   - Dashboard should update the status

3. **Test WebSocket connection:**
   - The dashboard shows a green dot when connected
   - Events appear instantly without refreshing

---

## Advanced Configuration

### Using Cloudflare Tunnel (for remote play)
```bash
# Install cloudflared first
cloudflared tunnel --url http://127.0.0.1:8000
```
This gives you a public URL like `https://xxx.trycloudflare.com`

### Custom Event Directory
Edit `client\lua\config.lua`:
```lua
output_dir = "D:/MyCustomPath/events/",
```

### Debug Mode
The Lua script shows detailed logs when `debug = true` in config.

---

## Need Help?

1. Check console windows for error messages
2. Verify all IDs match between admin panel and config.lua
3. Make sure all three components are running:
   - Server (start_server.bat)
   - Watcher (start_watcher.bat)
   - Lua script (in DeSmuME)