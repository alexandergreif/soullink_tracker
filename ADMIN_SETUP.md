# SoulLink Tracker - Admin Setup Guide

**For the person setting up and hosting the SoulLink Tracker system**

This guide is for the **admin/host** who will set up the central server and coordinate the 3-player Pokemon SoulLink playtest. Players should use the separate [PLAYER_SETUP.md](PLAYER_SETUP.md) guide.

## Admin Responsibilities

As the admin, you will:
- 🖥️ Set up and run the central API server
- 🗄️ Initialize the database with run data
- 👥 Create player accounts and provide authentication tokens
- 🌐 Host the web dashboard for real-time monitoring
- 🔧 Troubleshoot technical issues during the playtest

## Prerequisites

### System Requirements
- **Python 3.9+** installed
- **4GB+ RAM** (8GB+ recommended)
- **Stable internet connection** 
- **Modern web browser**
- **Basic command line knowledge**

### Network Setup
- **Port 9000** available (for API server)
- **Firewall configured** to allow incoming connections on port 9000
- **Static IP or domain** (recommended for multi-computer setups)

## Quick Setup (10 Minutes)

### 1. Download and Install

```bash
# Clone or download the SoulLink Tracker project
git clone https://github.com/your-repo/SoulLink_Tracker.git
cd SoulLink_Tracker

# Install Python dependencies
pip install -r requirements.txt
pip install -r client/watcher/requirements.txt

# Verify installation
python scripts/health_check.py
```

### 2. Initialize the System

```bash
# Run the automated setup (this does everything!)
python scripts/start_playtest.py
```

This script will automatically:
- ✅ Create the database with sample data
- ✅ Generate 3 player accounts with authentication tokens
- ✅ Create all configuration files
- ✅ Start the API server
- ✅ Open the web dashboard
- ✅ Display setup instructions for players

### 3. Share Player Information

The setup script creates `test_config.json` with player details:

```json
{
  "run_id": "uuid-of-the-run",
  "run_name": "Test SoulLink Run - HG/SS", 
  "players": [
    {
      "id": "player-uuid-1",
      "name": "Player1",
      "game": "HeartGold",
      "token": "jwt-token-for-player-1"
    },
    {
      "id": "player-uuid-2", 
      "name": "Player2",
      "game": "SoulSilver", 
      "token": "jwt-token-for-player-2"
    },
    {
      "id": "player-uuid-3",
      "name": "Player3", 
      "game": "HeartGold",
      "token": "jwt-token-for-player-3"
    }
  ]
}
```

**Send each player:**
1. Their **player name** and **authentication token**
2. Your **server IP address** (e.g., `192.168.1.100` or domain name)
3. The **run ID** for the web dashboard
4. Link to the [PLAYER_SETUP.md](PLAYER_SETUP.md) guide

## Manual Setup (Advanced)

If you prefer manual setup or need customization:

### 1. Initialize Database

```bash
# Create database with sample data
python scripts/init_database.py

# This creates:
# - soullink_tracker.db (SQLite database)
# - test_config.json (run and player info)
# - Loads Pokemon species and route data
```

### 2. Generate Player Configurations

```bash
# Create configuration files for all players
python client/watcher/player_config.py --api-url http://YOUR_IP:9000

# This creates:
# - client/watcher/configs/player1_config.json
# - client/watcher/configs/player2_config.json  
# - client/watcher/configs/player3_config.json
# - client/lua/configs/player1_config.lua
# - client/lua/configs/player2_config.lua
# - client/lua/configs/player3_config.lua
```

### 3. Start API Server

```bash
# Start the FastAPI server (accessible to other computers)
uvicorn src.soullink_tracker.main:app --host 0.0.0.0 --port 9000 --reload

# Test server is running
curl http://localhost:9000/health
```

### 4. Access Web Dashboard

