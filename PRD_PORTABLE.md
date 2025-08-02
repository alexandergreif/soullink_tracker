# Product Requirements Document: SoulLink Tracker Portable Edition

## Executive Summary

The SoulLink Tracker Portable Edition is a complete redesign focused on zero-installation deployment. Users download a single ZIP file, extract it, and run the application immediately without installing Python, dependencies, or configuring environments.

## Background & Problem Statement

### Current Issues
- Complex setup process (Python installation, pip dependencies, environment configuration)
- Platform-specific installation scripts and troubleshooting
- Dependency conflicts and version compatibility issues
- ~15 minute setup time per player
- Technical barriers preventing non-technical users from participating

### Solution Vision
**"Download, Extract, Run"** - A single executable that launches the complete SoulLink tracking system with zero external dependencies.

## Product Goals

### Primary Goals
1. **Zero Installation**: No Python, pip, or package management required
2. **Universal Compatibility**: Single download works on Windows 10+, macOS 10.15+, Linux x64
3. **Instant Setup**: <30 seconds from download to running application
4. **Self-Contained**: All dependencies, web UI, and data bundled in executable
5. **Simplified Distribution**: GitHub Releases with automated builds

### Secondary Goals
1. **Smaller Footprint**: Target <50MB download size per platform
2. **Better Performance**: Faster startup than interpreted Python
3. **Enhanced Security**: Code signing for trusted execution
4. **Auto-Updates**: Built-in update mechanism for new releases

## Architecture Overview

### New Simplified Stack
```
┌─────────────────────────────────────┐
│          Single Executable          │
├─────────────────────────────────────┤
│  Embedded Web UI (React/Vue SPA)    │
├─────────────────────────────────────┤
│     FastAPI Backend (Compiled)      │
├─────────────────────────────────────┤
│       SQLite Database (File)        │
├─────────────────────────────────────┤
│    Lua Scripts (File Resources)     │
└─────────────────────────────────────┘
```

### Deployment Strategy
- **Primary**: Nuitka compilation for optimal performance and size
- **Fallback**: PyInstaller for maximum compatibility
- **Distribution**: GitHub Releases with automated CI/CD

## Core Features

### 1. Unified Application Launcher
- Single executable starts web server and opens browser automatically
- Embedded web interface (no separate HTML files needed)
- Automatic port detection and localhost binding
- System tray integration for background operation

### 2. Simplified Configuration
```
soullink-tracker-v2.0.0/
├── soullink-tracker.exe          # Main executable
├── data/
│   ├── database.db              # SQLite database (created on first run)
│   ├── config.json              # Application settings
│   └── logs/                    # Application logs
├── lua-scripts/
│   ├── pokemon_tracker.lua      # DeSmuME script
│   ├── memory_addresses.lua     # Memory definitions
│   └── player_configs/          # Per-player Lua configs
├── README.md                    # Quick start guide
└── LICENSE
```

### 3. First-Run Experience
1. User extracts ZIP file
2. Runs executable
3. Application creates data directory and database
4. Browser opens to setup wizard
5. Setup wizard generates player tokens and Lua configs
6. Players copy Lua scripts to DeSmuME

### 4. Integrated Web Interface
- Embedded React/Vue SPA compiled into executable
- No separate web server or HTML files
- All assets bundled in binary
- Automatic browser launch with correct URL

### 5. Auto-Configuration System
- Automatic player token generation
- One-click Lua script generation for each player
- Pre-configured with sensible defaults
- Export configs for easy sharing

## Technical Implementation

### 1. Build System Architecture

#### Primary: Nuitka Compilation
```python
# build_nuitka.py
import subprocess
import sys

def build_portable():
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile", 
        "--include-data-dir=web=web",
        "--include-data-dir=lua-scripts=lua-scripts",
        "--include-data-dir=data=data",
        "--windows-console-mode=disable",  # GUI mode on Windows
        "--macos-app-bundle",  # macOS app bundle
        "--product-name=SoulLink Tracker",
        "--file-version=2.0.0",
        "--enable-plugin=anti-bloat",
        "--assume-yes-for-downloads",
        "src/main.py"
    ]
    subprocess.run(cmd, check=True)
```

#### Fallback: PyInstaller
```python
# build_pyinstaller.py
import PyInstaller.__main__

PyInstaller.__main__.run([
    '--onefile',
    '--windowed',
    '--add-data=web:web',
    '--add-data=lua-scripts:lua-scripts', 
    '--add-data=data:data',
    '--name=soullink-tracker',
    '--icon=assets/icon.ico',
    'src/main.py'
])
```

