# SoulLink Tracker - Troubleshooting Guide

This comprehensive guide helps you diagnose and fix common issues with the SoulLink Tracker pipeline.

## Quick Diagnostic Tools

### 🔧 New Diagnostic Commands

Before following manual troubleshooting steps, try these automated tools:

```bash
# Full pipeline diagnostic (recommended first step)
python diagnose_pipeline.py

# Validate your configuration
python validate_pipeline_config.py

# Test specific components
python diagnose_pipeline.py --component api
python diagnose_pipeline.py --component database
python diagnose_pipeline.py --component lua

# Enhanced setup with validation
setup_player.bat  # Windows
./setup_player.sh # Linux/Mac
```

---

## Common Issues by Component

### 🗂️ Configuration Issues

#### Problem: "Config file not found" or "Invalid UUIDs"
**Symptoms:**
- `config.lua` missing or contains example UUIDs
- Validation fails with UUID errors
- Watcher cannot find configuration

**Solution:**
```bash
# Generate new configuration interactively
python generate_lua_config.py -i

# Validate the generated config
python validate_pipeline_config.py
```

**Root Cause:** Configuration not generated or generated with wrong UUIDs.

#### Problem: "UUID mismatch" errors
**Symptoms:**
- Config has valid UUIDs but they don't match database
- API returns 404 for runs or players
- Watcher events are rejected

**Diagnostic:**
```bash
# Check run/player relationship
python validate_pipeline_config.py
```

**Solution:**
1. Open admin panel: http://127.0.0.1:8000/admin
2. Find the correct run and player UUIDs
3. Regenerate config with correct UUIDs:
   ```bash
   python generate_lua_config.py --run-id <UUID> --player-id <UUID>
   ```

---

### 🌐 API Server Issues

#### Problem: "Server not running" or "Connection refused"
**Symptoms:**
- Cannot access http://127.0.0.1:8000
- API health checks fail
- Watcher cannot connect

**Diagnostic:**
```bash
# Check server status
python diagnose_pipeline.py --component api

# Check processes
tasklist | findstr python     # Windows
ps aux | grep python          # Linux/Mac
```

**Solution:**
```bash
# Start the server
python start_server.py

# Or use portable mode
python soullink_portable.py
```

#### Problem: "Server runs but endpoints return errors"
**Symptoms:**
- Server starts but returns 500 errors
- Database errors in logs
- Some endpoints work, others don't

**Diagnostic:**
```bash
# Check specific endpoints
curl http://127.0.0.1:8000/v1/health
curl http://127.0.0.1:8000/v1/runs

# Check server logs
python start_server.py  # Check console output
```

**Solution:**
1. Check database integrity:
   ```bash
   python diagnose_pipeline.py --component database
   ```
2. Run database migrations:
   ```bash
   alembic upgrade head
   ```
3. Restart server after fixes

---

### 💾 Database Issues

#### Problem: "Database not found" or "Database locked"
**Symptoms:**
- `soullink_tracker.db` missing
- Database locked errors
- Server fails to start

**Diagnostic:**
```bash
# Check database status
python diagnose_pipeline.py --component database

# Check file permissions
ls -la soullink_tracker.db  # Linux/Mac
dir soullink_tracker.db     # Windows
```

**Solutions:**

For missing database:
```bash
# Start server to create database
python start_server.py

# Run migrations
alembic upgrade head
```

For locked database:
1. Close all applications using the database
2. Restart the server
3. If still locked, restart your computer

#### Problem: "Missing required tables" or "Database corruption"
**Symptoms:**
- Database exists but missing tables
- Migration errors
- Data inconsistencies

**Solution:**
```bash
# Check current migration state
alembic current

# Run all migrations
alembic upgrade head

# If severely corrupted, backup and recreate:
mv soullink_tracker.db soullink_tracker.db.backup
python start_server.py
```

---

### 🎮 Lua Script Issues

#### Problem: "Cannot find config.lua" or "DeSmuME errors"
**Symptoms:**
- Lua script fails to load
- Memory address errors
- No events generated

