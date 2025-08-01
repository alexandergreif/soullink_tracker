"""WebSocket connection manager for real-time updates."""

import json
import logging
from typing import Dict, List, Set
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from .schemas import (
    WebSocketMessage, EncounterEventMessage, CatchResultEventMessage,
    FaintEventMessage, AdminOverrideEventMessage, RunStatusUpdateMessage,
    PlayerStatusUpdateMessage, SoulLinkUpdateMessage
)
from ..core.enums import EncounterMethod, EncounterStatus

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manager for WebSocket connections and broadcasting."""
    
    def __init__(self):
        # Dict[run_id, Set[WebSocket]]
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, run_id: UUID):
        """Accept a WebSocket connection and add it to the run."""
        await websocket.accept()
        
        if run_id not in self.active_connections:
            self.active_connections[run_id] = set()
        
        self.active_connections[run_id].add(websocket)
        logger.info(f"WebSocket connected to run {run_id}. Total connections: {len(self.active_connections[run_id])}")
    
    def disconnect(self, websocket: WebSocket, run_id: UUID):
        """Remove a WebSocket connection from the run."""
        if run_id in self.active_connections:
            self.active_connections[run_id].discard(websocket)
            
            # Clean up empty sets
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
            
            logger.info(f"WebSocket disconnected from run {run_id}")
    
    async def broadcast_to_run(self, run_id: UUID, message: WebSocketMessage):
        """Broadcast a message to all connections in a run."""
        if run_id not in self.active_connections:
            return
        
        connections = self.active_connections[run_id].copy()  # Avoid mutation during iteration
        message_json = message.json()  # Use Pydantic's json() method which handles serialization
        
        # Track connections to remove if they fail
        failed_connections = set()
        
        for connection in connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                failed_connections.add(connection)
        
        # Remove failed connections
        for connection in failed_connections:
            self.disconnect(connection, run_id)
    
    def get_connection_count(self, run_id: UUID) -> int:
        """Get the number of active connections for a run."""
        return len(self.active_connections.get(run_id, set()))
    
    def get_total_connections(self) -> int:
        """Get the total number of active connections across all runs."""
        return sum(len(connections) for connections in self.active_connections.values())


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


# Broadcast helper functions for different event types

async def broadcast_encounter_event(
    manager: WebSocketManager,
    run_id: UUID,
    player_id: UUID,
    route_id: int,
    species_id: int,
    family_id: int,
    level: int,
    shiny: bool,
    method: EncounterMethod,
    status: EncounterStatus,
    rod_kind: str = None
):
    """Broadcast an encounter event to all connections."""
    message = EncounterEventMessage(
        run_id=run_id,
        player_id=player_id,
        route_id=route_id,
        species_id=species_id,
        family_id=family_id,
        level=level,
        shiny=shiny,
        method=method,
        status=status,
        rod_kind=rod_kind
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_catch_result_event(
    manager: WebSocketManager,
    run_id: UUID,
    player_id: UUID,
    encounter_ref: dict,
    status: str
):
    """Broadcast a catch result event to all connections."""
    message = CatchResultEventMessage(
        run_id=run_id,
        player_id=player_id,
        encounter_ref=encounter_ref,
        status=status
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_faint_event(
    manager: WebSocketManager,
    run_id: UUID,
    player_id: UUID,
    pokemon_key: str,
    party_index: int
):
    """Broadcast a faint event to all connections."""
    message = FaintEventMessage(
        run_id=run_id,
        player_id=player_id,
        pokemon_key=pokemon_key,
        party_index=party_index
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_admin_override_event(
    manager: WebSocketManager,
    run_id: UUID,
    action: str,
    details: dict
):
    """Broadcast an admin override event to all connections."""
    message = AdminOverrideEventMessage(
        run_id=run_id,
        action=action,
        details=details
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_run_status_update(
    manager: WebSocketManager,
    run_id: UUID,
    status: str,
    details: dict = None
):
    """Broadcast a run status update to all connections."""
    message = RunStatusUpdateMessage(
        run_id=run_id,
        status=status,
        details=details
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_player_status_update(
    manager: WebSocketManager,
    run_id: UUID,
    player_id: UUID,
    status: str,
    details: dict = None
):
    """Broadcast a player status update to all connections."""
    message = PlayerStatusUpdateMessage(
        run_id=run_id,
        player_id=player_id,
        status=status,
        details=details
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_soul_link_update(
    manager: WebSocketManager,
    run_id: UUID,
    link_id: UUID,
    route_id: int,
    action: str,
    members: list
):
    """Broadcast a soul link update to all connections."""
    message = SoulLinkUpdateMessage(
        run_id=run_id,
        link_id=link_id,
        route_id=route_id,
        action=action,
        members=members
    )
    await manager.broadcast_to_run(run_id, message)