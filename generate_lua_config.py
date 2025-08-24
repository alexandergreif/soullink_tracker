#!/usr/bin/env python3
"""Generate Lua configuration from database or user input"""

import json
import sys
import os
import platform
from pathlib import Path
from typing import Optional, Tuple
import sqlite3
from uuid import UUID
from datetime import datetime
import argparse


class LuaConfigGenerator:
    def __init__(self, db_path: str = "soullink_tracker.db"):
        self.db_path = db_path
        self.config_template = '''-- Auto-generated configuration for SoulLink Tracker
-- Generated: {timestamp}
-- Run: {run_name}
-- Player: {player_name}

return {{
    -- Run and Player identification
    run_id = "{run_id}",
    player_id = "{player_id}",
    
    -- API configuration
    api_base_url = "{api_url}",
    
    -- Event output directory
    output_dir = "{output_dir}",
    
    -- Optional: Game version
    game_version = "{game_version}",
    region = "{region}"
}}
'''
    
    def sanitize_lua_string(self, text: str) -> str:
        """Escape special characters for Lua strings"""
        if not text:
            return ""
        # Escape backslashes first
        text = text.replace('\\', '\\\\')
        # Escape quotes
        text = text.replace('"', '\\"')
        # Escape newlines
        text = text.replace('\n', '\\n')
        text = text.replace('\r', '\\r')
        # Limit length
        return text[:100]
    
    def validate_uuid(self, uuid_str: str) -> bool:
        """Validate that a string is a valid UUID"""
        try:
            UUID(uuid_str)
            return True
        except (ValueError, AttributeError):
            return False
    
    def list_runs_and_players(self) -> list:
        """List all available runs and players from database with edge case handling"""
        if not os.path.exists(self.db_path):
            print(f"❌ Database not found at {self.db_path}")
            print("   Make sure the server has been started at least once.")
            return []
        
        # Check if file is actually a database
        if os.path.isdir(self.db_path):
            print(f"❌ {self.db_path} is a directory, not a database file")
            return []
        
        # Check file is readable
        if not os.access(self.db_path, os.R_OK):
            print(f"❌ Cannot read database at {self.db_path} - permission denied")
            return []
        
        conn = None
        try:
            # Use timeout to prevent hanging on locked database
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.row_factory = None  # Return tuples, not Row objects
            cursor = conn.cursor()
            
            # First check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('runs', 'players')")
            tables = cursor.fetchall()
            if len(tables) < 2:
                print("❌ Database is missing required tables (runs, players)")
                print("   Database may be corrupted or from an incompatible version")
                return []
            
            query = '''
            SELECT r.id, r.name, p.id, p.name, p.game, p.region
            FROM runs r
            JOIN players p ON p.run_id = r.id
            ORDER BY r.created_at DESC, p.name
            '''
            
            results = cursor.execute(query).fetchall()
            
            # Validate results have expected structure
            valid_results = []
            for row in results:
                if len(row) == 6:
                    # Validate UUIDs
                    if self.validate_uuid(row[0]) and self.validate_uuid(row[2]):
                        valid_results.append(row)
                    else:
                        print(f"⚠️  Skipping invalid entry with malformed UUIDs")
            
            return valid_results
            
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                print(f"❌ Database is locked - another process may be using it")
                print("   Please close other applications accessing the database")
            elif "corrupt" in str(e).lower():
                print(f"❌ Database appears to be corrupted")
                print("   You may need to restore from a backup or recreate it")
            else:
                print(f"❌ Database operation error: {e}")
            return []
        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass  # Best effort close
    
    def interactive_setup(self) -> Tuple[str, str]:
        """Interactive wizard to select run and player"""
        runs_players = self.list_runs_and_players()
        
        if not runs_players:
            print("❌ No runs found! Please create a run first:")
            print("   1. Start the server: python start_server.py")
            print("   2. Open admin panel: http://127.0.0.1:8000/admin")
            print("   3. Create a run and player")
            sys.exit(1)
        
        print("🎮 SoulLink Tracker Configuration Generator")
        print("=" * 50)
        print("\nAvailable runs and players:")
        
        for idx, (run_id, run_name, player_id, player_name, game, region) in enumerate(runs_players, 1):
            safe_run_name = self.sanitize_lua_string(run_name)
            safe_player_name = self.sanitize_lua_string(player_name)
            print(f"{idx}. {safe_run_name} - {safe_player_name} ({game} {region})")
        
        while True:
            try:
                choice = int(input("\nSelect number: ")) - 1
                if 0 <= choice < len(runs_players):
                    selected = runs_players[choice]
                    return selected[0], selected[2]  # run_id, player_id
                print("Invalid selection!")
            except ValueError:
                print("Please enter a number")
            except KeyboardInterrupt:
                print("\nCancelled")
                sys.exit(0)
    
    def validate_config_output(self, path: Path) -> bool:
        """Validate output location before writing"""
        if path.exists():
            if path.is_dir():
                raise ValueError(f"{path} is a directory, not a file")
            if not os.access(path, os.W_OK):
                # Try to make it writable
                try:
                    path.chmod(0o644)
                except OSError:
                    raise PermissionError(f"Cannot write to {path}")
        else:
            parent = path.parent
            if not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise OSError(f"Cannot create directory {parent}: {e}")
        return True
    
    def generate_config(self, run_id: str, player_id: str, output_path: Optional[Path] = None):
        """Generate config.lua with proper values"""
        # Validate UUIDs
        if not self.validate_uuid(run_id):
            print(f"❌ Invalid run_id UUID: {run_id}")
            return False
        
        if not self.validate_uuid(player_id):
            print(f"❌ Invalid player_id UUID: {player_id}")
            return False
        
        # Get details from database
        if not os.path.exists(self.db_path):
            print(f"❌ Database not found at {self.db_path}")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
            SELECT r.name, p.name, p.game, p.region
            FROM runs r
            JOIN players p ON p.run_id = r.id
            WHERE r.id = ? AND p.id = ?
            '''
            
            result = cursor.execute(query, (run_id, player_id)).fetchone()
            conn.close()
            
            if not result:
                print(f"❌ Run or player not found in database!")
                print(f"   Run ID: {run_id}")
                print(f"   Player ID: {player_id}")
                return False
            
            run_name, player_name, game, region = result
            
            # Sanitize names for Lua
            run_name = self.sanitize_lua_string(run_name)
            player_name = self.sanitize_lua_string(player_name)
            
            # Determine output directory based on OS
            if platform.system() == "Windows":
                # Use expandvars to handle %USERNAME%
                output_dir = os.path.expandvars("C:/Users/%USERNAME%/AppData/Local/Temp/soullink_events/")
            else:
                output_dir = "/tmp/soullink_events/"
            
            # Generate config
            config_content = self.config_template.format(
                timestamp=datetime.now().isoformat(),
                run_name=run_name,
                player_name=player_name,
                run_id=run_id,
                player_id=player_id,
                api_url="http://127.0.0.1:8000",
                output_dir=output_dir,
                game_version=game or "Unknown",
                region=region or "Unknown"
            )
            
            # Save to file
            if output_path is None:
                output_path = Path("client/lua/config.lua")
            
            # Validate output path
            self.validate_config_output(output_path)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(config_content)
            
            print(f"✅ Configuration generated: {output_path}")
            print(f"   Run: {run_name}")
            print(f"   Player: {player_name}")
            print(f"\n🚀 Next steps:")
            print(f"   1. Open DeSmuME")
            print(f"   2. Tools -> Lua Scripting -> New Lua Script Window")
            print(f"   3. Browse to client/lua/pokemon_tracker_v3_fixed.lua")
            print(f"   4. Click Run")
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error generating config: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate Lua configuration for SoulLink Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode (recommended):
    python generate_lua_config.py -i
    
  Direct mode with UUIDs:
    python generate_lua_config.py --run-id <UUID> --player-id <UUID>
    
  Custom output location:
    python generate_lua_config.py -i --output custom/path/config.lua
        """
    )
    parser.add_argument("--run-id", help="Run UUID (get from admin panel)")
    parser.add_argument("--player-id", help="Player UUID (get from admin panel)")
    parser.add_argument("--output", help="Output path (default: client/lua/config.lua)",
                        default="client/lua/config.lua")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Interactive mode - select from available runs/players")
    parser.add_argument("--db-path", help="Path to database (default: soullink_tracker.db)",
                        default="soullink_tracker.db")
    
    args = parser.parse_args()
    
    generator = LuaConfigGenerator(db_path=args.db_path)
    
    # Use interactive mode if specified or if UUIDs not provided
    if args.interactive or (not args.run_id or not args.player_id):
        if not args.interactive and (not args.run_id or not args.player_id):
            print("ℹ️  No UUIDs provided, entering interactive mode...")
            print()
        
        run_id, player_id = generator.interactive_setup()
    else:
        run_id, player_id = args.run_id, args.player_id
    
    success = generator.generate_config(run_id, player_id, Path(args.output))
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()