**Diagnostic:**
```bash
# Check Lua environment
python diagnose_pipeline.py --component lua

# Validate config specifically
python validate_pipeline_config.py --config client/lua/config.lua
```

**Solutions:**

For missing config:
```bash
# Generate config
python generate_lua_config.py -i

# Verify config location
ls client/lua/config.lua
```

For DeSmuME issues:
1. Use correct ROM region (US/EU)
2. Update `memory_profile` in config.lua
3. Check DeSmuME Lua scripting is enabled
4. Try restarting DeSmuME

#### Problem: "Memory addresses incorrect" or "No encounters detected"
**Symptoms:**
- Script runs but no events
- Wrong encounter data
- Memory read errors

**Solution:**
1. Check ROM region matches config:
   ```lua
   memory_profile = "US"  -- or "EU"
   ```
2. Verify ROM is HeartGold/SoulSilver (not other games)
3. Update to latest `pokemon_tracker_v3_fixed.lua`

---

### 👀 Watcher Issues

#### Problem: "Watcher cannot start" or "Module import errors"
**Symptoms:**
- `simple_watcher.py` fails to run
- Missing dependencies
- Cannot find config

**Diagnostic:**
```bash
# Test watcher can run
python simple_watcher.py --help

# Check watcher status
python diagnose_pipeline.py --component watcher
```

**Solutions:**

For import errors:
```bash
# Install required packages
pip install -r requirements.txt

# Check Python path
python -c "import sys; print(sys.path)"
```

For config issues:
```bash
# Ensure config.lua exists and is valid
python validate_pipeline_config.py
```

#### Problem: "Events not being sent" or "API connection fails"
**Symptoms:**
- Watcher starts but no events reach server
- Connection timeout errors
- Authentication failures

**Diagnostic:**
```bash
# Test integration
python diagnose_pipeline.py --component integration

# Manual API test
curl -H "Authorization: Bearer test" http://127.0.0.1:8000/v1/events
```

**Solution:**
1. Verify server is running and accessible
2. Check API URL in config.lua matches server
3. Verify network connectivity (firewall, antivirus)
4. Check authentication tokens are valid

---

## Advanced Troubleshooting

### 🔄 Integration Testing

#### Problem: "Components work individually but not together"
**Symptoms:**
- Each component passes individual tests
- End-to-end flow doesn't work
- Events lost in pipeline

**Full Integration Test:**
```bash
# Run complete diagnostic
python diagnose_pipeline.py

# Test each step manually:
# 1. Generate test event
echo '{"type":"test","timestamp":"2025-01-01T00:00:00Z"}' > /tmp/soullink_events/test.json

# 2. Check watcher processes it
python simple_watcher.py --test-mode

# 3. Verify API receives it
curl http://127.0.0.1:8000/v1/runs/YOUR_RUN_ID/encounters
```

### 🔍 Log Analysis

#### Accessing Logs
```bash
# Server logs (console output)
python start_server.py

# Watcher logs 
python simple_watcher.py --debug

# System logs (Windows)
Event Viewer -> Application Logs

# System logs (Linux/Mac)
journalctl -f
tail -f /var/log/syslog
```

#### Log Patterns to Look For

**Success Patterns:**
- `"Config validation passed"`
- `"WebSocket connection established"`
- `"Event processed successfully"`
- `"Database connection OK"`

**Error Patterns:**
- `"Connection refused"`
- `"UUID not found"`
- `"Database locked"`
- `"Validation failed"`
- `"Authentication failed"`

### 🚨 Emergency Recovery

#### Complete Reset (Nuclear Option)
If nothing else works, full reset:

```bash
# 1. Stop all processes
taskkill /f /im python.exe     # Windows
killall python                # Linux/Mac

# 2. Backup important data
cp soullink_tracker.db soullink_tracker.db.backup

# 3. Clean slate
rm -f client/lua/config.lua
rm -rf /tmp/soullink_events/*

# 4. Restart setup
python start_server.py        # New terminal
setup_player.bat               # Run setup again
```

