#!/usr/bin/env python3
"""
WebSocket Tail - Monitor SoulLink WebSocket broadcasts in real-time

This tool connects to the SoulLink WebSocket endpoint and displays
incoming messages in real-time, similar to `tail -f` for log files.

Usage:
  python tools/ws_tail.py --run-id <run_id> --token <token>
  python tools/ws_tail.py --run-id <run_id> --token <token> --format json
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime
from typing import Dict, Any

import websockets


class WebSocketTail:
    """Real-time WebSocket message monitor."""
    
    def __init__(self, format_mode: str = "pretty"):
        self.format_mode = format_mode
        self.message_count = 0
        self.connection_established = False
        
    async def connect_and_tail(self, ws_url: str):
        """Connect to WebSocket and tail messages indefinitely."""
        print(f"= Connecting to: {ws_url}")
        print("=á Waiting for messages... (Ctrl+C to quit)")
        print("=" * 60)
        
        try:
            async with websockets.connect(ws_url) as websocket:
                self.connection_established = True
                print(" Connected successfully\n")
                
                async for message in websocket:
                    self.message_count += 1
                    self._display_message(message)
                    
        except websockets.exceptions.ConnectionClosedError:
            print("\nL WebSocket connection closed")
        except KeyboardInterrupt:
            print("\n=K Disconnecting...")
        except Exception as e:
            print(f"\nL Error: {e}")
            
    def _display_message(self, raw_message: str):
        """Display a WebSocket message with formatting."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            # Raw message, not JSON
            print(f"[{timestamp}] RAW: {raw_message}")
            return
            
        if self.format_mode == "json":
            # Pretty JSON format
            print(f"[{timestamp}] #{self.message_count}")
            print(json.dumps(data, indent=2))
            print("-" * 40)
        else:
            # Human-readable format
            msg_type = data.get("type", "unknown")
            
            if msg_type == "connection_established":
                print(f"[{timestamp}] > Connection established")
                run_id = data.get("run_id", "unknown")
                print(f"              Run ID: {run_id}")
                
            elif msg_type == "encounter":
                seq = data.get("sequence_number", "?")
                event_data = data.get("data", {})
                species = event_data.get("species_id", "?")
                route = event_data.get("route_id", "?") 
                level = event_data.get("level", "?")
                method = event_data.get("method", "?")
                shiny = "(" if event_data.get("shiny", False) else ""
                
                print(f"[{timestamp}] <¯ Encounter #{seq} - Species {species} {shiny}")
                print(f"              Route {route}, Level {level}, Method: {method}")
                
            elif msg_type == "catch_result":
                seq = data.get("sequence_number", "?")
                event_data = data.get("data", {})
                status = event_data.get("status", "unknown")
                ref = event_data.get("encounter_ref", {})
                species = ref.get("species_id", "?")
                route = ref.get("route_id", "?")
                
                status_emoji = {
                    "caught": "",
                    "fled": "=¨", 
                    "ko": "=¥",
                    "failed": "L"
                }.get(status, "S")
                
                print(f"[{timestamp}] {status_emoji} Catch Result #{seq} - {status.upper()}")
                print(f"              Species {species} on Route {route}")
                
            elif msg_type == "faint":
                seq = data.get("sequence_number", "?")
                event_data = data.get("data", {})
                pokemon_key = event_data.get("pokemon_key", "?")
                
                print(f"[{timestamp}]    Faint #{seq} - Pokemon {pokemon_key}")
                
            else:
                # Unknown message type
                seq = data.get("sequence_number", "?")
                print(f"[{timestamp}] S {msg_type.title()} #{seq}")
                if self.format_mode == "verbose":
                    print(f"              Data: {json.dumps(data, indent=14)}")
                    
        print()  # Empty line for readability


def main():
    parser = argparse.ArgumentParser(description="WebSocket Tail for SoulLink Tracker")
    parser.add_argument("--run-id", required=True, help="Run ID to monitor")
    parser.add_argument("--token", required=True, help="Player authentication token")
    parser.add_argument("--url", default="ws://127.0.0.1:8000", help="WebSocket base URL")
    parser.add_argument("--format", choices=["pretty", "json", "verbose"], 
                       default="pretty", help="Output format")
    
    args = parser.parse_args()
    
    # Construct WebSocket URL
    ws_url = f"{args.url}/v1/ws?run_id={args.run_id}&token={args.token}"
    
    # Start monitoring
    tail = WebSocketTail(format_mode=args.format)
    try:
        asyncio.run(tail.connect_and_tail(ws_url))
    except KeyboardInterrupt:
        print("\n=K Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()