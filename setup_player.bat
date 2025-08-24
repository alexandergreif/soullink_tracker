@echo off
REM SoulLink Tracker - Player Setup Helper
REM This script helps you configure the Lua script after logging in

echo ===============================================
echo SoulLink Tracker - Player Configuration Helper
echo ===============================================
echo.

REM Check if player credentials file exists
if not exist "%APPDATA%\SoulLink\player_config.json" (
    echo ERROR: No player credentials found!
    echo.
    echo Please log in first:
    echo 1. Open http://127.0.0.1:8000/player in your browser
    echo 2. Enter your run name, player name, and password
    echo 3. Click "Join Run"
    echo 4. After successful login, run this script again
    echo.
    pause
    exit /b 1
)

echo Found player credentials!
echo.

REM Parse the JSON to get run_id and player_id
for /f "tokens=2 delims=:, " %%a in ('type "%APPDATA%\SoulLink\player_config.json" ^| findstr "run_id"') do set RUN_ID=%%~a
for /f "tokens=2 delims=:, " %%a in ('type "%APPDATA%\SoulLink\player_config.json" ^| findstr "player_id"') do set PLAYER_ID=%%~a
for /f "tokens=2 delims=:, " %%a in ('type "%APPDATA%\SoulLink\player_config.json" ^| findstr "token"') do set TOKEN=%%~a

echo Configuration found:
echo Run ID: %RUN_ID%
echo Player ID: %PLAYER_ID%
echo.

REM Create the Lua config file
echo Creating Lua configuration file...
(
echo -- SoulLink Tracker Configuration
echo -- Auto-generated on %date% %time%
echo.
echo local config = {
echo     -- API Configuration
echo     api_base_url = "http://127.0.0.1:8000",
echo.    
echo     -- Run and Player IDs from login
echo     run_id = "%RUN_ID%",
echo     player_id = "%PLAYER_ID%",
echo.    
echo     -- Event Output Configuration
echo     output_dir = "C:/temp/soullink_events/",
echo.    
echo     -- Script Behavior
echo     poll_interval = 60,    -- Frames between checks
echo     debug = true,          -- Enable debug logging
echo     max_runtime = 3600,    -- Maximum runtime in seconds
echo.    
echo     -- Memory Profile
echo     memory_profile = "US"  -- Change to "EU" if needed
echo }
echo.
echo return config
) > client\lua\config.lua

echo ✅ Lua configuration created at client\lua\config.lua
echo.

REM Start the watcher if not already running
echo Starting event watcher...
start "SoulLink Watcher" /min cmd /c "python simple_watcher.py --run-id %RUN_ID% --player-id %PLAYER_ID% --token %TOKEN%"

echo.
echo ===============================================
echo Setup Complete!
echo ===============================================
echo.
echo Next steps:
echo 1. Open DeSmuME emulator
echo 2. Load your Pokemon HeartGold/SoulSilver ROM
echo 3. Go to Tools -^> Lua Scripting -^> New Lua Script Window
echo 4. Browse and load: client\lua\pokemon_tracker_v3_fixed.lua
echo 5. The script will start monitoring your game!
echo.
echo The watcher is running in the background to send events to the server.
echo.
pause