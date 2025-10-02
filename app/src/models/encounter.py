"""Encounter entity model for Pokemon encounter tracking.

This module defines the Pydantic model for Pokemon encounters detected by the
DeSmuME Lua script and processed through the Soullink Tracker pipeline.
"""

from typing import Optional
from pydantic import BaseModel, Field, model_validator


class Encounter(BaseModel):
    """Represents a single wild Pokemon encounter event.

    Fields are validated according to data-model.md specifications and
    contracts/encounter_json_schema.json.
    """

    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp with timezone (UTC preferred)"
    )
    player_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Player identifier configured in Lua script"
    )
    species_id: int = Field(
        ...,
        ge=1,
        le=493,
        description="National Pokedex number (Gen 4 range: 1-493)"
    )
    species_name: Optional[str] = Field(
        None,
        description="Pokemon species name (optional, can be recalculated from species_id)"
    )
    level: int = Field(
        ...,
        ge=1,
        le=100,
        description="Pokemon level when encountered"
    )
    current_hp: int = Field(
        ...,
        ge=0,
        description="Current HP stat (can be 0 if fainted during detection)"
    )
    max_hp: int = Field(
        ...,
        ge=1,
        description="Maximum HP stat"
    )
    location_id: Optional[int] = Field(
        None,
        description="HGSS map/route ID (optional, null if address unknown)"
    )
    location_name: Optional[str] = Field(
        None,
        description="Human-readable location name"
    )
    encounter_type: str = Field(
        ...,
        pattern="^(wild|legendary)$",
        description="Encounter classification (legendary exempt from Soullink duplicate rule)"
    )
    status: str = Field(
        ...,
        pattern="^(encountered|caught|ko|run)$",
        description="Encounter lifecycle status (initial: encountered, updated by user)"
    )
    personality_value: int = Field(
        ...,
        ge=0,
        le=4294967295,
        description="32-bit Pokemon PID (for uniqueness and shiny detection)"
    )

    @model_validator(mode='after')
    def validate_current_hp_not_exceeds_max(self):
        """Validate that current_hp does not exceed max_hp.

        This validation runs after all fields are set, ensuring
        current_hp <= max_hp constraint is enforced.
        """
        if self.current_hp > self.max_hp:
            raise ValueError(f'current_hp ({self.current_hp}) cannot exceed max_hp ({self.max_hp})')
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2025-10-01T14:30:52Z",
                    "player_name": "Alice",
                    "species_id": 25,
                    "species_name": "Pikachu",
                    "level": 12,
                    "current_hp": 35,
                    "max_hp": 35,
                    "location_id": None,
                    "location_name": "Unknown",
                    "encounter_type": "wild",
                    "status": "encountered",
                    "personality_value": 3849273841
                }
            ]
        }
    }
