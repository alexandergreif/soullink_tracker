"""SoulLink rules engine for determining encounter status and game logic.

V3-only rules engine that wraps pure functions from domain.rules.
Always uses the v3 event store for state building in the clean architecture.
"""

from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime

from ..utils.logging_config import get_logger

from .enums import EncounterStatus, EncounterMethod

# Legacy model imports removed in v3-only architecture
from ..db.models import Blocklist, Encounter, LinkMember  # Still needed for type hints
from ..domain.events import EncounterEvent
from ..domain.rules import RunState, PlayerRouteState, evaluate_encounter
from ..repositories.interfaces import RepositoryContainer


class RulesEngine:
    """Engine for SoulLink rules and game logic.

    V3-only rules engine that wraps pure functions from domain.rules.
    Always uses the v3 event store for state building.
    """

    def __init__(self, repos: RepositoryContainer):
        self.repos = repos
        self.logger = get_logger(__name__)
        self._state_cache: Dict[UUID, RunState] = {}

    async def _get_or_build_state(self, run_id: UUID) -> RunState:
        """Get cached state or build it from event store or legacy DB."""
        if run_id in self._state_cache:
            return self._state_cache[run_id]

        # v3-only architecture: always use event store
        state = await self._build_state_from_eventstore(run_id)

        self._state_cache[run_id] = state
        return state

    async def _build_state_from_eventstore(self, run_id: UUID) -> RunState:
        """Build state from v3 event store using repository."""
        try:
            # Get events from repository
            events = await self.repos.event.get_by_run_since_seq(
                run_id=run_id, since_seq=0, limit=100000
            )

            blocked_families = set()
            player_routes = {}

            # Parse events to build state
            # Note: This is simplified - in real implementation we'd need proper event deserialization
            for event in events:
                payload = event.payload_json
                
                if event.type == "encounter":
                    route_key = (UUID(payload["player_id"]), payload["route_id"])

                    # Update based on encounter status
                    if payload.get("fe_finalized", False):
                        new_state = PlayerRouteState(
                            fe_finalized=True,
                            first_encounter_family_id=payload["family_id"],
                            last_encounter_method=EncounterMethod(
                                payload["encounter_method"]
                            )
                            if payload.get("encounter_method")
                            else None,
                            last_rod_kind=payload.get("rod_kind"),
                        )
                        player_routes[route_key] = new_state

                elif event.type == "catch_result":
                    if payload.get("result") == "caught":
                        # Add caught families to blocklist
                        # Need to resolve family_id from encounter_id
                        encounter_id = UUID(payload["encounter_id"])
                        encounter = await self.repos.encounter.get_by_id(encounter_id)
                        if encounter:
                            blocked_families.add(encounter.family_id)

            return RunState(
                blocked_families=blocked_families, player_routes=player_routes
            )

        except Exception as e:
            # In v3-only architecture, event store failure is an error
            self.logger.error(
                f"Failed to build state from event store for run {run_id}: {e}"
            )
            raise

    # Legacy DB state building removed in v3-only architecture

    def _convert_encounter_to_event(
        self,
        run_id: UUID,
        player_id: UUID,
        route_id: int,
        species_id: int,
        family_id: int,
        level: Optional[int] = None,
        shiny: Optional[bool] = None,
        encounter_method: Optional[EncounterMethod] = None,
        rod_kind: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> EncounterEvent:
        """Convert legacy parameters to EncounterEvent."""
        return EncounterEvent(
            event_id=UUID(
                "00000000-0000-0000-0000-000000000000"
            ),  # Placeholder for legacy
            run_id=run_id,
            player_id=player_id,
            timestamp=timestamp or datetime.now(),
            route_id=route_id,
            species_id=species_id,
            family_id=family_id,
            level=level or 1,
            shiny=shiny or False,
            encounter_method=encounter_method or EncounterMethod.UNKNOWN,
            rod_kind=rod_kind,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False,
        )

    async def is_family_blocked(
        self, run_id: UUID, family_id: int, blocklist: List[Blocklist] = None
    ) -> bool:
        """Check if an evolution family is blocked (already caught/encountered).

        Delegates to pure function rules engine.
        """
        state = await self._get_or_build_state(run_id)
        return family_id in state.blocked_families

    async def should_skip_dupe_encounter(
        self,
        run_id: UUID,
        route_id: int,
        family_id: int,
        player_id: UUID,
        previous_encounters: List[Encounter] = None,
    ) -> bool:
        """
        Check if this encounter should be skipped as a dupe.

        Delegates to pure function rules engine with cross-player route check.
        """
        state = await self._get_or_build_state(run_id)

        # Check if family is globally blocked first
        if family_id in state.blocked_families:
            return True

        # Check cross-player route duplication
        for other_player_id, other_route_id in state.player_routes.keys():
            if (
                other_player_id != player_id
                and other_route_id == route_id
                and state.player_routes[(other_player_id, other_route_id)].fe_finalized
            ):
                # Need to check if that finalized encounter was the same family
                # Get encounters from repository instead of using previous_encounters parameter
                encounters = await self.repos.encounter.get_by_run_id(
                    run_id=run_id,
                    player_id=other_player_id,
                    route_id=route_id,
                    family_id=family_id,
                    limit=10,
                )
                
                for encounter in encounters:
                    if encounter.fe_finalized:
                        return True

        return False

    async def determine_encounter_status(
        self,
        run_id: UUID,
        route_id: int,
        family_id: int,
        player_id: UUID,
        blocklist: List[Blocklist] = None,
        previous_encounters: List[Encounter] = None,
    ) -> EncounterStatus:
        """
        Determine the status of a new encounter based on SoulLink rules.

        Delegates to pure function rules engine.
        """
        state = await self._get_or_build_state(run_id)

        # Create encounter event for pure function
        encounter_event = self._convert_encounter_to_event(
            run_id=run_id,
            player_id=player_id,
            route_id=route_id,
            species_id=0,  # Not used in status determination
            family_id=family_id,
        )

        # Use pure function
        decision = evaluate_encounter(state, encounter_event)

        # Check cross-player duplication (pure function can't see this)
        if not decision.dupes_skip:
            if await self.should_skip_dupe_encounter(
                run_id, route_id, family_id, player_id
            ):
                return EncounterStatus.DUPE_SKIP

        return decision.status

    async def can_finalize_first_encounter(
        self, run_id: UUID, family_id: int
    ) -> bool:
        """
        Check if a first encounter can be finalized.

        Delegates to pure function rules engine.
        """
        # Get blocked families from repository
        blocked_families = await self.is_family_blocked(run_id, family_id)

        # Family can be finalized if not globally blocked
        return not blocked_families

    def create_soul_link_members(
        self, link_id: UUID, encounters: List[Encounter]
    ) -> List[LinkMember]:
        """
        Create LinkMember objects for Pokemon caught on the same route.

        These Pokemon are soul-linked - if one faints, all linked Pokemon
        are marked as dead.

        Note: This method doesn't use pure functions as it's about creating
        database objects, not business logic.
        """
        return [
            LinkMember(
                link_id=link_id,
                player_id=encounter.player_id,
                encounter_id=encounter.id,
            )
            for encounter in encounters
        ]

    def should_create_soul_link(
        self, encounters: List[Encounter], route_id: int
    ) -> bool:
        """
        Determine if a soul link should be created for the given encounters.

        A soul link is created when multiple players have caught Pokemon
        on the same route.

        Note: This method uses simple filtering logic and doesn't need
        pure function delegation.
        """
        # Filter encounters for this route with CAUGHT status
        route_encounters = [
            e
            for e in encounters
            if e.route_id == route_id and e.status == EncounterStatus.CAUGHT
        ]

        # Need at least 2 different players
        unique_players = set(e.player_id for e in route_encounters)
        return len(unique_players) >= 2

    def get_linked_encounters(
        self, encounters: List[Encounter], route_id: int
    ) -> List[Encounter]:
        """
        Get all encounters that should be linked on a specific route.

        Returns encounters with CAUGHT status from different players
        on the same route.

        Note: This method uses simple filtering logic and doesn't need
        pure function delegation.
        """
        return [
            e
            for e in encounters
            if e.route_id == route_id and e.status == EncounterStatus.CAUGHT
        ]

    def clear_cache(self):
        """Clear the state cache. Useful for testing or when data changes."""
        self._state_cache.clear()

    def _invalidate_cache(self, run_id: UUID):
        """Invalidate cached state for a specific run."""
        if run_id in self._state_cache:
            del self._state_cache[run_id]
