"""Models package for Soullink Tracker.

This package contains Pydantic models and reference data for the encounter
tracking system.
"""

from .encounter import Encounter
from .soullink_rule import SoulinkRule
from .species_reference import get_species_name, is_legendary, SPECIES_NAMES, LEGENDARY_SPECIES

__all__ = [
    "Encounter",
    "SoulinkRule",
    "get_species_name",
    "is_legendary",
    "SPECIES_NAMES",
    "LEGENDARY_SPECIES",
]
