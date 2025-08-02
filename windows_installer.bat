@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM SoulLink Tracker - Windows All-in-One Installer
REM This script automatically installs Python and all required dependencies
REM ============================================================================

echo.
echo ========================================================
echo   SoulLink Tracker - Windows Installer
echo ========================================================
echo.
echo This installer will:
echo   - Check if Python is installed
echo   - Install Python 3.11 if needed
echo   - Install all required packages
echo   - Set up the SoulLink Tracker client
echo.
pause

REM Create logs directory
if not exist "logs" mkdir logs

REM Log file for installation
set LOGFILE=logs\windows_install.log
echo [%date% %time%] Starting Windows installation > "%LOGFILE%"

echo Checking system requirements...
echo [%date% %time%] Checking system requirements >> "%LOGFILE%"

REM Check if running on Windows
ver | findstr /i "Windows" >nul
if %errorlevel% neq 0 (
    echo ERROR: This installer is only for Windows systems.
    echo [%date% %time%] ERROR: Not running on Windows >> "%LOGFILE%"
    pause
    exit /b 1
)

REM Check Windows version (Windows 10/11 recommended)
for /f "tokens=3" %%i in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v ProductName 2^>nul') do set WINVER=%%i
echo Detected Windows version: %WINVER%
echo [%date% %time%] Windows version: %WINVER% >> "%LOGFILE%"

REM Check for admin privileges (optional but recommended)
net session >nul 2>&1
if %errorlevel% equ 0 (
    echo Running with administrator privileges (recommended)
    echo [%date% %time%] Running with admin privileges >> "%LOGFILE%"
) else (
    echo WARNING: Not running as administrator
    echo Some features may not work correctly
    echo [%date% %time%] WARNING: No admin privileges >> "%LOGFILE%"
    echo.
    echo You can continue, but if you encounter issues, try:
    echo "Right-click this file and select 'Run as administrator'"
    echo.
    pause
)

echo.
echo ========================================================
echo   Step 1: Checking Python Installation
echo ========================================================

REM Check if Python is installed and get version
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo Found Python !PYTHON_VERSION!
    echo [%date% %time%] Found Python !PYTHON_VERSION! >> "%LOGFILE%"
    
    REM Check if version is 3.8 or higher
    for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
        set MAJOR=%%a
        set MINOR=%%b
    )
    
    if !MAJOR! gtr 3 (
        set PYTHON_OK=1
    ) else if !MAJOR! equ 3 (
        if !MINOR! geq 8 (
            set PYTHON_OK=1
        ) else (
            set PYTHON_OK=0
        )
    ) else (
        set PYTHON_OK=0
    )
    
    if !PYTHON_OK! equ 1 (
        echo Python version is compatible (3.8+ required)
        echo [%date% %time%] Python version compatible >> "%LOGFILE%"
        goto :install_packages
    ) else (
        echo ERROR: Python version !PYTHON_VERSION! is too old
        echo Python 3.8 or higher is required
        echo [%date% %time%] ERROR: Python version too old >> "%LOGFILE%"
        goto :install_python
    )
) else (
    echo Python not found on system
    echo [%date% %time%] Python not found >> "%LOGFILE%"
    goto :install_python
)

:install_python
echo.
echo ========================================================
echo   Step 2: Installing Python 3.11
echo ========================================================
echo.
echo Python is not installed or version is too old.
echo This installer will download and install Python 3.11 for you.
echo.
echo The download is approximately 25MB and may take a few minutes.
echo.
set /p CONFIRM=Do you want to continue? (y/n): 
if /i "!CONFIRM!" neq "y" (
    echo Installation cancelled by user
    echo [%date% %time%] Installation cancelled by user >> "%LOGFILE%"
    pause
    exit /b 1
)

echo.
echo Downloading Python 3.11 installer...
echo [%date% %time%] Downloading Python installer >> "%LOGFILE%"

REM Download Python 3.11 installer
set PYTHON_URL=https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe
set PYTHON_INSTALLER=python-3.11.8-installer.exe

REM Use PowerShell to download (available on Windows 7+)
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'}"

if not exist "%PYTHON_INSTALLER%" (
    echo ERROR: Failed to download Python installer
    echo [%date% %time%] ERROR: Failed to download Python >> "%LOGFILE%"
    echo.
    echo Please try:
    echo 1. Check your internet connection
    echo 2. Download Python manually from https://python.org
    echo 3. Run this installer again
    pause
    exit /b 1
)

echo Download complete. Installing Python...
echo [%date% %time%] Installing Python >> "%LOGFILE%"

REM Install Python silently with pip and add to PATH
echo This may take several minutes...
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0

REM Wait for installation to complete
timeout /t 10 /nobreak >nul

REM Clean up installer
del "%PYTHON_INSTALLER%" >nul 2>&1

REM Refresh PATH environment variable
call refreshenv >nul 2>&1 || (
    echo Refreshing environment variables...
    REM Manual PATH refresh for older systems
    for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USER_PATH=%%b"
    for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SYSTEM_PATH=%%b"
    set "PATH=%SYSTEM_PATH%;%USER_PATH%"
)

