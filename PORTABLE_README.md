# SoulLink Tracker Portable Edition 🔗

## Quick Start (Portable Version)

### ⚡ Super Fast Setup (30 seconds)

1. **Download** the latest release for your platform:
   - [Windows](https://github.com/alex/soullink-tracker/releases/latest) - `soullink-tracker-vX.X.X-windows-x64.zip`
   - [macOS](https://github.com/alex/soullink-tracker/releases/latest) - `soullink-tracker-vX.X.X-macos-x64.zip`
   - [Linux](https://github.com/alex/soullink-tracker/releases/latest) - `soullink-tracker-vX.X.X-linux-x64.zip`

2. **Extract** the ZIP file to any folder (e.g., Desktop, Games folder)

3. **Run** the executable:
   - **Windows**: Double-click `soullink-tracker.exe`
   - **macOS**: Double-click `SoulLink Tracker.app`
   - **Linux**: Run `./soullink-tracker` in terminal

4. **Browser opens automatically** → Follow the setup wizard → Done! 🎉

### ✨ No Installation Required!
- ❌ No Python installation
- ❌ No pip dependencies
- ❌ No environment setup
- ❌ No configuration files
- ✅ Just download and run!

---

## Portable vs Traditional Installation

| Feature | Portable Edition | Traditional Installation |
|---------|------------------|--------------------------|
| **Setup Time** | 30 seconds | 15+ minutes |
| **Prerequisites** | None | Python 3.9+, pip, git |
| **File Size** | ~45MB download | Variable (dependencies) |
| **Updates** | Download new version | Git pull + pip install |
| **Portability** | Run from any folder | Tied to installation path |
| **Troubleshooting** | Minimal (self-contained) | Complex (dependencies) |

---

## How It Works

The portable edition uses [PyInstaller](https://pyinstaller.org/) to bundle:
- ✅ Python interpreter and all dependencies
- ✅ FastAPI backend and web interface
- ✅ SQLite database engine
- ✅ Lua scripts and data files
- ✅ Auto-configuration system

Into a single executable that runs on any compatible system.

---

## Features

### 🚀 Auto-Everything
- **Auto-port detection** - Finds available port (8000-8010)
- **Auto-browser launch** - Opens dashboard automatically
- **Auto-configuration** - Sensible defaults, no setup needed
- **Auto-resource detection** - Works in any folder

### 🎯 Built-in Setup Wizard
- **Player management** - Add/remove players with one click
- **Token generation** - Automatic secure token creation
- **Lua config export** - Download ready-to-use DeSmuME scripts
- **Real-time testing** - Verify setup before playing

### 🔒 Self-Contained
- **No external dependencies** - Everything bundled
- **No registry changes** - Portable installation
- **No admin rights required** - User-level execution
- **No internet required** - Works offline after download

---

## System Requirements

### Minimum Requirements
- **Memory**: 512MB RAM
- **Storage**: 100MB free space
- **Network**: None (offline capable)

### Supported Platforms
- **Windows**: Windows 10+ (64-bit)
- **macOS**: macOS 10.15+ (Intel and Apple Silicon)
- **Linux**: Any modern 64-bit distribution

---

## Usage

### First Time Setup
1. Run the portable executable
2. Browser opens to setup wizard
3. Create a new SoulLink run
4. Add players (names and game regions)
5. Export Lua scripts for each player
6. Give each player their Lua script
7. Start playing!

### Daily Usage
1. Run executable (double-click)
2. Browser opens to dashboard
3. Players load their Lua scripts in DeSmuME
4. Real-time tracking appears in dashboard
5. Close browser when done (app runs in system tray)

### File Organization
```
📁 soullink-tracker-portable/
├── 🚀 soullink-tracker.exe      # Main executable (Windows)
├── 🚀 SoulLink Tracker.app      # App bundle (macOS)  
├── 🚀 soullink-tracker          # Binary (Linux)
├── 📄 README.md                 # Documentation
├── 📄 LICENSE                   # License file
├── 📄 QUICK_START.txt           # Quick reference
└── 📁 data/                     # Auto-created on first run
    ├── config.json              # Application settings
    ├── soullink_tracker.db      # SQLite database
    └── logs/                    # Application logs
```

---

## Advanced Usage

### Command Line Options
The portable version supports several command line options:

```bash
# Windows
soullink-tracker.exe --help

# macOS (from terminal)
./SoulLink\ Tracker.app/Contents/MacOS/SoulLink\ Tracker --help

# Linux
./soullink-tracker --help
```

### Environment Variables
```bash
SOULLINK_DEBUG=1           # Enable debug logging
SOULLINK_PORT=8080         # Force specific port
SOULLINK_NO_BROWSER=1      # Don't auto-open browser
SOULLINK_NO_TRAY=1         # Disable system tray
```

### Data Directory
By default, the portable version creates a `data/` folder in the same directory as the executable. You can move this folder to preserve your runs between updates.

---

## Troubleshooting

### Common Issues

**🔴 "Application can't be opened" (macOS)**
```bash
# Remove quarantine flag
xattr -d com.apple.quarantine "SoulLink Tracker.app"
```

**🔴 "Windows protected your PC" (Windows)**
- Click "More info" → "Run anyway"
- This happens because the executable isn't code-signed

**🔴 Port already in use**
- The app automatically finds an available port
- If all ports 8000-8010 are busy, close other applications

**🔴 Browser doesn't open**
- Manually open: `http://localhost:8000`
- Check your default browser settings

### Debug Mode
Enable debug logging for troubleshooting:
```bash
# Set environment variable before running
export SOULLINK_DEBUG=1
./soullink-tracker
```

Check `data/logs/` for detailed log files.

---

## Updates

### Updating to New Version
1. Download new version
2. Extract to new folder (or replace old files)
3. Copy `data/` folder from old version (to preserve runs)
4. Run new version

### Migrating from Traditional Installation
1. Export your runs from the traditional version
2. Download portable version
3. Import runs through the web interface
4. Remove traditional installation if desired

---

## Security

### Code Signing
- **Windows**: Currently not code-signed (triggers SmartScreen)
- **macOS**: Currently not code-signed (requires "Open anyway")
- **Linux**: No code signing needed

### Verification
Each release includes SHA256 checksums:
```bash
# Verify download integrity
sha256sum soullink-tracker-v2.0.0-linux-x64.zip
# Compare with published checksum
```

### Privacy
- No telemetry or data collection
- No internet required after download
- All data stored locally in `data/` folder

---

## Development

### Building from Source
```bash
# Clone repository
git clone https://github.com/alex/soullink-tracker
cd soullink-tracker

# Install build dependencies
pip install pyinstaller
pip install -r requirements.txt

# Build portable version
python build/build_pyinstaller.py

# Find executable in dist/ folder
```

### Testing
```bash
# Test portable components
python test_portable.py

# Test build system  
python build/build_pyinstaller.py --spec-only
```

---

## Support

- 📖 **Documentation**: [Full README](README.md)
- 🐛 **Issues**: [GitHub Issues](https://github.com/alex/soullink-tracker/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/alex/soullink-tracker/discussions)
- 📧 **Contact**: [Project Maintainer](mailto:alex@example.com)

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Enjoy your SoulLink runs! 🔗🎮**