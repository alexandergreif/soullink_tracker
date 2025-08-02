---
name: Setup Failure
about: Report issues with admin or player setup processes
title: '[SETUP] Setup failed at [step description]'
labels: 'setup, bug'
assignees: ''
---

## Setup Type
- [ ] Admin Setup (`run_admin_setup.bat` or `python scripts/admin_setup.py`)
- [ ] Player Setup (`run_player_setup.bat` or `python scripts/player_setup.py`)
- [ ] Database Initialization (`python scripts/init_database.py`)

## System Information
**Operating System:** (Windows 11, macOS, Linux)
**Python Version:** (run `python --version`)
**Setup Method:** (Batch file, Direct Python script)

## Failure Point
**Step Where Setup Failed:** (e.g., "Step 4: Setting up database", "Player configuration loading")

## Complete Error Output
```
Paste the complete terminal/console output here, including all error messages and stack traces
```

## Setup Configuration
**Admin Setup Mode:** (Development/Production/Reset - if applicable)
**Configuration Files Present:** 
- [ ] player_config.json (for player setup)
- [ ] test_config.json (for database setup)
- [ ] admin_config.json (if exists)

## Previous Steps
What steps were completed successfully before the failure?
- [ ] Python dependencies installed
- [ ] Database initialized
- [ ] Configuration files created
- [ ] Network connectivity verified
- [ ] Other: _______________

## Environment Details
**Python Path:** (run `which python` or `where python`)
**Virtual Environment:** (Yes/No - if yes, which one?)
**Permissions:** (Running as administrator? Standard user?)
**Network:** (Behind corporate firewall? Proxy settings?)

## Reproducibility
- [ ] This happens every time I try to set up
- [ ] This happened once, and retrying worked
- [ ] This happens intermittently
- [ ] This only happens on specific configurations

## Attempted Solutions
What have you already tried to fix this?
- [ ] Re-downloaded the project
- [ ] Reinstalled Python
- [ ] Ran as administrator
- [ ] Disabled antivirus temporarily
- [ ] Cleared previous setup files
- [ ] Other: _______________

## Additional Context
Add any other context about the setup failure:
- Using corporate/managed computer?
- Specific antivirus or security software?
- Network restrictions or proxies?
- Modified any setup scripts?

## Logs and Configuration
If available, please attach or paste:
- Log files from the `logs/` directory
- Configuration files (with sensitive data removed)
- Output from `python scripts/test_windows_compatibility.py` (if on Windows)

## Checklist
- [ ] I have included the complete error output
- [ ] I have specified exactly which step failed
- [ ] I have listed what I've already tried
- [ ] I have checked for similar existing issues
- [ ] I have tested with a fresh download (if applicable)