### 2. Embedded Web Interface

#### Option A: FastAPI + Embedded SPA
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import webbrowser
import uvicorn

app = FastAPI()

# Serve embedded React/Vue app
app.mount("/static", StaticFiles(directory="web/static"), name="static")

@app.get("/")
async def root():
    return FileResponse("web/index.html")

def start_server():
    # Find available port
    port = find_free_port(8000)
    
    # Start server in background thread
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    
    # Open browser
    webbrowser.open(f"http://127.0.0.1:{port}")
    
    # Run server
    server.run()
```

#### Option B: Pure Web Technologies (Electron-style)
```python
import webview

def create_window():
    # Create native window with embedded web content
    webview.create_window(
        'SoulLink Tracker',
        'web/index.html',
        width=1200,
        height=800,
        resizable=True,
        min_size=(800, 600)
    )
    webview.start(debug=False)
```

### 3. Resource Management
```python
import sys
from pathlib import Path

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller/Nuitka"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller bundle
        return Path(sys._MEIPASS) / relative_path
    elif hasattr(sys, 'frozen'):
        # Nuitka bundle
        return Path(sys.executable).parent / relative_path
    else:
        # Development
        return Path(__file__).parent / relative_path

# Usage
lua_scripts_dir = get_resource_path("lua-scripts")
web_assets_dir = get_resource_path("web")
```

### 4. Configuration Management
```python
# config.py
from pydantic import BaseSettings
from pathlib import Path
import json

class AppConfig(BaseSettings):
    app_name: str = "SoulLink Tracker"
    version: str = "2.0.0"
    port: int = 8000
    host: str = "127.0.0.1"
    data_dir: Path = Path("data")
    auto_open_browser: bool = True
    
    class Config:
        env_prefix = "SOULLINK_"

def load_config() -> AppConfig:
    config_file = Path("data/config.json")
    if config_file.exists():
        with open(config_file) as f:
            config_data = json.load(f)
        return AppConfig(**config_data)
    else:
        # Create default config
        config = AppConfig()
        save_config(config)
        return config

def save_config(config: AppConfig):
    config_file = Path("data/config.json")
    config_file.parent.mkdir(exist_ok=True)
    with open(config_file, 'w') as f:
        json.dump(config.dict(), f, indent=2, default=str)
```

## User Experience Flow

### Initial Download & Setup
1. **Download**: User downloads `soullink-tracker-v2.0.0-windows-x64.zip` (or appropriate platform)
2. **Extract**: Unzip to desired location (e.g., Desktop, Games folder)
3. **First Run**: Double-click `soullink-tracker.exe`
4. **Auto-Setup**: Application creates data directory, initializes database
5. **Browser Launch**: Default browser opens to `http://localhost:8000`
6. **Setup Wizard**: Web interface guides through initial configuration

### Setup Wizard Flow
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Welcome       │ -> │  Create Run     │ -> │  Add Players    │
│   - Overview    │    │  - Run Name     │    │  - Player Names │
│   - Quick Start │    │  - Game Rules   │    │  - Game Regions │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         v                       v                       v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Generate Tokens │ -> │ Export Scripts  │ -> │    Ready!       │
│ - Auto-generate │    │ - Download Lua  │    │ - Dashboard URL │
│ - Display codes │    │ - Setup Guide   │    │ - Next Steps    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Daily Usage
1. **Launch**: Double-click executable (or use desktop shortcut)
2. **Auto-Open**: Browser opens to dashboard automatically
3. **Play**: Players use DeSmuME with included Lua scripts
4. **Track**: Real-time updates appear in web dashboard
5. **Close**: Close browser tab, application continues in system tray

## Platform-Specific Considerations

### Windows 10/11
- **Executable**: `soullink-tracker.exe`
- **Code Signing**: Sign with certificate to avoid SmartScreen warnings
- **Installation**: No installation required, but optional desktop shortcut creation
- **Firewall**: Application may trigger Windows Firewall prompt for localhost binding

### macOS 10.15+
- **Application Bundle**: `SoulLink Tracker.app` 
- **Code Signing**: Sign with Apple Developer Certificate
- **Notarization**: Submit to Apple for notarization to avoid Gatekeeper warnings
- **Permissions**: May prompt for network access permissions

