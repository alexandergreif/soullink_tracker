"""WebSocket message schemas for real-time updates."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from ..core.enums import EncounterMethod, EncounterStatus


class WebSocketMessage(BaseModel):
    """Base WebSocket message format."""

    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class EncounterEventMessage(WebSocketMessage):
    """WebSocket message for encounter events."""

    def __init__(
        self,
        run_id: UUID,
        player_id: UUID,
        route_id: int,
        species_id: int,
        family_id: int,
        level: int,
        shiny: bool,
        method: EncounterMethod,
        status: EncounterStatus,
        rod_kind: Optional[str] = None,
        **kwargs,
    ):
        data = {
            "run_id": str(run_id),
            "player_id": str(player_id),
            "route_id": route_id,
            "species_id": species_id,
            "family_id": family_id,
            "level": level,
            "shiny": shiny,
            "method": method.value,
            "status": status.value,
            "rod_kind": rod_kind,
        }
        super().__init__(type="encounter", data=data, **kwargs)


class CatchResultEventMessage(WebSocketMessage):
    """WebSocket message for catch result events."""

    def __init__(
        self,
        run_id: UUID,
        player_id: UUID,
        encounter_ref: Dict[str, Any],
        status: str,
        **kwargs,
    ):
        data = {
            "run_id": str(run_id),
            "player_id": str(player_id),
            "encounter_ref": encounter_ref,
            "status": status,
        }
        super().__init__(type="catch_result", data=data, **kwargs)


class FaintEventMessage(WebSocketMessage):
    """WebSocket message for faint events."""

    def __init__(
        self,
        run_id: UUID,
        player_id: UUID,
        pokemon_key: str,
        party_index: int,
        **kwargs,
    ):
        data = {
            "run_id": str(run_id),
            "player_id": str(player_id),
            "pokemon_key": pokemon_key,
            "party_index": party_index,
        }
        super().__init__(type="faint", data=data, **kwargs)


class AdminOverrideEventMessage(WebSocketMessage):
    """WebSocket message for admin override events."""

    def __init__(self, run_id: UUID, action: str, details: Dict[str, Any], **kwargs):
        data = {"run_id": str(run_id), "action": action, "details": details}
        super().__init__(type="admin_override", data=data, **kwargs)


class RunStatusUpdateMessage(WebSocketMessage):
    """WebSocket message for run status updates."""

    def __init__(
        self,
        run_id: UUID,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        data = {"run_id": str(run_id), "status": status, "details": details or {}}
        super().__init__(type="run_status", data=data, **kwargs)


class PlayerStatusUpdateMessage(WebSocketMessage):
    """WebSocket message for player status updates."""

    def __init__(
        self,
        run_id: UUID,
        player_id: UUID,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        data = {
            "run_id": str(run_id),
            "player_id": str(player_id),
            "status": status,
            "details": details or {},
        }
        super().__init__(type="player_status", data=data, **kwargs)


class SoulLinkUpdateMessage(WebSocketMessage):
    """WebSocket message for soul link updates."""

    def __init__(
        self,
        run_id: UUID,
        link_id: UUID,
        route_id: int,
        action: str,  # "created", "updated", "broken"
        members: list,
        **kwargs,
    ):
        data = {
            "run_id": str(run_id),
            "link_id": str(link_id),
            "route_id": route_id,
            "action": action,
            "members": members,
        }
        super().__init__(type="soul_link", data=data, **kwargs)
