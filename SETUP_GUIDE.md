# SoulLink Tracker Complete Setup Guide

This guide will get you up and running with the complete SoulLink tracking system.

## 🎯 Quick Start (3 Steps)

### Step 1: Start the Server
```bash
# Windows (double-click)
start_server.bat

# Or manually
python start_server.py
```

### Step 2: Start the Event Watcher
```bash
# Windows (double-click) 
start_watcher.bat

# Or manually
python simple_watcher.py
```

### Step 3: Load Lua Script in DeSmuME
1. Open Pokemon HeartGold/SoulSilver ROM in DeSmuME
2. Tools → Lua Script Console
3. Browse → `client/lua/pokemon_tracker_v3_fixed.lua`
4. Click Run

## 📊 Data Flow

```
Pokemon ROM → Lua Script → JSON Files → Python Watcher → API Server → Dashboard
```

## 🖥️ URLs

- **Dashboard**: http://127.0.0.1:8000/dashboard
- **Admin Panel**: http://127.0.0.1:8000/admin
- **API Docs**: http://127.0.0.1:8000/docs

## 🔧 Detailed Setup

### Prerequisites

1. **Python 3.8+** installed and in PATH
2. **DeSmuME 0.9.11+** with Lua support
3. **Pokemon HeartGold/SoulSilver ROM**

### Server Setup

The server handles the API, database, and web interface.

**Automatic (Windows):**
```bash
start_server.bat
```

**Manual:**
```bash
python start_server.py
```

**Expected Output:**
```
🎮 SoulLink Tracker - Server Startup
✅ All required dependencies are installed
🔧 Running database migrations...
✅ Database migrations completed successfully
📊 Loading reference data...
✅ Reference data loaded successfully
🚀 Starting SoulLink Tracker server...
📍 Server will be available at: http://127.0.0.1:8000
```

### Event Watcher Setup

The watcher reads JSON files from Lua and sends them to the API.

**Automatic (Windows):**
```bash
start_watcher.bat
```

**Manual:**
```bash
python simple_watcher.py
```

**Expected Output:**
```
=== Simple SoulLink Event Watcher ===
API Server: http://127.0.0.1:8000
Watch Directory: C:/temp/soullink_events/
✅ Server is running and accessible
Using run: Test SoulLink Run (12345678-1234-5678-9abc-123456789abc)
Using player: TestPlayer (87654321-4321-8765-cba9-987654321abc)
Starting monitoring loop...
```

### DeSmuME Lua Setup

The Lua script monitors the ROM and writes event files.

**Files to use:**
1. **First time**: `client/lua/test_desmume.lua` (compatibility test)
2. **Main script**: `client/lua/pokemon_tracker_v3_fixed.lua`

**Steps:**
1. Open Pokemon ROM in DeSmuME
2. Tools → Lua Script Console
3. Browse → Select script file
4. Click "Run"

**Expected Output:**
```
[12:34:56] [SoulLink V3] === Pokemon SoulLink Tracker V3 (Fixed) ===
[12:34:56] [SoulLink V3] Output directory: C:/temp/soullink_events/
[12:34:56] [SoulLink V3] Initialization complete, monitoring for events...
[12:35:06] [SoulLink V3] Script running for 10 seconds, monitoring...
```

## 🎮 Usage

### Creating Runs and Players

1. Go to **Admin Panel**: http://127.0.0.1:8000/admin
2. Click "Create New Run"
3. Enter run details (name, rules)
4. Add players (name, game version, region)
5. Copy player tokens for watcher configuration

### Monitoring Progress

1. Go to **Dashboard**: http://127.0.0.1:8000/dashboard
2. Select your run from the dropdown
3. Watch real-time updates as you play

### Event Types Tracked

- **Encounters**: Wild Pokemon appearing in battle
- **Catch Results**: Whether Pokemon were caught, fled, or fainted
- **Party Faints**: When your Pokemon reach 0 HP
- **Location Changes**: Moving between routes

## 🔍 Troubleshooting

### Server Won't Start

**Issue**: `ModuleNotFoundError: No module named 'soullink_tracker'`
**Solution**: Make sure you're in the project root directory and run `start_server.bat`

**Issue**: Missing dependencies
**Solution**: Install requirements with `pip install -r requirements.txt`

### Watcher Won't Connect

**Issue**: `Cannot connect to server`
**Solution**: Make sure the server is running first (`start_server.bat`)

**Issue**: No events being processed
**Solution**: Check that Lua script is writing files to `C:/temp/soullink_events/`

### Lua Script Stops

**Issue**: "script finished running" immediately
**Solution**: Use `pokemon_tracker_v3_fixed.lua` instead of the basic version

**Issue**: Memory read errors
**Solution**: Run `test_desmume.lua` first to check compatibility

### Dashboard Shows No Data

**Issue**: Dashboard loads but shows no events
**Solution**: Make sure the watcher is running (`start_watcher.bat`)

**Issue**: Events created but not appearing
**Solution**: Check watcher logs for API connection errors

## 📁 File Structure

```
SoulLink_Tracker/
├── start_server.bat          # Start the server (Windows)
├── start_server.py           # Start the server (cross-platform)
├── start_watcher.bat         # Start the event watcher (Windows)
├── simple_watcher.py         # Simple event watcher
├── client/lua/
│   ├── test_desmume.lua      # DeSmuME compatibility test
│   ├── pokemon_tracker_v3_fixed.lua  # Main Lua script (robust)
│   └── pokemon_tracker_v3.lua        # Basic Lua script
├── src/soullink_tracker/     # Main application code
└── web/                      # Dashboard and admin panel
```

## 🚀 Advanced Configuration

### Custom Directories

Edit `simple_watcher.py` to change directories:
```python
CONFIG = {
    'api_base_url': 'http://127.0.0.1:8000',
    'watch_directory': 'D:/my_events/',  # Change this
    'poll_interval': 2,
}
```

### Multiple Players

1. Create additional runs/players in admin panel
2. Configure each player's Lua script with their token
3. Run separate watcher instances for each player

### Network Setup

To run across multiple computers:
1. Change `127.0.0.1` to the server computer's IP address
2. Ensure firewall allows port 8000
3. Update Lua script and watcher configurations

## 📊 Monitoring

### Log Files

- **Server logs**: Shown in console
- **Watcher logs**: Shown in console
- **Lua logs**: DeSmuME console output

### Health Checks

- **Server health**: http://127.0.0.1:8000/health
- **API status**: http://127.0.0.1:8000/docs

## 💡 Tips

1. **Always start server first**, then watcher, then Lua script
2. **Use the batch files** on Windows for easier startup
3. **Check logs** if something isn't working
4. **Test with `test_desmume.lua`** if Lua script has issues
5. **Keep DeSmuME console open** to see Lua script output

## 🆘 Getting Help

If you encounter issues:

1. Check this troubleshooting guide
2. Look at console output for error messages
3. Try the test scripts (`test_desmume.lua`)
4. Create a GitHub issue with error details

## 🎉 Success Indicators

You know everything is working when:

- ✅ Server shows "Starting SoulLink Tracker server..."
- ✅ Watcher shows "Starting monitoring loop..."
- ✅ Lua script shows "Script running for X seconds, monitoring..."
- ✅ Dashboard shows your run and real-time events
- ✅ Encountering Pokemon creates events in the dashboard