@echo off
REM Simple SoulLink Event Watcher Startup Script
echo Starting SoulLink Event Watcher...

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

REM Install requests if needed
echo Installing/updating required packages...
python -m pip install requests >nul 2>&1

REM Check if the server is running
echo Checking if SoulLink server is running...
python -c "import requests; requests.get('http://127.0.0.1:8000/health', timeout=5)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: SoulLink server is not running!
    echo Please start the server first using start_server.bat
    echo or run: python start_server.py
    pause
    exit /b 1
)

echo ✅ Server is running
echo.
echo Starting event watcher...
echo The watcher will auto-detect your OS and create the appropriate directory
echo.

REM Start the watcher
python simple_watcher.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo Watcher stopped with error. Check the messages above.
    pause
)