#### Selective Component Reset

**Reset Configuration Only:**
```bash
rm client/lua/config.lua
python generate_lua_config.py -i
python validate_pipeline_config.py
```

**Reset Database Only:**
```bash
mv soullink_tracker.db soullink_tracker.db.backup
python start_server.py  # Creates new database
# Recreate runs/players in admin panel
```

---

## Error Code Reference

### Exit Codes from Diagnostic Tools

| Code | Meaning | Action |
|------|---------|---------|
| 0 | Success | Continue with setup |
| 1 | Critical failure | Fix errors before proceeding |
| 2 | Warnings only | May proceed with caution |
| 130 | User cancelled | Normal cancellation |

### Common HTTP Status Codes

| Code | Meaning | Typical Cause |
|------|---------|---------------|
| 200 | OK | Success |
| 401 | Unauthorized | Invalid/missing authentication |
| 404 | Not Found | Wrong UUID or endpoint |
| 429 | Rate Limited | Too many requests |
| 500 | Server Error | Database/server issues |
| 503 | Unavailable | Server not running |

---

## Component Dependencies

Understanding component relationships helps with troubleshooting:

```
┌─────────────────┐    ┌──────────────────┐
│   config.lua    │───▶│  Lua Script      │
└─────────────────┘    └──────────────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         │              │  Event Files     │
         │              └──────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Watcher       │───▶│   API Server     │───▶│   Database       │
└─────────────────┘    └──────────────────┘    └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  WebSocket UI    │
                       └──────────────────┘
```

**Dependency Rules:**
1. **config.lua** must have valid UUIDs from database
2. **Database** must exist before watcher/API can work
3. **API Server** must be running before watcher starts
4. **Lua Script** needs config.lua to know where to send events
5. **Watcher** needs both API connectivity and event directory access

---

## Getting Help

### Information to Collect

When reporting issues, include:

```bash
# System information
python diagnose_pipeline.py --export diagnostic_report.json

# Configuration validation
python validate_pipeline_config.py --json > config_validation.json

# Platform details
echo "OS: $(uname -a)"           # Linux/Mac
echo "OS: Windows $(ver)"        # Windows
python --version
```

### Support Resources

1. **GitHub Issues**: Report bugs with diagnostic output
2. **Documentation**: Check README.md and SETUP_GUIDE.md
3. **Logs**: Always include relevant log excerpts
4. **Configuration**: Share anonymized config (remove UUIDs)

### Self-Help Checklist

Before asking for help:

- [ ] Ran `python diagnose_pipeline.py`
- [ ] Ran `python validate_pipeline_config.py`
- [ ] Checked server is running (`curl http://127.0.0.1:8000/v1/health`)
- [ ] Verified config.lua has correct UUIDs
- [ ] Restarted all components
- [ ] Checked firewall/antivirus isn't blocking
- [ ] Tried on different network/computer
- [ ] Read error messages carefully
- [ ] Searched existing GitHub issues

---

## Prevention Tips

### Regular Maintenance

```bash
# Weekly health check
python diagnose_pipeline.py --export weekly_health.json

# Validate configuration after changes
python validate_pipeline_config.py

# Check database integrity
python diagnose_pipeline.py --component database
```

### Best Practices

1. **Always validate after config changes**
2. **Keep diagnostic output for comparison**
3. **Test pipeline before important runs**
4. **Regular database backups**
5. **Monitor disk space for event files**
6. **Update components together, not piecemeal**

### Backup Strategy

```bash
# Backup critical files
cp soullink_tracker.db soullink_tracker.db.$(date +%Y%m%d)
cp client/lua/config.lua client/lua/config.lua.backup
tar -czf soullink_backup_$(date +%Y%m%d).tar.gz soullink_tracker.db client/lua/config.lua data/config.json
```

---

This guide covers the most common issues. For complex problems, use the diagnostic tools first, then refer to specific sections based on the component showing issues.