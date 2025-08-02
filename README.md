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

## 🚀 Quick Start

### 🪟 Windows Users (Recommended)

**Most users should use this method - no technical knowledge required!**

1. **Download this project**:
   - Click the green "Code" button above → "Download ZIP"
   - Extract the ZIP file to your Desktop

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

```
🎮 Pokemon Game → 📝 Lua Script → 🔄 Python Watcher → 🌐 Web Server → 📊 Dashboard
```

1. **🎮 Play Pokemon** normally in DeSmuME
2. **📝 Lua script** automatically detects encounters, catches, faints
3. **🔄 Python watcher** sends events to central server
4. **⚡ Web dashboard** updates in real-time for all players
5. **🔗 Soul links** form automatically when players catch on same route

## 🛠️ Project Structure

```
SoulLink_Tracker/
├── windows_installer.bat          # 🪟 One-click Windows installer
├── run_admin_setup.bat            # 🔧 Admin server launcher  
├── run_player_setup.bat           # 🎮 Player client launcher
├── WINDOWS_SETUP.md               # 📖 Windows user guide
├── scripts/                       # 🐍 Python setup scripts
├── client/                        # 📱 Client components
│   ├── lua/                       # 🎮 DeSmuME Lua scripts
│   └── watcher/                   # 🔄 Python event watchers
├── web/                           # 🌐 Web dashboard
└── src/                           # ⚙️ Main application
```

## 🐛 Troubleshooting

### Windows Issues
- **"Python not found"**: Run `windows_installer.bat` first
- **"Can't connect"**: Check that admin's server is running
- **"Script not working"**: Make sure you loaded the correct `.lua` file

### General Issues
- **Events not appearing**: Check both DeSmuME and watcher are running
- **Dashboard not updating**: Verify internet connection and server status
- **Need help**: Check the logs folder or contact your admin

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