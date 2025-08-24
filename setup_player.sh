#!/bin/bash
# setup_player.sh - Unix/Linux/Mac setup helper for SoulLink Tracker
# This script helps generate Lua configuration using the interactive wizard

echo "==============================================="
echo "   SoulLink Tracker - Player Setup"
echo "==============================================="
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "ERROR: Python is not installed!"
    echo
    echo "Please install Python 3.8+ using your package manager:"
    echo "  Ubuntu/Debian: sudo apt install python3"
    echo "  macOS: brew install python3"
    echo "  Fedora: sudo dnf install python3"
    echo
    exit 1
fi

# Determine Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to check Python version"
    exit 1
fi

echo "Using Python $PYTHON_VERSION"
echo

# Check if database exists
if [ ! -f "soullink_tracker.db" ]; then
    echo "WARNING: Database not found!"
    echo
    echo "The server needs to be started at least once to create the database."
    echo "Run: $PYTHON_CMD start_server.py"
    echo
    read -p "Press Enter to continue anyway..."
fi

# Run the configuration generator in interactive mode
echo "Starting configuration wizard..."
echo
$PYTHON_CMD generate_lua_config.py --interactive

if [ $? -eq 0 ]; then
    echo
    echo "==============================================="
    echo "   Setup Complete!"
    echo "==============================================="
    echo
    echo "✅ Configuration file created successfully!"
    echo
    echo "Next steps:"
    echo "  1. Open DeSmuME emulator"
    echo "  2. Load your Pokemon HeartGold/SoulSilver ROM"
    echo "  3. Go to Tools -> Lua Scripting -> New Lua Script Window"
    echo "  4. Browse to: client/lua/pokemon_tracker_v3_fixed.lua"
    echo "  5. Click Run to start tracking!"
    echo
    echo "Additional steps:"
    echo "  - Start the watcher: $PYTHON_CMD simple_watcher.py"
    echo "  - Open dashboard: http://127.0.0.1:8000"
    echo
    read -p "Press Enter to exit..."
else
    echo
    echo "==============================================="
    echo "   Setup Failed"
    echo "==============================================="
    echo
    echo "❌ Configuration generation failed."
    echo
    echo "Please check the error messages above."
    echo
    echo "Common issues:"
    echo "  1. Server not running - Start with: $PYTHON_CMD start_server.py"
    echo "  2. No runs created - Use admin panel at http://127.0.0.1:8000/admin"
    echo "  3. Database locked - Close other applications using the database"
    echo
    read -p "Press Enter to exit..."
    exit 1
fi