Open in your browser:
- **Dashboard**: `http://YOUR_IP:9000/dashboard?run=RUN_ID_FROM_CONFIG`
- **API Docs**: `http://YOUR_IP:9000/docs`

## Network Configuration

### Single Computer Setup

All players on the same computer:
```bash
# Use localhost (default)
python scripts/start_playtest.py
# Players connect to: http://127.0.0.1:9000
```

### Multi-Computer Setup (Local Network)

Players on different computers in the same network:

```bash
# Start server accessible to local network
uvicorn src.soullink_tracker.main:app --host 0.0.0.0 --port 9000 --reload

# Find your IP address:
# Windows: ipconfig
# Mac/Linux: ifconfig

# Players connect to: http://YOUR_LOCAL_IP:9000
# Example: http://192.168.1.100:9000
```

### Internet Setup (Remote Players)

For players connecting over the internet:

#### Option 1: Port Forwarding
1. Configure router to forward port 9000 to your computer
2. Find your public IP: `curl ifconfig.me`
3. Players connect to: `http://YOUR_PUBLIC_IP:9000`

#### Option 2: Cloudflare Tunnel (Recommended)
```bash
# Install cloudflared
# Download from: https://github.com/cloudflare/cloudflared/releases

# Create tunnel (free, no port forwarding needed)
cloudflared tunnel --url http://localhost:9000

# Gives you a public URL like: https://abc123.trycloudflare.com
# Players connect to this URL instead
```

#### Option 3: ngrok
```bash
# Install ngrok: https://ngrok.com/download

# Expose local server
ngrok http 9000

# Gives you a public URL
# Players connect to this URL
```

## Player Management

### Adding New Players

```bash
# Edit test_config.json to add more players
# Then regenerate configurations:
python client/watcher/player_config.py
```

### Changing Player Names

1. Edit `test_config.json`
2. Update player names in the database (via API or direct SQL)
3. Regenerate config files

### Resetting Player Tokens

```bash
# Regenerate all configurations (creates new tokens)
python client/watcher/player_config.py --cleanup
python client/watcher/player_config.py
```

## Monitoring and Management

### Web Dashboard Features

The admin dashboard shows:
- 📊 **Run Statistics**: Total encounters, catches, faints, soul links
- 👥 **Player Status**: Online/offline, current stats, party Pokemon
- 📅 **Recent Events**: Real-time event feed with timestamps
- 🔗 **Soul Links**: Visual representation of linked Pokemon
- ⚡ **Connection Status**: WebSocket connectivity indicator

### Real-Time Monitoring

- **Events appear instantly** as players encounter/catch Pokemon
- **Soul links form automatically** when players catch on same route
- **Rules are enforced** (dupes clause, species clause, family blocking)
- **Toast notifications** for important events

### Health Monitoring

```bash
# Check system health
python scripts/health_check.py

# Run functional tests
python scripts/quick_test.py

# Check API endpoints
curl http://YOUR_IP:9000/health
curl http://YOUR_IP:9000/v1/runs/RUN_ID
```

## Troubleshooting

### Common Admin Issues

#### "Port 9000 already in use"
```bash
# Find process using port 9000
lsof -i :9000  # Mac/Linux
netstat -ano | findstr :9000  # Windows

# Kill the process or use different port
uvicorn src.soullink_tracker.main:app --host 0.0.0.0 --port 8000
```

#### "Players can't connect"
- ✅ Check firewall allows port 9000
- ✅ Verify IP address is correct
- ✅ Test with `curl http://YOUR_IP:9000/health`
- ✅ Check router port forwarding (if needed)

#### "Database errors"
```bash
# Reinitialize database
rm soullink_tracker.db test_config.json
python scripts/init_database.py
```

#### "WebSocket not working"
- ✅ Check browser console for errors
- ✅ Verify run ID in dashboard URL
- ✅ Test WebSocket endpoint: `ws://YOUR_IP:9000/v1/ws/RUN_ID`

### Player Support

When players have issues:

