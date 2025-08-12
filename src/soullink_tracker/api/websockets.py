"""WebSocket API endpoints for real-time updates."""

import json
import logging
import time
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import Run
from ..auth.dependencies import get_current_player_from_token
from ..events.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ws", tags=["websockets"])


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    run_id: UUID = Query(..., description="Run ID for the WebSocket connection"),
    token: str = Query(..., description="Bearer authentication token"),
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time updates for a specific run.

    **Requires Bearer token authentication via query parameter.**

    Clients can connect to this endpoint to receive real-time updates
    about encounters, catches, faints, and other game events.

    Example usage in JavaScript:
    ```javascript
    const ws = new WebSocket('ws://localhost:9000/v1/ws?run_id={run_id}&token={bearer_token}');
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log('Received:', data.type, data.data);
    };
    ```
    """
    try:
        # Authenticate the player using Bearer token
        player = get_current_player_from_token(token, db)

        # Verify the run exists
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            await websocket.close(code=4004, reason="Run not found")
            return

        # Verify player belongs to the requested run
        if player.run_id != run_id:
            await websocket.close(
                code=4003, reason="Player not authorized for this run"
            )
            return

    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # Connect to the WebSocket manager with player info
    await websocket_manager.connect(websocket, run_id, player.id)
    logger.info(f"WebSocket connected: player {player.name} in run {run_id}")

    try:
        # Keep the connection alive and handle incoming messages
        while True:
            # We mainly broadcast to clients, but we can handle incoming messages too
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                message_type = message.get("type", "unknown")

                if message_type == "pong":
                    # Handle pong response to our ping
                    logger.debug(f"Received pong from player {player.name}")
                    # Update last_ping time in the connection
                    if (
                        run_id in websocket_manager.active_connections
                        and websocket in websocket_manager.active_connections[run_id]
                    ):
                        websocket_manager.active_connections[run_id][
                            websocket
                        ].last_ping = time.time()

                elif message_type == "catch_up_request":
                    # Handle catch-up request for missed events
                    since_seq = message.get("data", {}).get("since_seq", 0)
                    logger.info(
                        f"Player {player.name} requesting catch-up since sequence {since_seq}"
                    )

                    # For now, send acknowledgment - actual catch-up is handled via REST API
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "catch_up_response",
                                "data": {
                                    "message": f"Use REST API: GET /v1/events?run_id={run_id}&since_seq={since_seq}",
                                    "rest_endpoint": f"/v1/events?run_id={run_id}&since_seq={since_seq}",
                                },
                            }
                        )
                    )

                else:
                    # Log other message types for debugging
                    logger.info(
                        f"Received WebSocket message from player {player.name}: {message_type}"
                    )

                    # Echo back a confirmation
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "message_received",
                                "data": {
                                    "original_type": message_type,
                                    "server_time": time.time(),
                                },
                            }
                        )
                    )

            except json.JSONDecodeError:
                # Handle non-JSON messages
                logger.warning(
                    f"Received non-JSON message from player {player.name}: {data}"
                )
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "data": {
                                "message": "Invalid JSON format",
                                "server_time": time.time(),
                            },
                        }
                    )
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket client {player.name} disconnected from run {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error for player {player.name} in run {run_id}: {e}")
    finally:
        websocket_manager.disconnect(websocket, run_id)


@router.get("/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.

    Returns information about active connections across all runs.
    """
    total_connections = websocket_manager.get_total_connections()
    active_runs = len(websocket_manager.active_connections)

    run_stats = {}
    for run_id, connections in websocket_manager.active_connections.items():
        run_stats[str(run_id)] = len(connections)

    return {
        "total_connections": total_connections,
        "active_runs": active_runs,
        "connections_per_run": run_stats,
    }


# Legacy endpoint - deprecated in favor of the main authenticated endpoint above
# Kept for backward compatibility but will be removed in a future version
