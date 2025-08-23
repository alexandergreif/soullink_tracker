# SoulLink Tracker

**Real-time tracker for 3-player Pokemon SoulLink runs in Pokemon HeartGold/SoulSilver**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![WebSocket](https://img.shields.io/badge/websocket-realtime-orange.svg)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![Windows](https://img.shields.io/badge/windows-supported-brightgreen.svg)](https://www.microsoft.com/windows)

Automatically tracks Pokemon encounters, catches, faints, and soul links across multiple players in real-time using DeSmuME Lua scripts and a centralized web dashboard.

## 🎮 What is SoulLink?

**SoulLink** is a challenging Pokemon variant where 2-3 players play linked games:
- 🔗 Pokemon caught on the same route become "soul linked" 
- 💀 If one linked Pokemon faints, **all linked Pokemon must be released**
- 🚫 **Dupes Clause**: Only first encounter of each species family counts
- 👥 **Species Clause**: Each player can only have one of each species family

## ✨ Features

- 🎯 **Automatic Detection**: DeSmuME Lua scripts detect encounters, catches, faints in real-time
- ⚡ **Real-time Updates**: WebSocket-based live dashboard for all players
- 🔗 **SoulLink Rules**: Automatically enforces dupes clause, species clause, soul link creation
- 🎣 **Full Encounter Support**: Grass, water, fishing, headbutt, rock smash encounters  
- 🌟 **Shiny Detection**: Automatically flags shiny Pokemon
- 📊 **Web Dashboard**: Beautiful real-time monitoring interface
- 🔒 **Secure**: JWT authentication per player
- 🪟 **Windows Friendly**: One-click setup for non-technical users

## 🆕 Key Features

- 🚀 **Simple Setup**: Single script to start everything
- 🔑 **Easy Authentication**: Interactive token generation
- 📊 **Admin Dashboard**: Web-based run management
- 📱 **Real-time Sync**: Live updates across all players
- 🔒 **Secure**: Token-based authentication
- 📈 **SQLite Database**: No complex database setup required
- 🔄 **Auto-migrations**: Database updates handled automatically
- 🎯 **Developer-friendly**: Hot reload during development

## 🚀 Quick Start

### Simple Setup (One Script)

**Step 1: Start the Server**
```bash
python start_server.py
```
This will:
- Run database migrations
- Load reference data
- Start the admin server at `http://127.0.0.1:8000`
- Open the admin panel in your browser

**Step 2: Create Runs and Players**
1. Open the admin panel: `http://127.0.0.1:8000/admin`
2. Create a new run with a password
3. Add players to the run
4. Share run info with players: run name + password

### 🔑 Authentication Workflow

**For Admin (Run Organizer):**
1. Start server: `python start_server.py`
2. Open admin panel: `http://127.0.0.1:8000/admin`
3. Create run with password
4. Add players (name, game version, region)
5. Share with players: run name + password

**For Players (Watcher Setup):**
1. Get from admin: run name + password
2. Configure watcher with:
   - **Server URL**: `http://127.0.0.1:8000`
   - **Run Name**: (from admin)
   - **Player Name**: (your name in the run)
   - **Password**: (run password from admin)
3. Watcher automatically logs in via `/v1/auth/login`

**Security:**
- Password-based authentication per run
- Automatic session token generation
- No complex token management needed

### 📱 Example Watcher Configuration

```json
{
  "server_url": "http://127.0.0.1:8000",
  "run_name": "Epic SoulLink Adventure",
  "player_name": "Alice",
  "password": "myrunpassword123"
}
```

Watcher login process:
1. POST `/v1/auth/login` with above credentials
2. Receive session token automatically
3. Use token for all subsequent API calls
4. Token expires after 30 days (configurable)
- **Download**: `soullink-tracker-admin-v3.0.0-windows-x64.zip`

#### 🎮 **User Version** (For Players)
- Lightweight client with watcher and Lua scripts
- Connects to admin's server automatically
- **Download**: `soullink-tracker-user-v3.0.0-windows-x64.zip`

### Setup Instructions:

#### For Admins (Run Organizers):
1. **Download** the Admin package from [Releases](https://github.com/alexandergreif/soullink_tracker/releases)
2. **Extract** the ZIP file to your Desktop
3. **Run** `soullink-tracker-admin.exe`
4. **Browser opens** automatically to the dashboard
5. **Create a run** and add player tokens
6. **Share** the API URL and tokens with players

#### For Players:
1. **Download** the User package from [Releases](https://github.com/alexandergreif/soullink_tracker/releases)
2. **Extract** the ZIP file to your Desktop
3. **Get** API URL and player token from your admin
4. **Run** `soullink-tracker-user.exe`
5. **Lua folder opens** automatically
6. **Load** `pokemon_tracker_v3.lua` in DeSmuME
7. **Start playing** - encounters are tracked automatically!

### 🔧 Advanced Setup (Source Code)

**For developers or advanced users who want to run from source:**

2. **For Server Host (Admin)**:
   - Double-click `windows_installer.bat` (installs Python automatically)
   - Double-click `run_admin_setup.bat` (starts the server)
   - Follow the [Windows Setup Guide →](WINDOWS_SETUP.md)

3. **For Players**:
   - Get your setup package from the admin
   - Double-click `windows_installer.bat` (if needed)
   - Double-click `run_player_setup.bat` (connects to server)
   - Follow the [Windows Setup Guide →](WINDOWS_SETUP.md)

### 🐧 Linux/Mac Users

**For technical users comfortable with command line:**

```bash
# Clone repository
git clone https://github.com/alexandergreif/Soullink_Tracker.git
cd Soullink_Tracker

# For Admin (server host)
python3 scripts/admin_setup.py --production

# For Players  
python3 scripts/player_setup.py player_config.json
```

## 📖 Documentation

### 📋 Setup Guides
- 🪟 **[Windows Setup Guide](WINDOWS_SETUP.md)** - For Windows users (recommended)
- 🐧 **[Advanced Setup](scripts/)** - For technical users with Python experience

### 📚 Project Information
- 🔧 **[Developer Context](CLAUDE.md)** - Technical details and architecture
- 📁 **[Client Files](client/)** - DeSmuME Lua scripts and Python watchers
- 🌐 **[Web Dashboard](web/)** - Real-time monitoring interface

## 📋 What You Need

### For Everyone
- 🎮 **DeSmuME** emulator (download separately from [desmume.org](https://desmume.org))
- 📀 **Pokemon HeartGold/SoulSilver ROM**
- 🌐 **Internet connection**

### Windows Users
- 🪟 **Windows 10 or 11**
- **No Python knowledge required** - everything is automated!

### Linux/Mac Users  
- 🐍 **Python 3.8+**
- Basic command line knowledge

## 🎯 How It Works

### V3 Dual-Architecture System

```
📊 ADMIN: FastAPI + SQLite + WebSocket Dashboard
                    ↑ HTTP/WebSocket API ↓
🎮 USER: DeSmuME → Lua Script → Watcher → API Server
```

#### Admin Side:
1. **📊 Admin runs** `soullink-tracker-admin.exe`
2. **🌐 Server starts** with FastAPI + SQLite database
3. **📊 Dashboard opens** in browser for monitoring
4. **🗗️ API provides** real-time endpoints for players

#### User Side:
1. **🎮 Player runs** `soullink-tracker-user.exe`
2. **📝 Lua script** detects encounters, catches, faints in DeSmuME
3. **🔄 Watcher** processes events and sends to admin's server
4. **⚡ Updates appear** instantly on admin's dashboard
5. **🔗 Soul links** form automatically when players catch on same route

## 🛠️ V3 Architecture

### Package Structure:
```
📊 Admin Package (soullink-tracker-admin-v3.0.0.zip):
│
├── soullink-tracker-admin.exe     # Main server executable
├── soullink-tracker-admin-debug.exe # Debug version with console
├── QUICK_START_ADMIN.txt          # Setup instructions
└── README.md + LICENSE             # Documentation

🎮 User Package (soullink-tracker-user-v3.0.0.zip):
│
├── soullink-tracker-user.exe      # Client executable
├── soullink-tracker-user-debug.exe # Debug version with console
├── QUICK_START_USER.txt           # Setup instructions
└── README.md + LICENSE             # Documentation
```

### Source Code Structure:
```
SoulLink_Tracker/
├── soullink_portable.py           # 📊 Admin entry point
├── soullink_user_portable.py      # 🎮 User entry point
├── build_dual.py                  # 🛠️ Builds both packages
├── client/lua/                    # 📝 DeSmuME Lua scripts
├── watcher/                       # 🔄 Python watcher components
├── web/                           # 🌐 Web dashboard (admin only)
└── src/soullink_tracker/          # ⚙️ Core application logic
```

## 🐛 Troubleshooting

### Windows Issues
- **"Python not found"**: Run `windows_installer.bat` first
- **"Can't connect"**: Check that admin's server is running
- **"Script not working"**: Make sure you loaded the correct `.lua` file

### V3 Specific Issues

#### Admin Issues:
- **"Port already in use"**: Another server is running, try debug version to see console
- **"Database error"**: Check logs/ directory for SQLite issues
- **"Browser doesn't open"**: Manually go to http://127.0.0.1:8000

#### User Issues:
- **"Cannot connect to API"**: Make sure admin's server is running and API URL is correct
- **"Lua folder not opening"**: Run as administrator or check antivirus settings
- **"Watcher not starting"**: Check logs_user/ directory for error details

### General Issues
- **Events not appearing**: Verify DeSmuME has the Lua script loaded
- **Dashboard not updating**: Check WebSocket connection in browser dev tools
- **Antivirus blocking**: Add executables to antivirus whitelist

### Getting Help

1. **📖 Read the setup guide**: [Windows Setup Guide](WINDOWS_SETUP.md)
2. **📁 Check logs folder** for error details
3. **📧 Contact your admin** for troubleshooting help
4. **🐛 Open an issue** on GitHub with error details

## 🎉 Success Stories

*"The one-click Windows installer made this so easy! We were playing within 10 minutes."* - Windows user

*"Real-time dashboard made our 3-player SoulLink run incredibly engaging!"* - SoulLink group

*"No more spreadsheet tracking - everything just works automatically."* - Player feedback

## 🗺️ Roadmap

### ✅ Completed
- ✅ Real-time encounter/catch/faint detection
- ✅ Web dashboard with live updates  
- ✅ SoulLink rules enforcement
- ✅ Windows-friendly one-click setup
- ✅ Comprehensive test suite

### 🔄 Planned
- 📱 Mobile-responsive dashboard improvements
- 🎮 Support for other Pokemon games
- 📊 Advanced statistics and analytics
- 🤖 Discord bot integration

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🎮 Ready to Start Your SoulLink Adventure?

### 🪟 Windows Users (Most People)
**[👉 Start Here: Windows Setup Guide](WINDOWS_SETUP.md)**

### 🐧 Technical Users (Linux/Mac)
**[👉 Advanced Setup Scripts](scripts/)**

### ❓ Need Help?
**[👉 Troubleshooting & Support](WINDOWS_SETUP.md#troubleshooting)**

---

**May your encounters be kind and your soul links be strong! 🔗✨**

*Built with ❤️ for the Pokemon challenge community*


⏺ Perfect! Here's your quick start guide:

  🚀 Easy 3-Step Start

  Option 1: Windows (Super Easy)

  Just double-click these files in order:
  1. start_server.bat → Wait for "Server will be available at..."
  2. start_watcher.bat → Wait for "Starting monitoring loop..."
  3. Load Lua script in DeSmuME → client/lua/pokemon_tracker_v3_fixed.lua

  Option 2: Manual (Any OS)

  # Step 1: Start server
  python start_server.py

  # Step 2: Start watcher (in new terminal)
  python simple_watcher.py

  # Step 3: Load Lua script in DeSmuME

  ✅ Prerequisites Check

  The scripts do auto-check most things for you! But you need:

  1. Python 3.8+ (check: python --version)
  2. DeSmuME with Lua support
  3. Pokemon HeartGold/SoulSilver ROM

  🔍 What the Scripts Auto-Handle:

  - ✅ Dependencies: Auto-installs Python packages (requirements.txt)
  - ✅ Database setup: Runs migrations automatically
  - ✅ Reference data: Loads Pokemon/route data
  - ✅ Configuration: Creates config files if missing
  - ✅ Directory creation: Makes event directories
  - ✅ Server health checks: Verifies everything is working

  📊 URLs After Startup:

  - Dashboard: http://127.0.0.1:8000/dashboard
  - Admin Panel: http://127.0.0.1:8000/admin
  - API Docs: http://127.0.0.1:8000/docs

  ⚡ Expected Output:

  Server startup:
  🎮 SoulLink Tracker - Server Startup
  ✅ All required dependencies are installed
  🔧 Running database migrations...
  ✅ Database migrations completed successfully
  🚀 Starting SoulLink Tracker server...

  Watcher startup:
  === Simple SoulLink Event Watcher ===
  ✅ Server is running and accessible
  Starting monitoring loop...

  🎯 First Time Setup:

  1. Start server & watcher (steps above)
  2. Go to Admin Panel: http://127.0.0.1:8000/admin
  3. Create a new run with your rules
  4. Add yourself as a player
  5. Copy your player token for later
  6. Load Lua script in DeSmuME with your ROM
  7. Open Dashboard to see events live!

  🆘 If Something Breaks:

  The setup guide has comprehensive troubleshooting, but most common issues:
  - "ModuleNotFoundError" → Run from project root directory
  - "Cannot connect to server" → Start server first
  - "Lua script stops immediately" → Use pokemon_tracker_v3_fixed.lua

  Just run the start scripts - they handle almost everything automatically! 🎮
  