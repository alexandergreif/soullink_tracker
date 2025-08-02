@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM SoulLink Tracker - Player Setup Launcher
REM Simple double-click launcher for the player setup script
REM ============================================================================

echo.
echo ========================================================
echo   SoulLink Tracker - Player Setup
echo ========================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please run the windows_installer.bat first to install Python
    echo and all required dependencies.
    echo.
    pause
    exit /b 1
)

REM Check if player setup script exists
if not exist "scripts\player_setup.py" (
    echo ERROR: Player setup script not found
    echo.
    echo Expected location: scripts\player_setup.py
    echo Current directory: %CD%
    echo.
    echo Please make sure you're running this from the SoulLink Tracker directory
    echo and that all files have been extracted properly.
    echo.
    pause
    exit /b 1
)

echo Python found. Starting player setup...
echo.

REM Look for player configuration file
set CONFIG_FILE=

REM Check for config files in current directory
for %%f in (*.json) do (
    findstr /i "player_id\|server_url\|bearer_token" "%%f" >nul 2>&1
    if !errorlevel! equ 0 (
        set CONFIG_FILE=%%f
        echo Found configuration file: %%f
        goto :found_config
    )
)

REM Check for common config file names
for %%f in (player_config.json config.json player*.json) do (
    if exist "%%f" (
        set CONFIG_FILE=%%f
        echo Found configuration file: %%f
        goto :found_config
    )
)

:found_config
if defined CONFIG_FILE (
    echo.
    echo Starting player setup with configuration: %CONFIG_FILE%
    echo.
    python scripts\player_setup.py "%CONFIG_FILE%"
) else (
    echo No configuration file found.
    echo.
    echo You have two options:
    echo   1. Place your player configuration file (*.json) in this directory
    echo   2. Run interactive setup (you'll need to enter details manually)
    echo.
    set /p CHOICE=Enter 1 or 2: 
    
    if "!CHOICE!" == "1" (
        echo.
        echo Please:
        echo   1. Get your player_config.json file from the admin
        echo   2. Copy it to this directory: %CD%
        echo   3. Run this setup again
        echo.
    ) else if "!CHOICE!" == "2" (
        echo.
        echo Starting interactive setup...
        echo You'll need your server URL and bearer token from the admin.
        echo.
        pause
        python scripts\player_setup.py --interactive
    ) else (
        echo Invalid choice. Please run this setup again.
    )
)

echo.
echo Setup finished. Check above for any error messages.
echo.
pause