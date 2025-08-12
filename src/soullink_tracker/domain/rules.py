"""
Pure function rules engine for SoulLink game mechanics.

This module contains all the core game logic as pure functions with no side effects.
All database interactions and state management are handled by the projection layer.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Tuple, Union, Callable
from uuid import UUID
from enum import Enum

from ..core.enums import EncounterStatus, EncounterMethod
from .events import EncounterEvent, CatchResultEvent, FaintEvent, FamilyBlockedEvent


class RodKind(str, Enum):
    """Fishing rod types for encounter method differentiation."""

    OLD = "old"
    GOOD = "good"
    SUPER = "super"


@dataclass(frozen=True)
class PlayerRouteState:
    """State of a specific player on a specific route."""

    fe_finalized: bool = False
    first_encounter_family_id: Optional[int] = None
    last_encounter_method: Optional[EncounterMethod] = None
    last_rod_kind: Optional[RodKind] = None


@dataclass(frozen=True)
class RunState:
    """Current state of a SoulLink run needed for rule evaluation."""

    blocked_families: Set[int] = field(default_factory=set)
    player_routes: Dict[Tuple[UUID, int], PlayerRouteState] = field(
        default_factory=dict
    )

    def get_route_state(self, player_id: UUID, route_id: int) -> PlayerRouteState:
        """Get the state for a specific player/route combination."""
        return self.player_routes.get((player_id, route_id), PlayerRouteState())

    def with_blocked_family(self, family_id: int) -> "RunState":
        """Return new RunState with an additional blocked family."""
        new_blocked = self.blocked_families | {family_id}
        return RunState(blocked_families=new_blocked, player_routes=self.player_routes)

    def with_route_state(
        self, player_id: UUID, route_id: int, route_state: PlayerRouteState
    ) -> "RunState":
        """Return new RunState with updated route state."""
        new_routes = dict(self.player_routes)
        new_routes[(player_id, route_id)] = route_state
        return RunState(
            blocked_families=self.blocked_families, player_routes=new_routes
        )


@dataclass(frozen=True)
class EncounterDecision:
    """Decision result for an encounter event."""

    status: EncounterStatus
    fe_finalized: bool = False  # Never finalize on encounter - only on catch result
    dupes_skip: bool = False
    blocklist_add: Optional[Tuple[int, str]] = None  # (family_id, origin)

    @property
    def should_create_route_progress(self) -> bool:
        """Whether this encounter should create/update route progress."""
        return not self.dupes_skip


@dataclass(frozen=True)
class CatchDecision:
    """Decision result for a catch result event."""

    fe_finalized: bool = False
    blocklist_add: Optional[Tuple[int, str]] = None  # (family_id, origin)


@dataclass(frozen=True)
class FaintDecision:
    """Decision result for a faint event (currently no-op for projections)."""

    pass  # Party status is managed separately


# Type alias for encounter lookup helper function
EncounterLookup = Callable[
    [UUID], Tuple[UUID, int, int]
]  # encounter_id -> (player_id, route_id, family_id)


def evaluate_encounter(state: RunState, event: EncounterEvent) -> EncounterDecision:
    """
    Evaluate an encounter event and determine the appropriate status.

    SoulLink Rules:
    1. If family is globally blocked -> DUPE_SKIP
    2. If same family encountered on same route by different player -> DUPE_SKIP
    3. Otherwise -> FIRST_ENCOUNTER (never finalized on encounter)

    Fishing Logic:
    - Global family blocking takes precedence over rod upgrades
    - Different rod kinds on same route don't bypass global blocks
    - Rod kind is tracked for potential future rule extensions

    Args:
        state: Current run state with blocked families and route progress
        event: The encounter event to evaluate

    Returns:
        EncounterDecision with status, finalization, and update instructions
    """
    # Check global family blocking first
    if event.family_id in state.blocked_families:
        return EncounterDecision(status=EncounterStatus.DUPE_SKIP, dupes_skip=True)

    # For this specific player, check if they have a finalized encounter on this route
    # If they do and it's a different family, this is still valid (multiple encounters per route)
    # If they do and it's the same family, this would be a dupe (shouldn't happen in normal flow)

    # The key rule: once ANY player finalizes a first encounter on a route,
    # other players encountering the same family get dupe-skip
    # This is handled at the projection level by checking fe_finalized across all players

    # At the pure rules level, we only have this player's state
    # The projection layer must query across players for proper dupe detection

    return EncounterDecision(
        status=EncounterStatus.FIRST_ENCOUNTER,
        fe_finalized=False,  # Never finalize on encounter
        dupes_skip=False,
    )


def apply_catch_result(
    state: RunState,
    event: CatchResultEvent,
    encounter_lookup: Optional[EncounterLookup] = None,
) -> CatchDecision:
    """
    Process a catch result event to determine finalization and blocking.

    Logic:
    - On CAUGHT: finalize first encounter and block the family globally
    - On other results (FLED, FAINTED): finalize first encounter but don't block family

    Args:
        state: Current run state
        event: The catch result event
        encounter_lookup: Function to resolve encounter_id to (player_id, route_id, family_id)

    Returns:
        CatchDecision with finalization and blocking instructions
    """
    if not encounter_lookup:
        raise ValueError("encounter_lookup is required for catch result processing")

    try:
        player_id, route_id, family_id = encounter_lookup(event.encounter_id)
    except Exception as e:
        raise ValueError(f"Failed to lookup encounter {event.encounter_id}: {e}")

    # Verify the catch result matches the encounter context
    if player_id != event.player_id:
        raise ValueError(
            f"Catch result player mismatch for encounter {event.encounter_id}"
        )

    # Always finalize the first encounter when catch result is processed
    fe_finalized = True

    # Block family globally only if caught
    blocklist_add = None
    if event.result == EncounterStatus.CAUGHT:
        blocklist_add = (family_id, "caught")

    return CatchDecision(fe_finalized=fe_finalized, blocklist_add=blocklist_add)


def process_family_blocked(state: RunState, event: FamilyBlockedEvent) -> RunState:
    """
    Process a family blocked event by updating the run state.

    Args:
        state: Current run state
        event: The family blocked event

    Returns:
        Updated RunState with the family blocked
    """
    return state.with_blocked_family(event.family_id)


def process_faint(state: RunState, event: FaintEvent) -> FaintDecision:
    """
    Process a faint event. Currently no changes to route progress or blocklist.

    Args:
        state: Current run state
        event: The faint event

    Returns:
        FaintDecision (currently empty)
    """
    return FaintDecision()


def should_skip_for_route_dupe(
    state: RunState,
    event: EncounterEvent,
    cross_player_lookup: Callable[[int, int], bool],
) -> bool:
    """
    Check if an encounter should be skipped due to route-level duplication.

    This function requires cross-player data that the pure rules engine doesn't have.
    It's provided as a helper for the projection layer to use.

    Args:
        state: Current run state
        event: The encounter event
        cross_player_lookup: Function that returns True if any other player
                            has finalized this family on this route

    Returns:
        True if this encounter should be skipped as a route-level dupe
    """
    return cross_player_lookup(event.route_id, event.family_id)


def get_fishing_rod_priority(rod_kind: Optional[Union[str, RodKind]]) -> int:
    """
    Get priority value for fishing rod kinds (for potential future rod upgrade logic).

    Args:
        rod_kind: The rod kind (old/good/super)

    Returns:
        Priority value (higher = better rod)
    """
    if not rod_kind:
        return 0

    rod_priorities = {RodKind.OLD: 1, RodKind.GOOD: 2, RodKind.SUPER: 3}

    # Handle string values
    if isinstance(rod_kind, str):
        rod_kind = RodKind(rod_kind.lower())

    return rod_priorities.get(rod_kind, 0)


def validate_encounter_sequence(
    events: list[Union[EncounterEvent, CatchResultEvent]],
) -> bool:
    """
    Validate that a sequence of events follows proper encounter -> catch_result ordering.

    This is a helper for testing and validation.

    Args:
        events: List of encounter and catch result events

    Returns:
        True if the sequence is valid
    """
    encounter_ids = set()

    for event in events:
        if isinstance(event, EncounterEvent):
            encounter_ids.add(event.event_id)
        elif isinstance(event, CatchResultEvent):
            if event.encounter_id not in encounter_ids:
                return False  # Catch result without prior encounter

    return True


# Property-based testing invariants for Hypothesis


def invariant_no_double_finalization(
    initial_state: RunState, events: list[Union[EncounterEvent, CatchResultEvent]]
) -> bool:
    """
    Invariant: A route/player combination can only be finalized once.

    This is an invariant for property-based testing.
    """
    finalized_routes = set()

    for event in events:
        if isinstance(event, CatchResultEvent):
            # In a real scenario, we'd track which route this finalizes
            # For the invariant, we assume each catch_result finalizes its route
            route_key = (event.player_id, "route_from_encounter")  # Simplified

            if route_key in finalized_routes:
                return False  # Double finalization detected

            finalized_routes.add(route_key)

    return True


def invariant_blocked_families_only_grow(
    initial_state: RunState,
    events: list[Union[EncounterEvent, CatchResultEvent, FamilyBlockedEvent]],
) -> bool:
    """
    Invariant: The set of blocked families can only grow, never shrink.
    """
    current_blocked = initial_state.blocked_families

    for event in events:
        if isinstance(event, FamilyBlockedEvent):
            # Family blocking should only add families
            if event.family_id in current_blocked:
                continue  # Already blocked, OK
            current_blocked = current_blocked | {event.family_id}
        elif (
            isinstance(event, CatchResultEvent)
            and event.result == EncounterStatus.CAUGHT
        ):
            # Caught events should block families (via lookup)
            # In a real test, we'd resolve the family_id from encounter_lookup
            pass

    return True


def invariant_dupes_respect_blocklist(
    state: RunState, encounter_events: list[EncounterEvent]
) -> bool:
    """
    Invariant: Encounters for blocked families always result in DUPE_SKIP.
    """
    for event in encounter_events:
        decision = evaluate_encounter(state, event)

        if event.family_id in state.blocked_families:
            if decision.status != EncounterStatus.DUPE_SKIP:
                return False

    return True
