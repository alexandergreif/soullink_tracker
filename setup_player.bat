@echo off
REM setup_player.bat - Windows setup helper for SoulLink Tracker
REM This script helps generate Lua configuration using the interactive wizard

echo ===============================================
echo   SoulLink Tracker - Player Setup
echo ===============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.8+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Check if database exists
if not exist "soullink_tracker.db" (
    echo WARNING: Database not found!
    echo.
    echo The server needs to be started at least once to create the database.
    echo Run: python start_server.py
    echo.
    pause
)

REM Run the configuration generator in interactive mode
echo Starting configuration wizard...
echo.
python generate_lua_config.py --interactive

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===============================================
    echo   Setup Complete!
    echo ===============================================
    echo.
    echo ✅ Configuration file created successfully!
    echo.
    echo Next steps:
    echo   1. Open DeSmuME emulator
    echo   2. Load your Pokemon HeartGold/SoulSilver ROM
    echo   3. Go to Tools -^> Lua Scripting -^> New Lua Script Window
    echo   4. Browse to: client\lua\pokemon_tracker_v3_fixed.lua
    echo   5. Click Run to start tracking!
    echo.
    echo Additional steps:
    echo   - Start the watcher: python simple_watcher.py
    echo   - Open dashboard: http://127.0.0.1:8000
    echo.
    pause
) else (
    echo.
    echo ===============================================
    echo   Setup Failed
    echo ===============================================
    echo.
    echo ❌ Configuration generation failed.
    echo.
    echo Please check the error messages above.
    echo.
    echo Common issues:
    echo   1. Server not running - Start with: python start_server.py
    echo   2. No runs created - Use admin panel at http://127.0.0.1:8000/admin
    echo   3. Database locked - Close other applications using the database
    echo.
    pause
    exit /b 1
)