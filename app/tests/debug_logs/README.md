# Debug Logs Directory

This directory stores debug artifacts from manual testing sessions.

## Contents

- `capture_report.json` - Automated capture report with encounter events, timestamps, latencies
- `screenshots/` - Battle screen captures (if Playwright MCP is available)
- `lua_console.txt` - DeSmuME Lua console output (manual copy-paste)

## Playwright MCP Setup (Optional - Windows Only)

Task T004a requires Windows PC with DeSmuME for full manual testing automation.

### Prerequisites
- Windows PC with VSCode + Claude Code installed
- DeSmuME emulator installed
- Pokemon HGSS ROM available

### Installation Steps
1. Install Playwright MCP server:
   ```
   npm install -g @playwright/mcp-server
   ```

2. Configure VSCode settings to enable Playwright MCP integration

3. Verify Playwright can capture screenshots:
   - Test with DeSmuME window capture
   - Verify screenshots saved to `tests/debug_logs/screenshots/`

### Usage
Once configured, the automated capture script (`tests/capture_manual_test.py`) can:
- Monitor JSON file creation in real-time
- Validate encounter JSON against schema
- Measure latency (battle screen → JSON file)
- Capture DeSmuME window screenshots at key moments
- Generate comprehensive debug reports

## Current Environment
- Platform: macOS (Darwin 24.0.0)
- Playwright MCP: Not configured (Windows-only feature)
- Manual testing: Will require Windows environment for full validation

## Note
Task T004a is marked as environment-blocked on macOS. Full manual testing validation requires Windows environment as specified in constitutional requirements.
