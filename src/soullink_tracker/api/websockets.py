"""WebSocket API endpoints for real-time updates."""

import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import Run
from ..events.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ws", tags=["websockets"])


@router.websocket("/{run_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    run_id: UUID,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time updates for a specific run.
    
    Clients can connect to this endpoint to receive real-time updates
    about encounters, catches, faints, and other game events.
    
    Example usage in JavaScript:
    ```javascript
    const ws = new WebSocket('ws://localhost:9000/v1/ws/{run_id}');
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log('Received:', data.type, data.data);
    };
    ```
    """
    # Verify the run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        await websocket.close(code=4004, reason="Run not found")
        return
    
    # Connect to the WebSocket manager
    await websocket_manager.connect(websocket, run_id)
    
    try:
        # Keep the connection alive and handle incoming messages
        while True:
            # We mainly broadcast to clients, but we can handle incoming messages too
            data = await websocket.receive_text()
            
            # For now, we just log incoming messages
            # In the future, we could handle client-to-server messages here
            logger.info(f"Received WebSocket message from client: {data}")
            
            # Echo back a confirmation (optional)
            await websocket.send_text(f"Server received: {data}")
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from run {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id}: {e}")
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
        "connections_per_run": run_stats
    }


# Optional: WebSocket endpoint with authentication
# This could be used for admin-only connections or player-specific updates
@router.websocket("/authenticated/{run_id}")
async def authenticated_websocket_endpoint(
    websocket: WebSocket,
    run_id: UUID,
    token: str = Query(..., description="JWT authentication token"),
    db: Session = Depends(get_db)
):
    """
    Authenticated WebSocket endpoint for real-time updates.
    
    Requires a valid JWT token as a query parameter.
    This endpoint could be used for player-specific updates
    or admin-only functionality.
    
    Example usage:
    ```javascript
    const ws = new WebSocket('ws://localhost:9000/v1/ws/authenticated/{run_id}?token={jwt_token}');
    ```
    """
    try:
        # Verify the JWT token
        from ..auth.security import verify_token
        from ..auth.dependencies import get_current_player_from_token
        
        player = get_current_player_from_token(token, db)
        
        # Verify the run exists and player belongs to it
        if player.run_id != run_id:
            await websocket.close(code=4003, reason="Player not in this run")
            return
            
    except Exception as e:
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    # Connect to the WebSocket manager
    await websocket_manager.connect(websocket, run_id)
    logger.info(f"Authenticated WebSocket connected: player {player.name} in run {run_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received authenticated WebSocket message from {player.name}: {data}")
            
            # Handle authenticated client messages here
            # Could include player-specific commands or actions
            
    except WebSocketDisconnect:
        logger.info(f"Authenticated WebSocket client {player.name} disconnected from run {run_id}")
    except Exception as e:
        logger.error(f"Authenticated WebSocket error for player {player.name} in run {run_id}: {e}")
    finally:
        websocket_manager.disconnect(websocket, run_id)