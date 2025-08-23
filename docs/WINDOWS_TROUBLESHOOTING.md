# Windows Troubleshooting Guide for SoulLink Tracker

## Common Windows Issues and Solutions

### 1. File Path Issues

#### Problem: "File not found" or "Invalid path" errors
**Symptoms:**
- Lua scripts can't write event files
- Watcher can't find event files
- Configuration files not loading

**Solutions:**
1. **Use forward slashes in paths:** Windows accepts both `/` and `\`, but forward slashes work everywhere
   ```json
   // Good
   "spool_dir": "C:/temp/soullink_events"
   
   // Also works but less portable
   "spool_dir": "C:\\temp\\soullink_events"
   ```

2. **Avoid spaces in paths:** If you must use spaces, ensure proper quoting
   ```json
   // Avoid
   "spool_dir": "C:/Program Files/soullink"
   
   // Better
   "spool_dir": "C:/ProgramData/SoulLink"
   ```

3. **Check directory permissions:** Ensure the application can write to the spool directory
   ```powershell
   # Create directory with proper permissions
   mkdir C:\temp\soullink_events
   icacls C:\temp\soullink_events /grant Users:F
   ```

### 2. DeSmuME Lua Script Issues

#### Problem: Lua script doesn't create event files
**Solutions:**
1. **Check Lua output directory exists:**
   ```lua
   -- In config.lua, ensure path exists
   SPOOL_DIR = "C:/temp/soullink_events/"
   ```

2. **Verify DeSmuME can write files:**
   - Run DeSmuME as Administrator (not recommended for regular use)
   - Or ensure the spool directory has write permissions for all users

3. **Enable debug logging in Lua:**
   ```lua
   DEBUG = true  -- Enable verbose logging
   ```

### 3. Python Watcher Issues

#### Problem: Watcher doesn't detect new files
**Solutions:**
1. **Check the watch directory matches Lua config:**
   ```python
   # In simple_watcher.py or config
   CONFIG['watch_directory'] = 'C:/temp/soullink_events'  # Must match Lua SPOOL_DIR
   ```

2. **Run with debug mode:**
   ```bash
   python simple_watcher.py --debug
   ```

3. **Check Windows Defender/Antivirus:**
   - Add exception for the soullink directories
   - Temporary disable real-time protection to test

### 4. Network/API Connection Issues

#### Problem: "Connection refused" or timeout errors
**Solutions:**
1. **Check Windows Firewall:**
   ```powershell
   # Allow Python through firewall
   netsh advfirewall firewall add rule name="Python SoulLink" dir=in action=allow program="C:\Python39\python.exe" enable=yes
   ```

2. **Verify server is running:**
   ```bash
   # Check if port 8000 is listening
   netstat -an | findstr :8000
   ```

3. **Use localhost instead of 127.0.0.1:**
   Some Windows configurations handle localhost differently

### 5. Portable Build Issues

#### Problem: Executable doesn't run or crashes immediately
**Solutions:**
1. **Check Visual C++ Redistributables:**
   - Install Microsoft Visual C++ Redistributable (2015-2022)
   - Download from Microsoft website

2. **Run from Command Prompt to see errors:**
   ```cmd
   cd C:\path\to\soullink
   soullink_portable.exe --debug
   ```

3. **Check for missing dependencies:**
   ```cmd
   # Will show DLL errors if any
   soullink_portable.exe
   ```

### 6. Permission Issues

#### Problem: "Access denied" errors
**Solutions:**
1. **Don't install in Program Files:**
   ```
   # Bad
   C:\Program Files\SoulLink\
   
   # Good
   C:\SoulLink\
   C:\Users\%USERNAME%\SoulLink\
   ```

2. **Run as regular user (not Administrator):**
   - Administrator mode can cause path resolution issues
   - Only use if absolutely necessary

3. **Check folder ownership:**
   ```powershell
   # Take ownership of folder
   takeown /f C:\SoulLink /r /d y
   icacls C:\SoulLink /grant %USERNAME%:F /t
   ```

## Windows-Specific Configuration

### Recommended Directory Structure
```
C:\SoulLink\
├── soullink_portable.exe
├── data\
│   ├── config.json
│   ├── routes.csv
│   └── species.csv
├── web\
│   └── (web files)
└── temp\
    └── soullink_events\  (Lua output directory)
```

### Environment Variables (Optional)
```cmd
# Set in System Properties > Environment Variables
SOULLINK_PORTABLE=1
SOULLINK_DATA_DIR=C:\SoulLink\data
SOULLINK_WEB_DIR=C:\SoulLink\web
SOULLINK_DEBUG=1  # For troubleshooting
```

### Windows Service Setup (Advanced)
To run as a Windows service:
1. Install NSSM (Non-Sucking Service Manager)
2. Create service:
   ```cmd
   nssm install SoulLinkTracker C:\SoulLink\soullink_portable.exe
   nssm set SoulLinkTracker AppDirectory C:\SoulLink
   nssm start SoulLinkTracker
   ```

## Diagnostic Commands

### Check Python Installation
```cmd
python --version
pip --version
```

### Test Network Connectivity
```cmd
# Test local server
curl http://127.0.0.1:8000/docs
# or
powershell -Command "Invoke-WebRequest http://127.0.0.1:8000/docs"
```

### Check File Permissions
```powershell
Get-Acl C:\temp\soullink_events | Format-List
```

### Monitor File Creation
```powershell
# Watch for new files in PowerShell
Get-ChildItem C:\temp\soullink_events -File | 
    Where-Object {$_.LastWriteTime -gt (Get-Date).AddMinutes(-5)}
```

## Getting Help

If issues persist:
1. Run with `--debug` flag for verbose output
2. Check logs in `%TEMP%\soullink_logs\`
3. Verify all paths use forward slashes or escaped backslashes
4. Ensure no antivirus is blocking file operations
5. Try running from a simple path like `C:\SoulLink\`

### Log Locations
- Application logs: `C:\SoulLink\logs\` or `%TEMP%\soullink_logs\`
- DeSmuME Lua output: Check DeSmuME console window
- Windows Event Viewer: Check Application logs for Python errors

## Quick Checklist

Before reporting issues, verify:
- [ ] All paths use forward slashes or properly escaped backslashes
- [ ] Spool directory exists and is writable
- [ ] No antivirus/Windows Defender blocking operations
- [ ] Server is running on port 8000
- [ ] Lua config matches watcher config for paths
- [ ] Running from a path without spaces or special characters
- [ ] Not running as Administrator (unless required)
- [ ] Visual C++ Redistributables installed (for portable build)