REM Verify Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python installation failed or PATH not updated
    echo [%date% %time%] ERROR: Python installation verification failed >> "%LOGFILE%"
    echo.
    echo Please try:
    echo 1. Restart this command prompt and run the installer again
    echo 2. Restart your computer and try again
    echo 3. Install Python manually from https://python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python !PYTHON_VERSION! installed successfully!
echo [%date% %time%] Python !PYTHON_VERSION! installed successfully >> "%LOGFILE%"

:install_packages
echo.
echo ========================================================
echo   Step 3: Installing Required Python Packages
echo ========================================================
echo.
echo Installing packages required for SoulLink Tracker...
echo [%date% %time%] Installing required packages >> "%LOGFILE%"

REM Upgrade pip first
echo Upgrading pip...
python -m pip install --upgrade pip >> "%LOGFILE%" 2>&1

REM Install required packages
echo Installing aiohttp...
python -m pip install "aiohttp>=3.8.0" >> "%LOGFILE%" 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Failed to install aiohttp
    echo [%date% %time%] WARNING: Failed to install aiohttp >> "%LOGFILE%"
)

echo Installing requests...
python -m pip install "requests>=2.28.0" >> "%LOGFILE%" 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Failed to install requests
    echo [%date% %time%] WARNING: Failed to install requests >> "%LOGFILE%"
)

echo Installing watchdog...
python -m pip install "watchdog>=2.1.0" >> "%LOGFILE%" 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Failed to install watchdog
    echo [%date% %time%] WARNING: Failed to install watchdog >> "%LOGFILE%"
)

echo Installing aiofiles...
python -m pip install "aiofiles>=0.8.0" >> "%LOGFILE%" 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Failed to install aiofiles
    echo [%date% %time%] WARNING: Failed to install aiofiles >> "%LOGFILE%"
)

echo Installing pydantic...
python -m pip install "pydantic>=1.10.0" >> "%LOGFILE%" 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Failed to install pydantic
    echo [%date% %time%] WARNING: Failed to install pydantic >> "%LOGFILE%"
)

echo.
echo Verifying package installation...
echo [%date% %time%] Verifying package installation >> "%LOGFILE%"

REM Verify packages are installed
python -c "import aiohttp, requests, watchdog, aiofiles, pydantic; print('All packages installed successfully')" 2>nul
if %errorlevel% equ 0 (
    echo All required packages installed successfully!
    echo [%date% %time%] All packages verified >> "%LOGFILE%"
) else (
    echo WARNING: Some packages may not have installed correctly
    echo [%date% %time%] WARNING: Package verification failed >> "%LOGFILE%"
    echo Check the log file for details: %LOGFILE%
)

echo.
echo ========================================================
echo   Step 4: Setting Up SoulLink Tracker
echo ========================================================

REM Create necessary directories
echo Creating directories...
if not exist "temp" mkdir temp
if not exist "temp\events" mkdir "temp\events"
if not exist "client" mkdir client
if not exist "client\watcher" mkdir "client\watcher"
if not exist "client\watcher\configs" mkdir "client\watcher\configs"
if not exist "client\lua" mkdir "client\lua"
if not exist "client\lua\configs" mkdir "client\lua\configs"

echo [%date% %time%] Created directory structure >> "%LOGFILE%"

REM Create desktop shortcuts
echo Creating desktop shortcuts...

REM Create shortcut for player setup
set DESKTOP=%USERPROFILE%\Desktop
echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%DESKTOP%\SoulLink Player Setup.lnk" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "%CD%\run_player_setup.bat" >> CreateShortcut.vbs
echo oLink.WorkingDirectory = "%CD%" >> CreateShortcut.vbs
echo oLink.Description = "SoulLink Tracker Player Setup" >> CreateShortcut.vbs
echo oLink.IconLocation = "shell32.dll,21" >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs
cscript CreateShortcut.vbs >nul 2>&1
del CreateShortcut.vbs >nul 2>&1

echo [%date% %time%] Created desktop shortcuts >> "%LOGFILE%"

echo.
echo ========================================================
echo   Installation Complete!
echo ========================================================
echo.
echo SoulLink Tracker has been successfully installed!
echo [%date% %time%] Installation completed successfully >> "%LOGFILE%"
echo.
echo What was installed:
echo   - Python !PYTHON_VERSION!
echo   - All required Python packages
echo   - SoulLink Tracker directory structure
echo   - Desktop shortcuts
echo.
echo Next steps:
echo   1. Get your player configuration file from the admin
echo   2. Double-click "SoulLink Player Setup" on your desktop
echo   3. Follow the setup instructions
echo   4. Download and install DeSmuME emulator separately
echo.
echo Files created:
echo   - Desktop shortcut: "SoulLink Player Setup"
echo   - Installation log: %LOGFILE%
echo.
echo For troubleshooting, check the log file or contact your admin.
echo.
pause

endlocal
echo [%date% %time%] Installer finished >> "%LOGFILE%"