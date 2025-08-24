@echo off
REM setup_player.bat - Enhanced Windows setup helper for SoulLink Tracker
REM This script helps generate Lua configuration with full validation

echo ===============================================
echo   SoulLink Tracker - Player Setup (Enhanced)
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

echo ✅ Python is available
echo.

REM Check if validation tools exist
if not exist "validate_pipeline_config.py" (
    echo WARNING: Config validation tool not found
    echo Some validation checks will be skipped.
    echo.
)

if not exist "diagnose_pipeline.py" (
    echo WARNING: Pipeline diagnostic tool not found
    echo Advanced diagnostics will be skipped.
    echo.
)

REM Pre-setup validation
echo 🔍 Running pre-setup checks...
echo.

REM Check if database exists
if not exist "soullink_tracker.db" (
    echo ❌ Database not found!
    echo.
    echo The server needs to be started at least once to create the database.
    echo Please run: python start_server.py
    echo.
    set SETUP_ISSUES=1
) else (
    echo ✅ Database found
)

REM Check if server is running
echo Checking if server is running...
curl -s http://127.0.0.1:8000/v1/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ Server is running and accessible
    set SERVER_RUNNING=1
) else (
    echo ⚠️  Server not responding at http://127.0.0.1:8000
    echo    You may need to start it: python start_server.py
    set SERVER_RUNNING=0
)

REM Check required directories
if not exist "client\lua" (
    echo ❌ Lua directory not found: client\lua
    set SETUP_ISSUES=1
) else (
    echo ✅ Lua directory found
)

if not exist "client\lua\pokemon_tracker_v3_fixed.lua" (
    echo ❌ Main Lua script not found: client\lua\pokemon_tracker_v3_fixed.lua
    set SETUP_ISSUES=1
) else (
    echo ✅ Lua tracker script found
)

echo.

REM Report pre-setup issues
if defined SETUP_ISSUES (
    echo ❌ SETUP ISSUES DETECTED
    echo.
    echo Please fix the above issues before continuing.
    echo Common fixes:
    echo   1. Run: python start_server.py
    echo   2. Check that you're in the correct project directory
    echo   3. Ensure all project files are present
    echo.
    pause
    exit /b 1
)

echo ✅ Pre-setup checks passed!
echo.

REM Run the configuration generator in interactive mode
echo 🎮 Starting configuration wizard...
echo.
python generate_lua_config.py --interactive

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===============================================
    echo   Configuration Generated - Running Validation
    echo ===============================================
    echo.
    echo ✅ Configuration file created successfully!
    echo.
    
    REM Run post-setup validation
    echo 🔍 Validating configuration...
    echo.
    
    if exist "validate_pipeline_config.py" (
        python validate_pipeline_config.py --quiet
        if %ERRORLEVEL% EQU 0 (
            echo ✅ Configuration validation passed!
        ) else if %ERRORLEVEL% EQU 2 (
            echo ⚠️  Configuration validation passed with warnings
            echo    Run: python validate_pipeline_config.py
            echo    to see details.
        ) else (
            echo ❌ Configuration validation failed!
            echo.
            echo Running detailed validation...
            python validate_pipeline_config.py
            echo.
            echo Please fix the above issues before continuing.
            pause
            exit /b 1
        )
    ) else (
        echo ⚠️  Validation tool not available - skipping detailed checks
    )
    
    echo.
    echo 🔧 Testing component integration...
    
    REM Test that all components can work together
    if exist "diagnose_pipeline.py" (
        python diagnose_pipeline.py --component integration --quiet
        if %ERRORLEVEL% EQU 0 (
            echo ✅ Integration test passed!
        ) else (
            echo ⚠️  Integration test found issues
            echo    Run: python diagnose_pipeline.py
            echo    for full diagnostic report.
        )
    )
    
    echo.
    echo ===============================================
    echo   Setup Complete!
    echo ===============================================
    echo.
    echo 🎉 Your SoulLink Tracker is ready to use!
    echo.
    echo NEXT STEPS:
    echo   1. Open DeSmuME emulator
    echo   2. Load your Pokemon HeartGold/SoulSilver ROM
    echo   3. Go to Tools -^> Lua Scripting -^> New Lua Script Window
    echo   4. Browse to: client\lua\pokemon_tracker_v3_fixed.lua
    echo   5. Click Run to start tracking!
    echo.
    echo ADDITIONAL STEPS:
    echo   - Start the watcher: python simple_watcher.py
    echo   - Open dashboard: http://127.0.0.1:8000
    echo.
    echo TROUBLESHOOTING:
    echo   - Full diagnostic: python diagnose_pipeline.py
    echo   - Validate config: python validate_pipeline_config.py
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
    echo 🔍 Running diagnostic to identify issues...
    echo.
    
    if exist "diagnose_pipeline.py" (
        python diagnose_pipeline.py --quiet
        echo.
        echo For detailed diagnostic report, run:
        echo   python diagnose_pipeline.py
    ) else (
        echo Diagnostic tool not available.
        echo.
        echo Please check the error messages above.
        echo.
        echo Common issues:
        echo   1. Server not running - Start with: python start_server.py
        echo   2. No runs created - Use admin panel at http://127.0.0.1:8000/admin
        echo   3. Database locked - Close other applications using the database
    )
    echo.
    pause
    exit /b 1
)