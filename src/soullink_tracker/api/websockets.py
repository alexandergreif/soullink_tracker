"""WebSocket API endpoints for real-time updates."""

import asyncio
import json
import time
import uuid
from uuid import UUID

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    Query,
    HTTPException,
)
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import Run
from ..auth.dependencies import get_current_player_from_token
from ..events.websocket_manager import websocket_manager
from ..utils.logging_config import get_logger

logger = get_logger('websocket')

router = APIRouter(prefix="/v1/ws", tags=["websockets"])


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    run_id: UUID = Query(..., description="Run ID for the WebSocket connection"),
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time updates for a specific run.

    **Requires Bearer token authentication via message-based auth.**

    Clients can connect to this endpoint to receive real-time updates
    about encounters, catches, faints, and other game events.

    Authentication flow:
    1. Connect to WebSocket without token in URL
    2. Send {"type": "auth", "token": "bearer_token"} as first message within 5 seconds
    3. Server validates and responds with success/failure
    4. Connection closes with 4001 if auth fails or times out

    Example usage in JavaScript:
    ```javascript
    const ws = new WebSocket('ws://localhost:9000/v1/ws?run_id={run_id}');
    ws.onopen = function() {
        ws.send(JSON.stringify({"type": "auth", "token": bearer_token}));
    };
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log('Received:', data.type, data.data);
    };
    ```
    """
    # Accept WebSocket connection first, then handle authentication via messages
    logger.info(f"WebSocket connection attempt: run_id={run_id}")

    await websocket.accept()

    # Initialize variables for authentication
    player = None
    authenticated = False
    auth_timeout = 5.0  # 5 seconds timeout for authentication

    try:
        # Send authentication required message
        await websocket.send_text(
            json.dumps(
                {
                    "type": "auth_required",
                    "data": {
                        "message": "Please send authentication token within 5 seconds",
                        "timeout_seconds": auth_timeout,
                        "format": "{'type': 'auth', 'token': 'your_bearer_token'}",
                    },
                    "timestamp": time.time(),
                }
            )
        )

        # Wait for authentication message with timeout (increased to 10 seconds)
        auth_timeout = 10.0  # Increase timeout for slower connections
        max_auth_attempts = 3
        auth_attempts = 0
        start_time = time.time()
        while time.time() - start_time < auth_timeout and not authenticated and auth_attempts < max_auth_attempts:
            try:
                # Receive authentication message with short timeout to allow checking time
                auth_data = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
                auth_attempts += 1

                try:
                    auth_message = json.loads(auth_data)

                    if auth_message.get("type") == "auth":
                        token = auth_message.get("token")

                        if not token or token.strip() == "":
                            logger.warning(
                                "WebSocket authentication failed: Empty token in auth message"
                            )
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "auth_failed",
                                        "data": {"reason": "Empty or missing token"},
                                        "timestamp": time.time(),
                                    }
                                )
                            )
                            await websocket.close(
                                code=4001, reason="Empty authentication token"
                            )
                            return

                        # Authenticate the player using token
                        try:
                            player = get_current_player_from_token(token.strip(), db)

                            # Verify the run exists
                            run = db.query(Run).filter(Run.id == run_id).first()
                            if not run:
                                logger.warning(
                                    f"WebSocket authentication failed: Run {run_id} not found"
                                )
                                await websocket.send_text(
                                    json.dumps(
                                        {
                                            "type": "auth_failed",
                                            "data": {"reason": "Run not found"},
                                            "timestamp": time.time(),
                                        }
                                    )
                                )
                                await websocket.close(code=4004, reason="Run not found")
                                return

                            # Verify player belongs to the requested run
                            if player.run_id != run_id:
                                logger.warning(
                                    f"WebSocket authentication failed: Player {player.id} not authorized for run {run_id}"
                                )
                                await websocket.send_text(
                                    json.dumps(
                                        {
                                            "type": "auth_failed",
                                            "data": {
                                                "reason": "Player not authorized for this run"
                                            },
                                            "timestamp": time.time(),
                                        }
                                    )
                                )
                                await websocket.close(
                                    code=4003,
                                    reason="Player not authorized for this run",
                                )
                                return

                            # Authentication successful
                            authenticated = True
                            logger.info(
                                f"WebSocket authentication successful: player_id={player.id}, player_name={player.name}"
                            )

                            # Send success message
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "auth_success",
                                        "data": {
                                            "player_id": str(player.id),
                                            "player_name": player.name,
                                            "run_id": str(run_id),
                                        },
                                        "timestamp": time.time(),
                                    }
                                )
                            )
                            break

                        except HTTPException as auth_error:
                            logger.warning(
                                f"WebSocket authentication failed: {auth_error.detail}"
                            )
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "auth_failed",
                                        "data": {"reason": auth_error.detail},
                                        "timestamp": time.time(),
                                    }
                                )
                            )
                            await websocket.close(
                                code=4001,
                                reason=f"Authentication failed: {auth_error.detail}",
                            )
                            return
                    else:
                        logger.warning(
                            f"WebSocket: Expected auth message, got: {auth_message.get('type', 'unknown')}"
                        )
                        # Continue waiting for auth message

                except json.JSONDecodeError:
                    logger.warning(
                        f"WebSocket: Received non-JSON auth data: {auth_data}"
                    )
                    # Continue waiting for proper auth message

            except asyncio.TimeoutError:
                # Continue waiting, don't increment attempts for timeouts
                continue
            except Exception as recv_error:
                auth_attempts += 1
                logger.warning(f"WebSocket: Error receiving auth message (attempt {auth_attempts}): {recv_error}")
                # Continue waiting or timeout will handle it

        # Check if authentication was successful
        if not authenticated:
            logger.warning(
                f"WebSocket authentication timeout after {auth_timeout} seconds"
            )
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "auth_timeout",
                        "data": {
                            "reason": "Authentication timeout - no valid token received within 5 seconds"
                        },
                        "timestamp": time.time(),
                    }
                )
            )
            await websocket.close(code=4001, reason="Authentication timeout")
            return

    except Exception as e:
        logger.error(
            f"WebSocket authentication failed with unexpected error: {e}", exc_info=True
        )
        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "auth_error",
                        "data": {"reason": "Internal authentication error"},
                        "timestamp": time.time(),
                    }
                )
            )
            await websocket.close(code=4001, reason="Authentication error")
        except Exception:
            pass
        return

    # Connect to the WebSocket manager with player info (websocket already accepted)
    # Use the manager's register method for proper initialization
    websocket_manager.register_existing_connection(websocket, run_id, player.id)
    logger.info(f"WebSocket connected: player {player.name} in run {run_id}")

    # Send welcome message after successful authentication
    await websocket.send_text(
        json.dumps(
            {
                "type": "connection_established",
                "data": {
                    "run_id": str(run_id),
                    "player_id": str(player.id),
                    "player_name": player.name,
                    "server_time": time.time(),
                    "connection_id": str(uuid.uuid4()),  # For debugging
                },
                "timestamp": time.time(),
            },
            default=str,
        )
    )

    try:
        # Keep the connection alive and handle incoming messages
        while True:
            try:
                # We mainly broadcast to clients, but we can handle incoming messages too
                # Add timeout to prevent hanging connections
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keep-alive ping if no message received for 30 seconds
                await websocket.send_text(json.dumps({
                    "type": "keep_alive",
                    "data": {"server_time": time.time()}
                }))
                continue
            except Exception as msg_error:
                logger.warning(f"WebSocket message error for player {player.name}: {msg_error}")
                # Try to send error response
                try:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "data": {"message": "Message processing error", "server_time": time.time()}
                    }))
                except Exception:
                    # If we can't send error response, connection is broken
                    break
                continue

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

                elif message_type == "ping":
                    # Handle ping request - reply with pong
                    logger.debug(f"Received ping from player {player.name}")
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "pong",
                                "data": {
                                    "server_time": time.time(),
                                },
                            }
                        )
                    )

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


@router.websocket("/legacy")
async def websocket_endpoint_legacy(
    websocket: WebSocket,
    run_id: UUID = Query(..., description="Run ID for the WebSocket connection"),
    token: str = Query(..., description="Bearer authentication token"),
    db: Session = Depends(get_db),
):
    """
    Legacy WebSocket endpoint with query parameter authentication.

    **DEPRECATED**: This endpoint is deprecated and will be removed in a future version.
    Use the main endpoint with message-based authentication instead.

    **Security Warning**: Tokens in URLs are logged and cached, making them less secure.
    """
    logger.warning(
        f"Legacy WebSocket endpoint used for run {run_id} - consider upgrading to message-based auth"
    )

    # Enhanced authentication with detailed logging
    logger.info(f"Legacy WebSocket connection attempt: run_id={run_id}")

    try:
        # Validate token is present and not empty
        if not token or token.strip() == "" or token == "missing":
            logger.warning(
                f"Legacy WebSocket authentication failed: Empty or missing token (received: '{token}')"
            )
            await websocket.close(code=4001, reason="Missing authentication token")
            return

        # Authenticate the player using session token with Bearer token fallback
        try:
            # Use the updated authentication method that supports JWT, session, and legacy Bearer tokens
            player = get_current_player_from_token(token.strip(), db)
            logger.info(
                f"Legacy WebSocket authentication successful: player_id={player.id}, player_name={player.name}"
            )
        except HTTPException as auth_error:
            logger.warning(
                f"Legacy WebSocket authentication failed: {auth_error.detail}"
            )
            raise auth_error

        # Verify the run exists
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            logger.warning(
                f"Legacy WebSocket authentication failed: Run {run_id} not found"
            )
            await websocket.close(code=4004, reason="Run not found")
            return

        # Verify player belongs to the requested run
        if player.run_id != run_id:
            logger.warning(
                f"Legacy WebSocket authentication failed: Player {player.id} not authorized for run {run_id} (belongs to {player.run_id})"
            )
            await websocket.close(
                code=4003, reason="Player not authorized for this run"
            )
            return

    except HTTPException as e:
        logger.warning(
            f"Legacy WebSocket authentication failed (HTTP {e.status_code}): {e.detail}"
        )
        await websocket.close(code=4001, reason=f"Authentication failed: {e.detail}")
        return
    except Exception as e:
        logger.error(
            f"Legacy WebSocket authentication failed with unexpected error: {e}",
            exc_info=True,
        )
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # Connect to the WebSocket manager with player info
    await websocket_manager.connect(websocket, run_id, player.id)
    logger.info(f"Legacy WebSocket connected: player {player.name} in run {run_id}")

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

                elif message_type == "ping":
                    # Handle ping request - reply with pong
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "data": {"server_time": time.time()}
                    }))
                    logger.debug(f"Sent pong to player {player.name}")

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
        logger.info(
            f"Legacy WebSocket client {player.name} disconnected from run {run_id}"
        )
    except Exception as e:
        logger.error(
            f"Legacy WebSocket error for player {player.name} in run {run_id}: {e}"
        )
    finally:
        websocket_manager.disconnect(websocket, run_id)


# Legacy endpoint comment - kept for reference
# The above legacy endpoint maintains backward compatibility but will be removed in a future version