1. **Direct them to** [PLAYER_SETUP.md](PLAYER_SETUP.md)
2. **Check their token** is correct in config file
3. **Verify their API URL** points to your server
4. **Test connectivity** from their computer:
   ```bash
   curl http://YOUR_IP:9000/health
   ```

### Advanced Debugging

Enable debug logging:
```bash
# Start server with debug logging
uvicorn src.soullink_tracker.main:app --host 0.0.0.0 --port 9000 --log-level debug

# Check detailed logs in console output
```

## Security Considerations

### Basic Security

- 🔒 **JWT Tokens**: Each player has unique authentication
- 🔒 **Input Validation**: All API inputs are validated
- 🔒 **CORS Protection**: Cross-origin requests are controlled
- 🔒 **Idempotency**: Duplicate events are prevented

### Production Recommendations

For serious/long-term deployments:

```bash
# Use HTTPS (required for production)
# Use PostgreSQL instead of SQLite
# Add rate limiting
# Use Redis for WebSocket scaling
# Add monitoring and logging
# Use Docker for containerization
```

## Configuration Files Reference

### Key Files Created

```
SoulLink_Tracker/
├── soullink_tracker.db           # SQLite database
├── test_config.json              # Run and player info
├── client/watcher/configs/       # Python watcher configs
│   ├── player1_config.json
│   ├── player2_config.json
│   └── player3_config.json
├── client/lua/configs/           # DeSmuME Lua configs
│   ├── player1_config.lua
│   ├── player2_config.lua
│   └── player3_config.lua
└── logs/                         # Log files
    ├── health_check_*.json
    └── watcher_*.log
```

### API Endpoints

Important endpoints for monitoring:

- `GET /health` - Server health check
- `GET /v1/runs/{run_id}` - Run information
- `GET /v1/runs/{run_id}/players` - Player list
- `GET /v1/runs/{run_id}/encounters` - Recent encounters
- `GET /v1/runs/{run_id}/soul-links` - Soul links
- `WS /v1/ws/{run_id}` - WebSocket for real-time updates

## Run Management

### Starting a New Run

```bash
# Create fresh database and run
rm soullink_tracker.db test_config.json
python scripts/init_database.py

# Update player names in test_config.json if needed
# Regenerate configurations
python client/watcher/player_config.py
```

### Backup and Recovery

```bash
# Backup database
cp soullink_tracker.db soullink_tracker_backup_$(date +%Y%m%d).db

# Backup configuration
cp test_config.json test_config_backup.json
```

### Mid-Run Administration

- **View all data** via API endpoints or web dashboard
- **Manual overrides** available via admin API (if needed)
- **Export run data** for post-run analysis
- **Monitor player activity** in real-time

## Post-Run Analysis

After your playtest:

```bash
# Export run data (future feature)
python scripts/export_run_data.py --run-id RUN_ID --format json

# Generate run report (future feature)  
python scripts/generate_report.py --run-id RUN_ID
```

## Getting Help

### For Admin Issues

1. **Check health status**: `python scripts/health_check.py`
2. **Run functional tests**: `python scripts/quick_test.py`
3. **Check server logs** in console output
4. **Verify network connectivity** from player machines

### For Player Issues

1. **Direct players to** [PLAYER_SETUP.md](PLAYER_SETUP.md)
2. **Help debug their configuration** files
3. **Test API connectivity** from their machines
4. **Check authentication tokens** are correct

---

## You're Ready to Host! 🎮

Once setup is complete:

1. ✅ **Send players their setup information**
2. ✅ **Share the player setup guide** 
3. ✅ **Coordinate start time** for everyone to begin
4. ✅ **Monitor the dashboard** during play
5. ✅ **Help troubleshoot** any issues that arise
6. ✅ **Enjoy watching** the SoulLink unfold in real-time!

**Good luck with your Pokemon SoulLink adventure! 🔗✨**

*The players will love seeing their encounters and soul links appear instantly on the dashboard!*