"""SoulLink rules engine for determining encounter status and game logic."""

from typing import List, Optional
from uuid import UUID

from .enums import EncounterStatus
from ..db.models import Encounter, Blocklist, LinkMember


class RulesEngine:
    """Engine for SoulLink rules and game logic."""

    def is_family_blocked(
        self, 
        run_id: UUID, 
        family_id: int, 
        blocklist: List[Blocklist]
    ) -> bool:
        """Check if an evolution family is blocked (already caught/encountered)."""
        return any(
            entry.family_id == family_id and entry.run_id == run_id
            for entry in blocklist
        )

    def should_skip_dupe_encounter(
        self,
        run_id: UUID,
        route_id: int,
        family_id: int,
        player_id: UUID,
        previous_encounters: List[Encounter]
    ) -> bool:
        """
        Check if this encounter should be skipped as a dupe.
        
        Returns True if the same family has already been encountered
        on the same route by any player in this run.
        """
        return any(
            encounter.run_id == run_id
            and encounter.route_id == route_id
            and encounter.family_id == family_id
            and encounter.player_id != player_id  # Different player
            and encounter.fe_finalized  # First encounter was finalized
            for encounter in previous_encounters
        )

    def determine_encounter_status(
        self,
        run_id: UUID,
        route_id: int,
        family_id: int,
        player_id: UUID,
        blocklist: List[Blocklist],
        previous_encounters: List[Encounter]
    ) -> EncounterStatus:
        """
        Determine the status of a new encounter based on SoulLink rules.
        
        Rules:
        1. If family is blocked globally -> DUPE_SKIP
        2. If same family encountered on same route by different player -> DUPE_SKIP  
        3. Otherwise -> FIRST_ENCOUNTER
        """
        # Check if family is globally blocked
        if self.is_family_blocked(run_id, family_id, blocklist):
            return EncounterStatus.DUPE_SKIP
        
        # Check if this is a dupe encounter on the same route
        if self.should_skip_dupe_encounter(
            run_id, route_id, family_id, player_id, previous_encounters
        ):
            return EncounterStatus.DUPE_SKIP
        
        # This is a valid first encounter
        return EncounterStatus.FIRST_ENCOUNTER

    def can_finalize_first_encounter(
        self, 
        family_id: int, 
        blocklist: List[Blocklist]
    ) -> bool:
        """
        Check if a first encounter can be finalized.
        
        A first encounter can only be finalized if the evolution family
        hasn't been caught or encountered by any player globally.
        """
        return not any(entry.family_id == family_id for entry in blocklist)

    def create_soul_link_members(
        self, 
        link_id: UUID, 
        encounters: List[Encounter]
    ) -> List[LinkMember]:
        """
        Create LinkMember objects for Pokemon caught on the same route.
        
        These Pokemon are soul-linked - if one faints, all linked Pokemon
        are marked as dead.
        """
        return [
            LinkMember(
                link_id=link_id,
                player_id=encounter.player_id,
                encounter_id=encounter.id
            )
            for encounter in encounters
        ]

    def should_create_soul_link(
        self, 
        encounters: List[Encounter], 
        route_id: int
    ) -> bool:
        """
        Determine if a soul link should be created for the given encounters.
        
        A soul link is created when multiple players have caught Pokemon
        on the same route.
        """
        # Filter encounters for this route with CAUGHT status
        route_encounters = [
            e for e in encounters 
            if e.route_id == route_id and e.status == EncounterStatus.CAUGHT
        ]
        
        # Need at least 2 different players
        unique_players = set(e.player_id for e in route_encounters)
        return len(unique_players) >= 2

    def get_linked_encounters(
        self, 
        encounters: List[Encounter], 
        route_id: int
    ) -> List[Encounter]:
        """
        Get all encounters that should be linked on a specific route.
        
        Returns encounters with CAUGHT status from different players
        on the same route.
        """
        return [
            e for e in encounters
            if e.route_id == route_id and e.status == EncounterStatus.CAUGHT
        ]