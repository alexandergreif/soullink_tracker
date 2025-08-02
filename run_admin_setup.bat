@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM SoulLink Tracker - Admin Setup Launcher  
REM Simple double-click launcher for the admin setup script
REM ============================================================================

echo.
echo ========================================================
echo   SoulLink Tracker - Admin Setup
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

REM Check if admin setup script exists
if not exist "scripts\admin_setup.py" (
    echo ERROR: Admin setup script not found
    echo.
    echo Expected location: scripts\admin_setup.py
    echo Current directory: %CD%
    echo.
    echo Please make sure you're running this from the SoulLink Tracker directory
    echo and that all files have been extracted properly.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python !PYTHON_VERSION! found. Starting admin setup...
echo.

echo Choose setup mode:
echo   1. Development mode (local testing only)
echo   2. Production mode (with external tunnel for remote players)
echo   3. Reset configuration and start fresh
echo.
set /p CHOICE=Enter your choice (1-3): 

if "!CHOICE!" == "1" (
    echo.
    echo Starting development mode setup...
    echo This will run the server locally only (no external access)
    echo.
    python scripts\admin_setup.py --dev
) else if "!CHOICE!" == "2" (
    echo.
    echo Starting production mode setup...
    echo This will set up external tunnel for remote player access
    echo.
    python scripts\admin_setup.py --production
) else if "!CHOICE!" == "3" (
    echo.
    echo Resetting configuration and starting fresh...
    echo This will clear all previous data and settings
    echo.
    set /p CONFIRM=Are you sure? This will delete all existing data (y/n): 
    if /i "!CONFIRM!" == "y" (
        python scripts\admin_setup.py --reset --production
    ) else (
        echo Reset cancelled.
    )
) else (
    echo Invalid choice. Please run this setup again and choose 1, 2, or 3.
    goto :end
)

echo.
echo Admin setup finished. Check above for any error messages.
echo.
echo If setup was successful, you should now:
echo   1. Run: python scripts\distribute_players.py
echo   2. Send the player packages to each player
echo   3. Monitor the dashboard for activity
echo.

:end
pause