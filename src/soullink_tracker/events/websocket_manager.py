"""WebSocket connection manager for real-time updates with sequence-based broadcasting."""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from uuid import UUID
from dataclasses import dataclass

from fastapi import WebSocket

from .schemas import (
    WebSocketMessage,
    EncounterEventMessage,
    CatchResultEventMessage,
    FaintEventMessage,
    AdminOverrideEventMessage,
    RunStatusUpdateMessage,
    PlayerStatusUpdateMessage,
    SoulLinkUpdateMessage,
)
from ..core.enums import EncounterMethod, EncounterStatus
from ..utils.logging_config import get_logger, log_exception

logger = get_logger('websocket')


@dataclass
class WebSocketConnection:
    """Enhanced WebSocket connection with metadata."""

    websocket: WebSocket
    run_id: UUID
    player_id: UUID
    last_ping: float
    last_sequence: int = 0  # Last sequence number sent to this connection

    def __post_init__(self):
        self.last_ping = time.time()


class WebSocketManager:
    """Enhanced manager for WebSocket connections with sequence-based broadcasting."""

    def __init__(self):
        # Dict[run_id, Dict[WebSocket, WebSocketConnection]]
        self.active_connections: Dict[UUID, Dict[WebSocket, WebSocketConnection]] = {}
        # Heartbeat interval in seconds
        self.heartbeat_interval = 30
        # Connection timeout in seconds (no pong response)
        self.connection_timeout = 60
        # Ping timeout in seconds (wait for pong)
        self.ping_timeout = 10
        # Start heartbeat task
        self._heartbeat_task = None

    async def connect(self, websocket: WebSocket, run_id: UUID, player_id: UUID):
        """Accept a WebSocket connection and add it to the run."""
        await websocket.accept()

        if run_id not in self.active_connections:
            self.active_connections[run_id] = {}

        connection = WebSocketConnection(
            websocket=websocket,
            run_id=run_id,
            player_id=player_id,
            last_ping=time.time(),
        )

        self.active_connections[run_id][websocket] = connection

        # Start heartbeat task if this is the first connection
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(
            f"WebSocket connected: player {player_id} to run {run_id}. Total connections: {len(self.active_connections[run_id])}"
        )

        # Send welcome message with heartbeat info
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection_established",
                    "data": {
                        "run_id": str(run_id),
                        "player_id": str(player_id),
                        "heartbeat_interval": self.heartbeat_interval,
                        "server_time": time.time(),
                    },
                }
            )
        )

    def register_existing_connection(self, websocket: WebSocket, run_id: UUID, player_id: UUID):
        """Register an already-accepted WebSocket connection."""
        if run_id not in self.active_connections:
            self.active_connections[run_id] = {}

        connection = WebSocketConnection(
            websocket=websocket,
            run_id=run_id,
            player_id=player_id,
            last_ping=time.time(),
        )

        self.active_connections[run_id][websocket] = connection

        # Start heartbeat task if this is the first connection
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(
            f"WebSocket registered: player {player_id} to run {run_id}. Total connections: {len(self.active_connections[run_id])}"
        )

    def disconnect(self, websocket: WebSocket, run_id: UUID):
        """Remove a WebSocket connection from the run."""
        if (
            run_id in self.active_connections
            and websocket in self.active_connections[run_id]
        ):
            connection = self.active_connections[run_id][websocket]
            del self.active_connections[run_id][websocket]

            # Clean up empty run connections
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]

            logger.info(
                f"WebSocket disconnected: player {connection.player_id} from run {run_id}"
            )

            # Stop heartbeat task if no connections remain
            if not self.active_connections and self._heartbeat_task:
                self._heartbeat_task.cancel()
                self._heartbeat_task = None

    async def broadcast_to_run(
        self,
        run_id: UUID,
        message: WebSocketMessage,
        sequence_number: Optional[int] = None,
    ):
        """Broadcast a message to all connections in a run with sequence tracking."""
        if run_id not in self.active_connections:
            return

        connections = dict(
            self.active_connections[run_id]
        )  # Avoid mutation during iteration
        message_data = (
            message.model_dump() if hasattr(message, "model_dump") else message.dict()
        )

        # Add sequence number if provided
        if sequence_number is not None:
            message_data["sequence_number"] = sequence_number
            message_data["server_time"] = time.time()

        message_json = json.dumps(message_data, default=str)

        # Track connections to remove if they fail
        failed_connections = []

        for websocket, connection in connections.items():
            try:
                # Update last sequence sent to this connection
                if sequence_number is not None:
                    connection.last_sequence = sequence_number

                await websocket.send_text(message_json)

            except Exception as e:
                logger.warning(
                    f"Failed to send message to WebSocket (player {connection.player_id}): {e}"
                )
                failed_connections.append(websocket)

        # Remove failed connections
        for websocket in failed_connections:
            self.disconnect(websocket, run_id)

    async def broadcast_with_sequence_filter(
        self,
        run_id: UUID,
        message: WebSocketMessage,
        sequence_number: int,
        min_sequence: Optional[int] = None,
    ):
        """Broadcast only to connections that need this sequence number."""
        if run_id not in self.active_connections:
            return

        connections = dict(self.active_connections[run_id])
        message_data = (
            message.model_dump() if hasattr(message, "model_dump") else message.dict()
        )
        message_data["sequence_number"] = sequence_number
        message_data["server_time"] = time.time()

        message_json = json.dumps(message_data, default=str)
        failed_connections = []

        for websocket, connection in connections.items():
            # Only send if connection needs this sequence
            if min_sequence is None or connection.last_sequence < sequence_number:
                try:
                    connection.last_sequence = sequence_number
                    await websocket.send_text(message_json)
                except Exception as e:
                    logger.warning(
                        f"Failed to send message to WebSocket (player {connection.player_id}): {e}"
                    )
                    failed_connections.append(websocket)

        # Remove failed connections
        for websocket in failed_connections:
            self.disconnect(websocket, run_id)

    async def send_catch_up_messages(
        self, websocket: WebSocket, run_id: UUID, events_data: List[Dict[str, Any]]
    ):
        """Send catch-up messages to a specific connection."""
        if (
            run_id not in self.active_connections
            or websocket not in self.active_connections[run_id]
        ):
            return

        connection = self.active_connections[run_id][websocket]

        try:
            # Send catch-up header
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "catch_up_start",
                        "data": {
                            "total_events": len(events_data),
                            "server_time": time.time(),
                        },
                    }
                )
            )

            # Send each event
            for event_data in events_data:
                # Update connection's last sequence
                if "sequence_number" in event_data:
                    connection.last_sequence = max(
                        connection.last_sequence, event_data["sequence_number"]
                    )

                await websocket.send_text(json.dumps(event_data, default=str))

            # Send catch-up complete
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "catch_up_complete",
                        "data": {
                            "events_sent": len(events_data),
                            "current_sequence": connection.last_sequence,
                            "server_time": time.time(),
                        },
                    }
                )
            )

        except Exception as e:
            logger.error(
                f"Failed to send catch-up messages to player {connection.player_id}: {e}"
            )
            self.disconnect(websocket, run_id)

    async def _heartbeat_loop(self):
        """Background task to send heartbeat pings to all connections."""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                await self._send_heartbeats()
        except asyncio.CancelledError:
            logger.info("Heartbeat task cancelled")
        except Exception as e:
            logger.error(f"Heartbeat task error: {e}")

    async def _send_heartbeats(self):
        """Send ping messages to all active connections with timeout detection."""
        current_time = time.time()
        failed_connections = []
        timeout_connections = []

        for run_id, connections in self.active_connections.items():
            for websocket, connection in dict(connections).items():
                # Check if connection has timed out (no activity for too long)
                if current_time - connection.last_ping > self.connection_timeout:
                    logger.warning(
                        f"WebSocket connection timeout for player {connection.player_id} "
                        f"(last ping: {current_time - connection.last_ping:.1f}s ago)"
                    )
                    timeout_connections.append((websocket, run_id))
                    continue

                try:
                    # Send ping with timeout info
                    ping_message = {
                        "type": "ping",
                        "data": {
                            "server_time": current_time,
                            "last_sequence": connection.last_sequence,
                            "timeout_seconds": self.ping_timeout,
                        },
                    }
                    await websocket.send_text(json.dumps(ping_message))
                    connection.last_ping = current_time

                except Exception as e:
                    logger.warning(
                        f"Failed to ping WebSocket (player {connection.player_id}): {e}"
                    )
                    failed_connections.append((websocket, run_id))

        # Clean up failed and timed-out connections
        for websocket, run_id in failed_connections + timeout_connections:
            try:
                await websocket.close(code=1001, reason="Connection timeout or ping failure")
            except Exception:
                pass  # Connection might already be closed
            self.disconnect(websocket, run_id)

    def get_connection_count(self, run_id: UUID) -> int:
        """Get the number of active connections for a run."""
        return len(self.active_connections.get(run_id, {}))

    def get_total_connections(self) -> int:
        """Get the total number of active connections across all runs."""
        return sum(len(connections) for connections in self.active_connections.values())

    def get_connection_info(self, run_id: UUID) -> List[Dict[str, Any]]:
        """Get detailed info about connections for a run."""
        if run_id not in self.active_connections:
            return []

        info = []
        for websocket, connection in self.active_connections[run_id].items():
            info.append(
                {
                    "player_id": str(connection.player_id),
                    "last_sequence": connection.last_sequence,
                    "last_ping": connection.last_ping,
                    "connected_seconds": time.time() - connection.last_ping,
                }
            )

        return info


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
    rod_kind: str = None,
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
        rod_kind=rod_kind,
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_catch_result_event(
    manager: WebSocketManager,
    run_id: UUID,
    player_id: UUID,
    encounter_ref: dict,
    status: str,
):
    """Broadcast a catch result event to all connections."""
    message = CatchResultEventMessage(
        run_id=run_id, player_id=player_id, encounter_ref=encounter_ref, status=status
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_faint_event(
    manager: WebSocketManager,
    run_id: UUID,
    player_id: UUID,
    pokemon_key: str,
    party_index: int,
):
    """Broadcast a faint event to all connections."""
    message = FaintEventMessage(
        run_id=run_id,
        player_id=player_id,
        pokemon_key=pokemon_key,
        party_index=party_index,
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_admin_override_event(
    manager: WebSocketManager, run_id: UUID, action: str, details: dict
):
    """Broadcast an admin override event to all connections."""
    message = AdminOverrideEventMessage(run_id=run_id, action=action, details=details)
    await manager.broadcast_to_run(run_id, message)


async def broadcast_run_status_update(
    manager: WebSocketManager, run_id: UUID, status: str, details: dict = None
):
    """Broadcast a run status update to all connections."""
    message = RunStatusUpdateMessage(run_id=run_id, status=status, details=details)
    await manager.broadcast_to_run(run_id, message)


async def broadcast_player_status_update(
    manager: WebSocketManager,
    run_id: UUID,
    player_id: UUID,
    status: str,
    details: dict = None,
):
    """Broadcast a player status update to all connections."""
    message = PlayerStatusUpdateMessage(
        run_id=run_id, player_id=player_id, status=status, details=details
    )
    await manager.broadcast_to_run(run_id, message)


async def broadcast_soul_link_update(
    manager: WebSocketManager,
    run_id: UUID,
    link_id: UUID,
    route_id: int,
    action: str,
    members: list,
):
    """Broadcast a soul link update to all connections."""
    message = SoulLinkUpdateMessage(
        run_id=run_id,
        link_id=link_id,
        route_id=route_id,
        action=action,
        members=members,
    )
    await manager.broadcast_to_run(run_id, message)
