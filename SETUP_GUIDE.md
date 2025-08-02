# SoulLink Tracker - Complete Setup Guide

This guide provides step-by-step instructions for setting up the SoulLink Tracker system with automated installation scripts.

## Overview

The SoulLink Tracker consists of two main components:
- **Admin Server**: Centralized tracking server with web dashboard
- **Player Clients**: Individual client setups for each player's DeSmuME + event monitoring

## Prerequisites

### System Requirements
- **Python 3.9+** (required for both admin and players)
- **Internet connection** (for package installation and tunnel setup)
- **DeSmuME emulator** (players only)
- **Pokemon HeartGold/SoulSilver ROM** (players only)

### Administrative Privileges
- Admin setup requires administrative/sudo privileges for:
  - Installing system packages
  - Setting up networking (Cloudflare tunnel)
  - Configuring services

## Part 1: Admin Setup

### Quick Start (Recommended)
```bash
# Navigate to project directory
cd /path/to/SoulLink_Tracker

# Run admin setup with automatic mode selection
python3 scripts/admin_setup.py

# Follow the interactive prompts to choose:
# 1. Development mode (local testing)
# 2. Production mode (with external tunnel)
```

### Advanced Admin Setup Options

#### Development Mode (Local Only)
```bash
python3 scripts/admin_setup.py --dev
```
- Runs server locally only (127.0.0.1:9000)
- No external tunnel setup
- Ideal for testing and development
- Players must be on same network

#### Production Mode (With Tunnel)
```bash
python3 scripts/admin_setup.py --production
```
- Sets up Cloudflare tunnel for external access
- Generates public URL for remote players
- Automatic SSL/TLS encryption
- Ideal for distributed play sessions

#### Reset Configuration
```bash
python3 scripts/admin_setup.py --reset --production
```
- Clears all previous configuration
- Rebuilds database from scratch
- Regenerates all tokens and configs

#### Tunnel Only Setup
```bash
python3 scripts/admin_setup.py --tunnel-only
```
- Only installs and configures Cloudflare tunnel
- Use when server is already running

### What Admin Setup Does

1. **System Validation**
   - Checks Python version (3.9+ required)
   - Verifies disk space and network connectivity
   - Validates required system commands

2. **Dependency Installation**
   - Installs Python packages (FastAPI, SQLite, etc.)
   - Downloads Cloudflare tunnel binary (production mode)
   - Sets up virtual environment if needed

3. **Database Initialization**
   - Creates SQLite database with WAL mode
   - Populates with Pokemon species and route data
   - Generates test run with sample players
   - Creates database backup

4. **Network Configuration**
   - Sets up Cloudflare tunnel (production mode)
   - Generates external URL for player access
   - Configures proper CORS and security headers

5. **Service Startup**
   - Starts FastAPI server (uvicorn)
   - Starts tunnel process (if enabled)
   - Monitors service health

6. **Admin Tools Generation**
   - Creates player distribution packages
   - Generates monitoring scripts
   - Sets up log rotation

### Admin Outputs

After successful setup, you'll see:
```
🎮 SOULLINK TRACKER - ADMIN SUMMARY
================================================================
🔧 System Information:
   Mode: PRODUCTION
   Project: /path/to/SoulLink_Tracker
   Python: 3.11.0

🌐 Server URLs:
   Local API: http://127.0.0.1:9000
   Public URL: https://random-tunnel.trycloudflare.com
   API Docs: http://127.0.0.1:9000/docs

📊 Current Run:
   Name: Test SoulLink Run
   ID: 550e8400-e29b-41d4-a716-446655440000
   Players: 3
   Dashboard: http://127.0.0.1:9000/dashboard?run=550e8400-e29b-41d4-a716-446655440000

🛠️ Admin Tools:
   Distribute players: python scripts/distribute_players.py
   Health check: python scripts/health_check.py
   Database backup: python scripts/backup_database.py

🎯 Next Steps:
   1. Run: python scripts/distribute_players.py
   2. Send player packages to each player
   3. Monitor logs and dashboard for activity
   4. Use Ctrl+C to shutdown all services
```

## Part 2: Player Distribution

### Generate Player Packages
```bash
# After admin setup completes, generate player packages
python3 scripts/distribute_players.py
```

This creates individual setup packages for each player:
```
player_packages/
├── Player1_setup.zip
├── Player2_setup.zip
└── Player3_setup.zip
```

Each package contains:
- `setup.py` - Player setup script
- `player_config.json` - Pre-configured connection details
- `README.md` - Player-specific instructions

### Send to Players
- Send the appropriate `.zip` file to each player
- Players extract and run the setup script
- No additional coordination required

## Part 3: Player Setup

### Player Quick Start
```bash
# Extract the setup package received from admin
unzip PlayerName_setup.zip
cd PlayerName_package

# Run the setup script
python3 setup.py
```

### Manual Player Setup
If using the main project directory:
```bash
# Create player configuration file
cat > player_config.json << EOF
{
    "player_id": "uuid-from-admin",
    "player_name": "Your Name",
    "server_url": "https://tunnel-url.trycloudflare.com",
    "bearer_token": "jwt-token-from-admin"
}
EOF

# Run player setup
python3 scripts/player_setup.py player_config.json
```

