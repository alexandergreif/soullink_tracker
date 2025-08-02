@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM SoulLink Tracker - Player Distribution Script Launcher
REM Creates player packages after admin setup
REM ============================================================================

echo.
echo ========================================================
echo   SoulLink Tracker - Player Distribution
echo ========================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please run the windows_installer.bat first to install Python.
    echo.
    pause
    exit /b 1
)

REM Check if distribute players script exists
if not exist "scripts\distribute_players.py" (
    echo ERROR: Player distribution script not found
    echo.
    echo This script should be auto-generated after admin setup completes.
    echo Please run the admin setup first: run_admin_setup.bat
    echo.
    pause
    exit /b 1
)

REM Check if admin configuration exists
if not exist "admin_config.json" (
    echo ERROR: Admin configuration not found
    echo.
    echo Please run the admin setup first: run_admin_setup.bat
    echo The admin setup must complete successfully before distributing players.
    echo.
    pause
    exit /b 1
)

echo Creating player distribution packages...
echo.

python scripts\distribute_players.py

echo.
echo Distribution complete!
echo.
echo Check the 'player_packages' folder for ZIP files to send to each player.
echo Each player should receive their specific ZIP file.
echo.
pause