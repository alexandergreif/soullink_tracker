# SoulLink Tracker - Windows Setup Guide

**Easy setup for Windows users who don't know Python!**

This guide is for regular Windows users who just want to run SoulLink Tracker without dealing with technical details.

## 📥 What You Downloaded

You should have downloaded/extracted a folder called `SoulLink_Tracker` that contains these important files:
- `windows_installer.bat` - **START HERE** (installs everything automatically)
- `run_admin_setup.bat` - For admins (runs the server)
- `run_player_setup.bat` - For players (joins the game)

## 🎯 Quick Start

### If You're the **Admin** (hosting the game):

1. **Double-click** `windows_installer.bat`
   - This installs Python and all required software automatically
   - Takes 5-10 minutes depending on your internet speed
   - You only need to do this once!

2. **Double-click** `run_admin_setup.bat`
   - Choose option 2 (Production mode) for remote players
   - The server will start and give you a public URL
   - Keep this window open while playing!

3. **Generate player packages**:
   - When setup finishes, it will tell you to run a command
   - Open Command Prompt in the SoulLink_Tracker folder
   - Type: `python scripts\distribute_players.py`
   - This creates ZIP files for each player

4. **Send ZIP files to players**
   - Each player gets their own ZIP file
   - They extract it and run the setup

### If You're a **Player** (joining the game):

1. **Get your setup package** from the admin (a ZIP file)

2. **Extract the ZIP file** to your Desktop or Documents

3. **Double-click** `windows_installer.bat` (if Python isn't installed)
   - This installs Python and all required software automatically
   - You only need to do this once!

4. **Double-click** `run_player_setup.bat`
   - This connects you to the admin's server
   - Follow the instructions to set up DeSmuME

5. **Download DeSmuME** separately:
   - Go to: https://desmume.org/download/
   - Download the Windows version
   - Install it normally

## 📋 Detailed Instructions

### First Time Installation (Everyone)

**Step 1: Install Python and Dependencies**

1. **Right-click** on `windows_installer.bat`
2. **Select "Run as administrator"** (recommended)
3. **Click "Yes"** when Windows asks for permission
4. **Follow the prompts**:
   - Press any key to continue
   - Type "y" and press Enter when asked to install Python
   - Wait for everything to download and install (5-10 minutes)
5. **Installation complete!** You'll see a success message

**What this installer does:**
- Downloads and installs Python 3.11 (if needed)
- Installs all required Python packages
- Creates folders and shortcuts
- Sets everything up automatically

### Admin Setup (Server Host)

**Step 2: Start the Server**

1. **Double-click** `run_admin_setup.bat`
2. **Choose your mode**:
   - Type "1" for local testing (same network only)  
   - Type "2" for internet play (remote players) ✅ **Recommended**
   - Type "3" to reset everything and start over
3. **Wait for setup** to complete
4. **Important**: Keep this window open! The server runs here
5. **Copy the public URL** - you'll give this to players

**Step 3: Create Player Packages**

1. **When setup finishes**, you'll see instructions
2. **Press Ctrl+C** to stop the server temporarily  
3. **Open Command Prompt** in the SoulLink_Tracker folder:
   - Press `Windows key + R`
   - Type `cmd` and press Enter
   - Type `cd ` (with a space) then drag the SoulLink_Tracker folder into the window
   - Press Enter
4. **Type**: `python scripts\distribute_players.py`
5. **Press Enter** - this creates player packages
6. **Send the ZIP files** to each player (each player gets a different file)
7. **Restart the server** by double-clicking `run_admin_setup.bat` again

### Player Setup (Joining the Game)

**Step 2: Connect to Server**

1. **Extract your ZIP file** (the one the admin sent you)
2. **Double-click** `run_player_setup.bat` in the extracted folder
3. **Follow the setup wizard** - it should find your config automatically
4. **Wait for setup** to complete
5. **Keep this window open!** The watcher runs here

**Step 3: Setup DeSmuME**

1. **Download DeSmuME** from https://desmume.org/download/
2. **Install DeSmuME** normally (just click Next, Next, Install)
3. **Open DeSmuME**
4. **Load your Pokemon HeartGold/SoulSilver ROM**
5. **Open the Lua Script Console**:
   - In DeSmuME: Tools → Lua Script Console
6. **Load the tracking script**:
   - In the Lua console: File → Open
   - Navigate to your extracted folder
   - Open: `client\lua\configs\your_name_config.lua`
7. **Start playing!** Events are tracked automatically

## 🖥️ What Each Window Does

When everything is running, you'll have these windows open:

### Admin (Server Host):
- **Admin Setup Window**: Shows server status, must stay open
- **Web Browser**: Dashboard showing all players' progress
- **Command Prompt** (optional): For running admin commands

### Players:
- **Player Setup Window**: Shows event watcher status, must stay open  
- **DeSmuME**: The actual game emulator
- **DeSmuME Lua Console**: Shows script status (can be minimized)
- **Web Browser**: Dashboard to view everyone's progress

## 🔧 Troubleshooting

### "Python not found" error:
- Run `windows_installer.bat` first
- Make sure it completed successfully
- Try restarting your computer

### "Failed to connect to server":
- Check that the admin's server is running
- Verify your player config file has the correct server URL
- Make sure your antivirus isn't blocking the connection

### "Script not working in DeSmuME":
- Make sure you loaded the correct `.lua` file for your player
- Check that the Lua console shows no error messages
- Verify your ROM is compatible (HeartGold/SoulSilver)

### Events not showing up:
- Check that both the player setup window and DeSmuME are running
- Look for error messages in the player setup window
- Make sure you're encountering Pokemon in the game

### General problems:
1. Close everything and restart
2. Check the `logs` folder for error details
3. Contact your admin for help
4. Try running as administrator

## 🆘 Getting Help

If you're stuck:

1. **Check the logs folder** - look for files ending in `.log`
2. **Take a screenshot** of any error messages
3. **Contact your admin** - they can help troubleshoot
4. **Make sure all windows stay open** while playing

## 📱 System Requirements

- **Windows 10 or 11** (Windows 7/8 might work but not tested)
- **Internet connection** (for initial setup and server communication)
- **At least 1GB free disk space**
- **DeSmuME emulator** (download separately)
- **Pokemon HeartGold or SoulSilver ROM** (not included)

## 🎮 Ready to Play!

Once everything is set up:
- Your events (encounters, catches, faints) are tracked automatically
- Check the web dashboard to see everyone's progress
- Follow SoulLink rules as agreed by your group
- Have fun!

---

**Need more help?** Ask your admin or check the detailed `SETUP_GUIDE.md` for technical users.