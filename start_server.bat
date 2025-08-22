@echo off
REM SoulLink Tracker Windows Startup Script
echo Starting SoulLink Tracker on Windows...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and add it to your PATH
    pause
    exit /b 1
)

REM Set the working directory to the script location
cd /d "%~dp0"

REM Check if we're in the right directory
if not exist "src\soullink_tracker" (
    echo ERROR: soullink_tracker source code not found
    echo Make sure you're running this from the project root directory
    echo Expected: src\soullink_tracker\
    pause
    exit /b 1
)

REM Install dependencies if requirements.txt exists
if exist "requirements.txt" (
    echo Installing Python dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo WARNING: Failed to install some dependencies
        echo You may need to install them manually
    )
)

REM Start the server
echo.
echo Starting SoulLink Tracker server...
python start_server.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo Server failed to start. Check the error messages above.
    pause
)