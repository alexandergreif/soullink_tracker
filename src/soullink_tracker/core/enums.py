"""Enums for the SoulLink tracker application."""

from enum import Enum


class EncounterMethod(str, Enum):
    """Encounter methods for Pokemon."""

    GRASS = "grass"
    SURF = "surf"
    FISH = "fish"
    STATIC = "static"
    UNKNOWN = "unknown"


class RodKind(str, Enum):
    """Fishing rod types."""

    OLD = "old"
    GOOD = "good"
    SUPER = "super"


class EncounterStatus(str, Enum):
    """Status of an encounter."""

    FIRST_ENCOUNTER = "first_encounter"
    CAUGHT = "caught"
    FLED = "fled"
    KO = "ko"
    FAILED = "failed"
    DUPE_SKIP = "dupe_skip"


class GameVersion(str, Enum):
    """Pokemon game versions."""

    HEARTGOLD = "HeartGold"
    SOULSILVER = "SoulSilver"


class Region(str, Enum):
    """Game regions."""

    EU = "EU"
    US = "US"
    JP = "JP"
