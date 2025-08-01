# SoulLink Tracker - Player Setup Guide

**For players joining a Pokemon SoulLink run**

This guide is for **players** who want to connect their Pokemon game to an existing SoulLink Tracker session. The admin/host should have already set up the central server using the [ADMIN_SETUP.md](ADMIN_SETUP.md) guide.

## What You Need from the Admin

Before starting, get these details from your admin:

- 🏷️ **Your player name** (e.g., "Player1", "Alex", etc.)
- 🔑 **Your authentication token** (long string starting with "eyJ...")
- 🌐 **Server address** (e.g., `http://192.168.1.100:9000` or `https://abc123.trycloudflare.com`)
- 🆔 **Run ID** (UUID for the web dashboard)
- 🎮 **Your assigned game** (HeartGold or SoulSilver)

## Prerequisites

### What You Need

- 🎮 **DeSmuME emulator** (version 0.9.11+ with Lua support)
- 📀 **Pokemon HeartGold or SoulSilver ROM** (preferably randomized)
- 🐍 **Python 3.9+** installed on your computer
- 🌐 **Internet connection** to reach the admin's server
- 💾 **~100MB free disk space** for files and events

### Downloads

1. **DeSmuME**: Download from [desmume.org](http://desmume.org/download/)
   - ✅ Make sure it includes Lua support
   - ✅ Windows: Get the x64 version
   - ✅ Mac: Download the Universal Binary

2. **Python**: Download from [python.org](https://python.org/downloads/)
   - ✅ Version 3.9 or higher
   - ✅ Make sure to check "Add Python to PATH" during installation

## Quick Setup (5 Minutes)

### 1. Download Player Files

Get these files from your admin:

```
📁 Your player folder should contain:
├── pokemon_tracker.lua          # Main Lua script for DeSmuME
├── your_config.lua             # Your personal Lua configuration  
├── event_watcher.py            # Python script to send events
├── your_config.json            # Your personal watcher configuration
└── requirements.txt            # Python dependencies
```

**OR** download the full project and use the config files the admin created for you.

### 2. Install Python Dependencies

```bash
# Open terminal/command prompt in your player folder
pip install aiohttp watchdog aiofiles requests

# Or if you have the full project:
pip install -r requirements.txt
```

### 3. Configure Your Setup

#### Edit Your Lua Config (`your_config.lua`)

```lua
local PLAYER_CONFIG = {
    player_name = "YourPlayerName",     -- From admin
    game_version = "HeartGold",         -- HeartGold or SoulSilver  
    region = "EU",                      -- ROM region (US/EU/JP)
    api_base_url = "http://ADMIN_IP:9000", -- From admin
    player_token = "your-jwt-token",    -- From admin
    output_dir = "C:/temp/soullink/",   -- Where to save events (Windows)
    -- output_dir = "/tmp/soullink/",   -- Mac/Linux version
    debug_mode = true,                  -- Enable for troubleshooting
}
```

#### Edit Your Watcher Config (`your_config.json`)

```json
{
    "player_name": "YourPlayerName",
    "player_id": "your-player-uuid-from-admin",
    "player_token": "your-jwt-token-from-admin", 
    "run_id": "run-uuid-from-admin",
    "api_base_url": "http://ADMIN_IP:9000",
    "watch_directory": "C:/temp/soullink/",
    "debug": true
}
```

### 4. Test Connection

```bash
# Test if you can reach the admin's server
curl http://ADMIN_IP:9000/health

# Should return something like:
# {"status":"healthy","service":"soullink-tracker","version":"1.0.0"}
```

### 5. Start Playing!

Now you're ready to connect your Pokemon game:

## DeSmuME Setup

### 1. Load Your ROM

1. **Open DeSmuME**
2. **File → Open ROM** and select your Pokemon HeartGold/SoulSilver ROM
3. **Start a new game** and play until you reach the overworld
4. **Save your game** (in case something goes wrong)

### 2. Load the Lua Script

1. **Open Lua Script Console**: Tools → Lua Script Console
2. **Click "Browse"** in the Lua console
3. **Navigate to your player folder** and select `pokemon_tracker.lua`
4. **The script should load** and start showing messages like:
   ```
   [SoulLink] Pokemon SoulLink Tracker started
   [SoulLink] Player: YourPlayerName (HeartGold)
   [SoulLink] Output directory: C:/temp/soullink/
   ```

### 3. Start the Event Watcher

Open a new terminal/command prompt and run:

```bash
# Navigate to your player folder
cd /path/to/your/player/folder

# Start the event watcher
python event_watcher.py your_config.json
```

You should see:
```
Starting SoulLink Event Watcher for player: YourPlayerName
Monitoring directory: C:/temp/soullink/
API server: http://ADMIN_IP:9000
API connection successful: soullink-tracker v1.0.0
Event watcher started successfully
```

### 4. Verify Everything Works

1. **Walk in tall grass** in your Pokemon game
2. **Encounter a wild Pokemon**
3. **Check the terminal** - you should see:
   ```
   [SoulLink] Encounter detected: Species 19 Level 3
   Event sent successfully: encounter
   ```
4. **Check the web dashboard** - your encounter should appear in real-time!

## Web Dashboard

### Accessing the Dashboard

Open your web browser and go to:
```
http://ADMIN_IP:9000/dashboard?run=RUN_ID_FROM_ADMIN
```

### What You'll See

- 📊 **Run Statistics**: Total encounters, catches, faints for all players
- 👥 **All Player Status**: See what everyone is doing in real-time  
- 📅 **Recent Events**: Live feed of encounters, catches, faints
- 🔗 **Soul Links**: Visual representation of linked Pokemon
- ⚡ **Connection Status**: Shows if you're connected to the server

### Real-Time Updates

The dashboard updates **instantly** when:
- ✨ You encounter a wild Pokemon
- ⚾ You catch or fail to catch a Pokemon  
- 💀 One of your Pokemon faints
- 🔗 A soul link is formed (when you and teammates catch on same route)
- 🚫 A Pokemon family gets blocked by the dupes clause

## Gameplay and Rules

### How SoulLink Tracking Works

The system **automatically** tracks:

1. **Wild Encounters**: Detected when you enter a battle with a wild Pokemon
2. **Catch Results**: Detected when the battle ends (caught vs. fled)
3. **Pokemon Faints**: Detected when your party Pokemon's HP reaches 0
4. **Soul Links**: Created automatically when players catch Pokemon on the same route

### SoulLink Rules (Enforced Automatically)

- 🔄 **Dupes Clause**: Only first encounter of each species family counts
- 👥 **Species Clause**: Each player can only have one of each species family  
- 🔗 **Soul Links**: Pokemon caught on same route are soul-linked
- 🚫 **Family Blocking**: Catching a Pokemon blocks its evolution family for everyone

### What the Script Detects

- 🌱 **Grass encounters** (walking in tall grass)
- 🌊 **Water encounters** (surfing)
- 🎣 **Fishing encounters** (any fishing rod)
- 🌳 **Headbutt encounters** (headbutting trees)
- 🪨 **Rock Smash encounters** (breaking rocks)
- ✨ **Shiny Pokemon** (automatically flagged)
- 📊 **Pokemon level, location, encounter method**

## Troubleshooting

### Common Issues

#### "Lua script not working"

**Symptoms**: No messages in DeSmuME console, no event files created

**Solutions**:
- ✅ Make sure DeSmuME has Lua support (try Tools → Lua Script Console)
- ✅ Check your ROM region matches config (US/EU/JP)
- ✅ Verify output directory exists and is writable
- ✅ Try restarting DeSmuME and reloading the script

#### "Event watcher can't connect to server"

**Symptoms**: 
```
API connection test failed: Connection refused
```

**Solutions**:
- ✅ Check the server address is correct
- ✅ Make sure admin's server is running
- ✅ Test connection: `curl http://ADMIN_IP:9000/health`
- ✅ Check your firewall isn't blocking the connection

#### "Authentication failed"

**Symptoms**:
```
Authentication failed - check player token
```

**Solutions**:
- ✅ Double-check your authentication token from admin
- ✅ Make sure there are no extra spaces in the token
- ✅ Verify your player name matches what admin set up
- ✅ Ask admin to regenerate your token

#### "Events not appearing on dashboard"

**Symptoms**: Encounters happen in-game but don't show up on dashboard

**Solutions**:
- ✅ Check if JSON files are being created in your output directory
- ✅ Look at event watcher terminal for error messages
- ✅ Verify your run ID is correct in the dashboard URL
- ✅ Try refreshing the web page

#### "No encounters detected"

**Symptoms**: Playing normally but Lua script doesn't detect encounters

**Solutions**:
- ✅ Make sure you're in a wild Pokemon battle (not trainer battle)
- ✅ Check DeSmuME console for error messages
- ✅ Try encountering Pokemon in different locations
- ✅ Verify ROM is properly loaded and working
- ✅ Check if your ROM version is supported

### Debug Mode

If you're having issues, enable debug mode:

1. **Lua Config**: Set `debug_mode = true`
2. **Watcher Config**: Set `"debug": true`
3. **Restart both** the Lua script and event watcher

This will show detailed information about what's happening.

### Getting Help

**Before asking for help**, try:

1. ✅ **Restart everything**: DeSmuME, Lua script, event watcher
2. ✅ **Check all configuration** files have correct values
3. ✅ **Test basic connectivity**: `curl http://ADMIN_IP:9000/health`
4. ✅ **Look at terminal/console** output for error messages

**When asking admin for help**, provide:

- 📋 **Error messages** from terminal/console
- ⚙️ **Your configuration files** (remove your token for privacy)
- 🖥️ **Your operating system** (Windows/Mac/Linux)
- 🎮 **ROM version** and region
- 📱 **What you were doing** when the problem occurred

## Advanced Tips

### Multiple Computers

If you're playing on a different computer than where you run the watcher:

1. **Run DeSmuME + Lua script** on gaming computer
2. **Set output directory** to shared network folder
3. **Run event watcher** on computer with internet access
4. **Point watcher** to the shared folder

### Performance Optimization

For better performance:

```lua
-- In your Lua config
poll_interval = 30,              -- Check memory more frequently (30 frames = 0.5 seconds)
max_events_per_minute = 60,      -- Allow more events per minute
```

### Backup Your Save

**Highly recommended**: Backup your Pokemon save file regularly!

- **DeSmuME saves** are in the `Battery` folder
- **Copy your .dsv file** to a safe location
- **Back up before major events** (Elite Four, risky encounters)

## File Structure

Your player folder should look like:

```
📁 YourPlayerFolder/
├── pokemon_tracker.lua          # Main Lua script
├── your_config.lua             # Your Lua configuration
├── event_watcher.py            # Python event watcher
├── your_config.json            # Your watcher configuration
├── requirements.txt            # Python dependencies
└── temp/                       # Event files (created automatically)
    ├── event_1234567890_1234.json
    ├── event_1234567891_5678.json
    └── ...
```

## What Happens During Play

### Normal Gameplay Flow

1. 🎮 **You play Pokemon** normally in DeSmuME
2. 👁️ **Lua script detects** encounters/catches/faints automatically
3. 📝 **Events are written** to JSON files in your temp folder
4. 🔄 **Python watcher reads** the files and sends them to the server
5. ⚡ **Admin's dashboard updates** in real-time
6. 🔗 **Soul links form** when you and teammates catch on same route
7. 🎉 **Everyone sees** the progress live on the dashboard!

### What You'll See

**In DeSmuME Console**:
```
[SoulLink] Encounter detected: Species 19 Level 3
[SoulLink] Battle ended: caught
[SoulLink] Pokemon fainted: personality_123456
```

**In Event Watcher Terminal**:
```
Event sent successfully: encounter
Event sent successfully: catch_result  
Health: 15 events processed, 0 failed, 0 API errors
```

**On Web Dashboard**:
- 📊 Your encounter count goes up
- 📝 "Wild Rattata appeared!" shows in recent events
- ⚾ "Rattata was caught!" appears when you catch it
- 🔗 Soul link forms if teammate caught on same route

---

## Ready to Play! 🎮

Once everything is set up:

1. ✅ **DeSmuME running** with your Pokemon game
2. ✅ **Lua script loaded** and showing debug messages  
3. ✅ **Event watcher running** and connected to server
4. ✅ **Web dashboard open** and showing your player
5. ✅ **Ready to start** your SoulLink adventure!

**Important Reminders**:
- 💾 **Save your game frequently** (in case of crashes)
- 🔍 **Keep an eye on the dashboard** to see soul links form
- 💬 **Coordinate with teammates** about encounters and routes
- 🎉 **Have fun** - the system handles all the rule tracking automatically!

**Good luck, trainer! May your encounters be kind and your soul links be strong! 🔗✨**

*Remember: The admin can see everything on their dashboard, so they can help troubleshoot if anything goes wrong!*