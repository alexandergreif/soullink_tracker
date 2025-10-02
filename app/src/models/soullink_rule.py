"""SoulinkRule entity model for duplicate species enforcement.

This module defines the Pydantic model for tracking which Pokemon species have
been caught by players, enforcing the core Soullink rule: once a species is
caught by any player, no other player can catch that species (except legendaries).
"""

from pydantic import BaseModel, Field


class SoulinkRule(BaseModel):
    """Represents a Soullink rule entry for duplicate species prevention.

    Each entry records which player caught a specific Pokemon species first.
    The database enforces UNIQUE constraint on species_id to prevent duplicates.
    Legendary Pokemon are exempt from this rule and are not inserted.
    """

    species_id: int = Field(
        ...,
        ge=1,
        le=493,
        strict=True,
        description="National Pokedex number (Gen 4 range: 1-493). UNIQUE in database."
    )
    caught_by_player: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Player identifier who caught this species first"
    )
    caught_at: str = Field(
        ...,
        description="ISO 8601 timestamp when species was first caught (UTC preferred)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "species_id": 25,
                    "caught_by_player": "Alice",
                    "caught_at": "2025-10-01T14:30:52Z"
                },
                {
                    "species_id": 143,
                    "caught_by_player": "Bob",
                    "caught_at": "2025-10-01T16:22:15Z"
                }
            ]
        }
    }