### Interactive Player Setup
```bash
python3 scripts/player_setup.py --interactive
```
Prompts for:
- Player name
- Server URL
- Bearer token

### What Player Setup Does

1. **Configuration Loading**
   - Loads player config from JSON file or interactive input
   - Validates connection credentials
   - Tests server connectivity

2. **System Check**
   - Verifies Python 3.8+ 
   - Checks disk space and network
   - Locates DeSmuME installation

3. **Dependency Installation**
   - Installs required Python packages
   - Downloads missing client files if needed
   - Creates directory structure

4. **Client Configuration**
   - Generates player-specific Lua config
   - Creates event watcher configuration
   - Sets up logging and monitoring

5. **DeSmuME Integration**
   - Provides DeSmuME setup instructions
   - Generates custom Lua script
   - Configures automatic event detection

6. **Service Startup**
   - Starts event watcher process
   - Opens player dashboard
   - Begins monitoring system

### Player Outputs

After successful setup:
```
🎮 SOULLINK TRACKER - PLAYER SETUP COMPLETE
======================================================================
👤 Player Information:
   Name: Player1
   ID: 123e4567-e89b-12d3-a456-426614174000
   Server: https://tunnel-url.trycloudflare.com

📁 Configuration Files:
   Watcher config: client/watcher/configs/player1_config.json
   Lua config: client/lua/configs/player1_config.lua

🕹️ DeSmuME Setup:
   1. Open DeSmuME
   2. Load Pokemon HG/SS ROM
   3. Tools → Lua Script Console
   4. Load: client/lua/configs/player1_config.lua

📊 Monitoring:
   Event watcher: Running
   Log file: logs/player1_watcher.log
   Events dir: temp/events

🌐 Web Dashboard:
   URL: https://tunnel-url.trycloudflare.com/dashboard?run=550e8400-e29b-41d4-a716-446655440000

🚀 Ready to Play!
   - Start playing Pokemon HG/SS in DeSmuME
   - Events will be automatically tracked
   - Monitor dashboard for real-time updates
   - Press Ctrl+C in this window to stop monitoring
```

## Part 4: Playing the SoulLink

### DeSmuME Setup (Each Player)
1. **Load ROM**: Open Pokemon HeartGold/SoulSilver in DeSmuME
2. **Enable Lua**: Tools → Lua Script Console
3. **Load Script**: Open the generated `player_config.lua` file
4. **Start Playing**: Events are automatically detected and tracked

### Monitoring and Dashboard
- **Web Dashboard**: Real-time view of all encounters, catches, and deaths
- **Event Logs**: Detailed logs of all game events
- **Soul Link Status**: Visual representation of linked Pokemon
- **Route Matrix**: Overview of encounters per route per player

### Troubleshooting

#### Admin Issues
```bash
# Check service status
curl http://127.0.0.1:9000/health

# View logs
tail -f logs/api.log
tail -f logs/tunnel.log

# Restart services
python3 scripts/admin_setup.py --reset --production
```

#### Player Issues
```bash
# Check event watcher
ps aux | grep event_watcher

# View logs
tail -f logs/player_watcher.log

# Test server connection
curl -H "Authorization: Bearer YOUR_TOKEN" SERVER_URL/health

# Restart watcher
python3 scripts/player_setup.py player_config.json
```

#### Common Problems

1. **Connection Refused**
   - Check server URL and token
   - Verify tunnel is running (admin)
   - Check firewall settings

2. **Events Not Detected**
   - Verify DeSmuME Lua script is loaded
   - Check ROM region compatibility
   - Review Lua console for errors

3. **Dashboard Not Updating**
   - Check WebSocket connection
   - Verify event watcher is running
   - Clear browser cache

## Part 5: Advanced Configuration

### Environment Variables
```bash
# Override default settings
export SOULLINK_DB_PATH="/custom/path/soullink.db"
export SOULLINK_LOG_LEVEL="DEBUG"
export SOULLINK_API_PORT="8080"
```

### Custom Rules Configuration
Edit `test_config.json` to modify:
- Dupes clause behavior
- Soul link rules
- Encounter validation
- Fishing rod detection

### Production Deployment
For permanent deployment:
1. Use process manager (systemd, supervisor)
2. Set up proper logging rotation
3. Configure backup automation
4. Monitor with external health checks

## Security Considerations

- **Bearer Tokens**: Generated with cryptographic security
- **HTTPS**: Automatic via Cloudflare tunnel
- **Rate Limiting**: Built-in API protection
- **Input Validation**: All events validated server-side
- **CORS**: Configured for web dashboard access

## Support and Maintenance

- **Logs**: Check `logs/` directory for troubleshooting
- **Database**: Automatic backups created during setup
- **Updates**: Re-run setup scripts to update configurations
- **Monitoring**: Health check endpoints available for external monitoring

---

**Happy SoulLinking!** 🎮✨