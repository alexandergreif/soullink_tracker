#!/usr/bin/env python3
"""
Helper script to generate config.lua for the Lua tracker
Gets run and player information from the SoulLink Tracker API
"""

import requests
import sys
from pathlib import Path

def get_admin_info(api_url="http://127.0.0.1:8000"):
    """Get run and player information from admin API."""
    try:
        # Get runs
        runs_response = requests.get(f"{api_url}/v1/admin/runs", timeout=10)
        if runs_response.status_code != 200:
            print(f"❌ Failed to get runs: {runs_response.status_code}")
            return None
            
        runs = runs_response.json()
        if not runs:
            print("❌ No runs found. Create a run in the admin panel first.")
            return None
            
        # Use first run
        run = runs[0]
        run_id = run['id']
        run_name = run['name']
        
        # Get players for this run
        players_response = requests.get(f"{api_url}/v1/runs/{run_id}/players", timeout=10)
        if players_response.status_code != 200:
            print(f"❌ Failed to get players: {players_response.status_code}")
            return None
            
        players_data = players_response.json()
        
        # Handle both direct list and wrapped response formats
        if isinstance(players_data, dict) and 'players' in players_data:
            players = players_data['players']
        else:
            players = players_data
            
        if not players:
            print("❌ No players found. Create a player in the admin panel first.")
            return None
            
        # Use first player
        player = players[0]
        player_id = player['id']
        player_name = player['name']
        
        return {
            'run_id': run_id,
            'run_name': run_name,
            'player_id': player_id,
            'player_name': player_name,
            'api_url': api_url
        }
        
    except requests.RequestException as e:
        print(f"❌ Cannot connect to server: {e}")
        print("Make sure the SoulLink Tracker server is running at http://127.0.0.1:8000")
        return None

def generate_config_lua(info):
    """Generate config.lua content."""
    config_content = f'''--[[
SoulLink Tracker Configuration
Auto-generated on {info.get('timestamp', 'unknown')}

Run: {info['run_name']} ({info['run_id']})
Player: {info['player_name']} ({info['player_id']})
]]

local config = {{
    -- API Configuration
    api_base_url = "{info['api_url']}",
    
    -- Run and Player IDs (from admin panel)
    run_id = "{info['run_id']}",
    player_id = "{info['player_id']}",
    
    -- Event Output Configuration
    output_dir = "C:/temp/soullink_events/",
    
    -- Script Behavior
    poll_interval = 60,    -- Frames between checks (60 = 1 second at 60fps)
    debug = true,          -- Enable debug logging
    max_runtime = 3600,    -- Maximum runtime in seconds (1 hour)
    
    -- Memory Profile (US/EU)
    memory_profile = "US"  -- Change to "EU" if needed
}}

return config
'''
    return config_content

def main():
    print("🎮 SoulLink Tracker - Lua Config Generator")
    print("=" * 50)
    
    # Check if server is running
    print("🔍 Checking server connection...")
    info = get_admin_info()
    if not info:
        print("\n💡 To fix this:")
        print("1. Start the SoulLink Tracker server: python start_server.py")
        print("2. Open admin panel: http://127.0.0.1:8000/admin")
        print("3. Create a run and add a player")
        print("4. Run this script again")
        sys.exit(1)
    
    print("✅ Server connection successful")
    print(f"📋 Found run: {info['run_name']}")
    print(f"👤 Found player: {info['player_name']}")
    
    # Generate config content
    from datetime import datetime
    info['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    config_content = generate_config_lua(info)
    
    # Write config file
    config_path = Path("client/lua/config.lua")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        print(f"✅ Generated config file: {config_path}")
        print(f"\n🔑 Configuration details:")
        print(f"   Run ID: {info['run_id']}")
        print(f"   Player ID: {info['player_id']}")
        print(f"   API URL: {info['api_url']}")
        
        print(f"\n🚀 Next steps:")
        print(f"1. Load the Lua script in DeSmuME: {config_path.parent}/pokemon_tracker_v3_fixed.lua")
        print(f"2. Start the Python watcher: python simple_watcher.py")
        print(f"3. Events should now appear in the dashboard!")
        
    except Exception as e:
        print(f"❌ Failed to write config file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()