### Linux x64
- **Executable**: `soullink-tracker` (AppImage or binary)
- **Dependencies**: Fully static binary with no external dependencies
- **Desktop Integration**: Include `.desktop` file for application menu integration
- **Permissions**: Executable permission may need to be set after extraction

## Release & Distribution Strategy

### Automated Build Pipeline
```yaml
# .github/workflows/release.yml
name: Build and Release

on:
  push:
    tags: ['v*']

jobs:
  build:
    strategy:
      matrix:
        include:
          - os: windows-latest
            target: windows-x64
            ext: .exe
          - os: macos-latest  
            target: macos-x64
            ext: .app
          - os: ubuntu-latest
            target: linux-x64
            ext: ""
    
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install nuitka pyinstaller
          pip install -r requirements.txt
      
      - name: Build with Nuitka
        run: python build_nuitka.py
      
      - name: Package release
        run: |
          mkdir release
          cp -r dist/* release/
          cp README.md LICENSE release/
          
      - name: Create archive
        run: |
          cd release
          zip -r ../soullink-tracker-${{ github.ref_name }}-${{ matrix.target }}.zip *
      
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: soullink-tracker-${{ matrix.target }}
          path: soullink-tracker-${{ github.ref_name }}-${{ matrix.target }}.zip

  release:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: |
            **/*.zip
          generate_release_notes: true
```

### Release Assets
Each release will include:
- `soullink-tracker-v2.0.0-windows-x64.zip` (~40MB)
- `soullink-tracker-v2.0.0-macos-x64.zip` (~45MB)  
- `soullink-tracker-v2.0.0-linux-x64.zip` (~35MB)
- `checksums.txt` (SHA256 hashes)
- Auto-generated release notes

## Success Metrics

### Technical Metrics
- **Download Size**: <50MB per platform
- **Startup Time**: <5 seconds from executable launch to browser opening
- **Memory Usage**: <100MB RAM during normal operation
- **Setup Time**: <30 seconds from download to working application

### User Experience Metrics
- **Setup Success Rate**: >95% successful first-time setups
- **User Feedback**: Positive feedback on ease of installation
- **Support Tickets**: <10% of downloads require support
- **Adoption Rate**: 3x increase in user adoption vs current version

## Implementation Timeline

### Phase 1: Core Portable Architecture (2 weeks)
- Set up Nuitka/PyInstaller build system
- Create unified executable with embedded web UI
- Implement resource management and configuration system
- Basic functionality testing across platforms

### Phase 2: User Experience Polish (1 week)  
- Design and implement setup wizard
- Auto-browser launching and port detection
- System tray integration and proper shutdown
- Error handling and user feedback

### Phase 3: Release Infrastructure (1 week)
- GitHub Actions build pipeline
- Code signing for Windows and macOS
- Automated testing and quality assurance
- Documentation and quick start guides

### Phase 4: Testing & Launch (1 week)
- Cross-platform testing
- User acceptance testing
- Performance optimization
- Official release and announcement

## Risk Assessment

### High Risk
- **Build Complexity**: Nuitka/PyInstaller may have compatibility issues with FastAPI
  - *Mitigation*: Test early, have PyInstaller fallback ready
- **Platform Differences**: Resource paths and permissions vary across OS
  - *Mitigation*: Extensive cross-platform testing, platform-specific builds

### Medium Risk  
- **File Size**: Bundled application may exceed size targets
  - *Mitigation*: Optimize dependencies, use UPX compression
- **Code Signing**: Certificate acquisition and signing process complexity
  - *Mitigation*: Start certificate process early, use GitHub secrets

### Low Risk
- **User Adoption**: Users may prefer familiar installation process
  - *Mitigation*: Provide both portable and traditional installation options
- **Performance**: Compiled version may have different performance characteristics
  - *Mitigation*: Performance testing and optimization in Phase 4

## Future Enhancements

### Version 2.1
- **Auto-Updates**: Built-in update mechanism
- **Themes**: Dark/light mode support
- **Advanced Config**: More customization options in UI

### Version 2.2
- **Cloud Sync**: Optional cloud backup of runs and configurations
- **Mobile App**: Companion mobile app for remote monitoring
- **Plugin System**: Support for community-created extensions

## Conclusion

The SoulLink Tracker Portable Edition represents a fundamental shift toward accessibility and ease of use. By eliminating installation complexity and providing a "download and run" experience, we can significantly expand the user base while maintaining all the powerful features of the current system.

The portable approach aligns with modern software distribution trends and user expectations for friction-free software experiences. Success in this project will establish a foundation for future enhancements and broader community adoption.