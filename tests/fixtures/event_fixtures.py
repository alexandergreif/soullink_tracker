"""
Comprehensive test fixtures for all event types in the SoulLink Tracker.

This module provides factories and fixtures for creating realistic test data
covering all event types, encounter methods, and edge cases.
"""

import json
import random
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum


class EventType(str, Enum):
    """Event types matching the API schema."""
    ENCOUNTER = "encounter"
    CATCH_RESULT = "catch_result"
    FAINT = "faint"
    PARTY_UPDATE = "party_update"
    BLACKOUT = "blackout"
    EVOLUTION = "evolution"
    TRADE = "trade"
    NICKNAME = "nickname"


class EncounterMethod(str, Enum):
    """Encounter methods matching the API schema."""
    GRASS = "grass"
    SURF = "surf"
    FISH = "fish"
    STATIC = "static"
    GIFT = "gift"
    ROCK_SMASH = "rock_smash"
    HEADBUTT = "headbutt"
    UNKNOWN = "unknown"


class RodKind(str, Enum):
    """Fishing rod types."""
    OLD = "old"
    GOOD = "good"
    SUPER = "super"


class CatchStatus(str, Enum):
    """Catch result statuses."""
    CAUGHT = "caught"
    FLED = "fled"
    KO = "ko"
    FAILED = "failed"


@dataclass
class EventFixture:
    """Base class for event fixtures."""
    run_id: str
    player_id: str
    type: EventType = EventType.ENCOUNTER  # Will be overridden by subclasses
    time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    idempotency_key: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Remove idempotency_key from event data (it's a header)
        data.pop("idempotency_key", None)
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class EncounterFixture(EventFixture):
    """Encounter event fixture."""
    route_id: int = 31
    species_id: int = 25  # Pikachu
    family_id: int = 25
    level: int = 5
    shiny: bool = False
    method: EncounterMethod = EncounterMethod.GRASS
    rod_kind: Optional[RodKind] = None
    type: EventType = field(default=EventType.ENCOUNTER)
    
    def __post_init__(self):
        """Validate fishing encounters have rod_kind."""
        if self.method == EncounterMethod.FISH and not self.rod_kind:
            self.rod_kind = RodKind.OLD  # Default to old rod
        elif self.method != EncounterMethod.FISH:
            self.rod_kind = None  # Clear rod_kind for non-fishing


@dataclass
class CatchResultFixture(EventFixture):
    """Catch result event fixture."""
    encounter_ref: Dict[str, int] = field(default_factory=lambda: {"route_id": 31, "species_id": 25})
    status: CatchStatus = CatchStatus.CAUGHT
    encounter_id: Optional[str] = None  # For V3 API
    type: EventType = field(default=EventType.CATCH_RESULT)


@dataclass
class FaintFixture(EventFixture):
    """Faint event fixture."""
    pokemon_key: str = field(default_factory=lambda: str(random.randint(10000000, 99999999)))
    party_index: Optional[int] = None
    nickname: Optional[str] = None
    species_id: Optional[int] = None
    type: EventType = field(default=EventType.FAINT)


@dataclass
class PartyUpdateFixture(EventFixture):
    """Party update event fixture."""
    party: List[Dict[str, Any]] = field(default_factory=list)
    type: EventType = field(default=EventType.PARTY_UPDATE)
    
    @staticmethod
    def create_pokemon_entry(
        pokemon_key: str,
        species_id: int,
        level: int,
        nickname: Optional[str] = None,
        is_egg: bool = False
    ) -> Dict[str, Any]:
        """Create a party Pokemon entry."""
        entry = {
            "pokemon_key": pokemon_key,
            "species_id": species_id,
            "level": level,
            "is_egg": is_egg
        }
        if nickname:
            entry["nickname"] = nickname
        return entry


class EventFixtureFactory:
    """Factory for creating event fixtures with realistic data."""
    
    # Common Pokemon for testing (Gen 1-2)
    COMMON_POKEMON = [
        (16, "Pidgey", 16),
        (19, "Rattata", 19),
        (25, "Pikachu", 25),
        (129, "Magikarp", 129),
        (60, "Poliwag", 60),
        (74, "Geodude", 74),
        (41, "Zubat", 41),
        (179, "Mareep", 179),
        (161, "Sentret", 161),
        (163, "Hoothoot", 163),
    ]
    
    # Routes for HG/SS
    ROUTES = [
        (29, "Route 29"),
        (30, "Route 30"),
        (31, "Route 31"),
        (32, "Route 32"),
        (33, "Route 33"),
        (42, "Route 42"),
        (43, "Lake of Rage"),
        (1, "New Bark Town"),
        (2, "Cherrygrove City"),
        (3, "Violet City"),
    ]
    
    @classmethod
    def create_encounter(
        cls,
        run_id: str,
        player_id: str,
        route_id: Optional[int] = None,
        species_id: Optional[int] = None,
        method: Optional[EncounterMethod] = None,
        **kwargs
    ) -> EncounterFixture:
        """Create an encounter fixture with optional randomization."""
        if route_id is None:
            route_id = random.choice(cls.ROUTES)[0]
        
        if species_id is None:
            pokemon = random.choice(cls.COMMON_POKEMON)
            species_id = pokemon[0]
            family_id = pokemon[2]
        else:
            # Find family_id or use species_id as fallback
            family_id = kwargs.pop("family_id", species_id)
        
        if method is None:
            method = random.choice([EncounterMethod.GRASS, EncounterMethod.SURF, EncounterMethod.FISH])
        
        # Handle method as string if passed
        if isinstance(method, str):
            method = EncounterMethod(method)
        
        # Random level based on early-game range
        level = kwargs.pop("level", random.randint(2, 15))
        
        # Small chance of shiny
        shiny = kwargs.pop("shiny", random.random() < 0.01)
        
        return EncounterFixture(
            run_id=run_id,
            player_id=player_id,
            route_id=route_id,
            species_id=species_id,
            family_id=family_id,
            level=level,
            shiny=shiny,
            method=method,
            **kwargs
        )
    
    @classmethod
    def create_catch_result(
        cls,
        run_id: str,
        player_id: str,
        route_id: int,
        species_id: int,
        status: Optional[CatchStatus] = None,
        **kwargs
    ) -> CatchResultFixture:
        """Create a catch result fixture."""
        if status is None:
            # Weighted random status (more likely to catch)
            status = random.choices(
                [CatchStatus.CAUGHT, CatchStatus.FLED, CatchStatus.KO, CatchStatus.FAILED],
                weights=[60, 20, 10, 10],
                k=1
            )[0]
        
        return CatchResultFixture(
            run_id=run_id,
            player_id=player_id,
            encounter_ref={"route_id": route_id, "species_id": species_id},
            status=status,
            **kwargs
        )
    
    @classmethod
    def create_faint(
        cls,
        run_id: str,
        player_id: str,
        pokemon_key: Optional[str] = None,
        **kwargs
    ) -> FaintFixture:
        """Create a faint event fixture."""
        if pokemon_key is None:
            pokemon_key = str(random.randint(10000000, 99999999))
        
        return FaintFixture(
            run_id=run_id,
            player_id=player_id,
            pokemon_key=pokemon_key,
            **kwargs
        )
    
    @classmethod
    def create_party_update(
        cls,
        run_id: str,
        player_id: str,
        party_size: int = 3,
        **kwargs
    ) -> PartyUpdateFixture:
        """Create a party update fixture with random Pokemon."""
        party = []
        for i in range(party_size):
            pokemon = random.choice(cls.COMMON_POKEMON)
            party.append(PartyUpdateFixture.create_pokemon_entry(
                pokemon_key=str(random.randint(10000000, 99999999)),
                species_id=pokemon[0],
                level=random.randint(5, 20),
                nickname=pokemon[1] if random.random() < 0.3 else None
            ))
        
        return PartyUpdateFixture(
            run_id=run_id,
            player_id=player_id,
            party=party,
            **kwargs
        )
    
    @classmethod
    def create_complete_scenario(
        cls,
        run_id: str,
        player_id: str,
        num_encounters: int = 5
    ) -> List[EventFixture]:
        """Create a complete scenario with multiple related events."""
        events = []
        caught_pokemon = []
        
        # Create encounters and catch results
        for i in range(num_encounters):
            route_id = cls.ROUTES[i % len(cls.ROUTES)][0]
            pokemon = cls.COMMON_POKEMON[i % len(cls.COMMON_POKEMON)]
            
            # Create encounter
            encounter = cls.create_encounter(
                run_id=run_id,
                player_id=player_id,
                route_id=route_id,
                species_id=pokemon[0],
                family_id=pokemon[2]
            )
            events.append(encounter)
            
            # 70% chance of catch attempt
            if random.random() < 0.7:
                status = random.choices(
                    [CatchStatus.CAUGHT, CatchStatus.FLED, CatchStatus.KO],
                    weights=[50, 30, 20],
                    k=1
                )[0]
                
                catch_result = cls.create_catch_result(
                    run_id=run_id,
                    player_id=player_id,
                    route_id=route_id,
                    species_id=pokemon[0],
                    status=status
                )
                events.append(catch_result)
                
                if status == CatchStatus.CAUGHT:
                    caught_pokemon.append(pokemon)
        
        # Create party update with caught Pokemon
        if caught_pokemon:
            party = []
            for i, pokemon in enumerate(caught_pokemon[:6]):  # Max 6 in party
                party.append(PartyUpdateFixture.create_pokemon_entry(
                    pokemon_key=str(random.randint(10000000, 99999999)),
                    species_id=pokemon[0],
                    level=random.randint(5, 15),
                    nickname=pokemon[1] if random.random() < 0.3 else None
                ))
            
            party_update = PartyUpdateFixture(
                run_id=run_id,
                player_id=player_id,
                party=party
            )
            events.append(party_update)
            
            # 20% chance of a faint event for a party member
            if party and random.random() < 0.2:
                fainted_pokemon = random.choice(party)
                faint = cls.create_faint(
                    run_id=run_id,
                    player_id=player_id,
                    pokemon_key=fainted_pokemon["pokemon_key"],
                    species_id=fainted_pokemon["species_id"],
                    nickname=fainted_pokemon.get("nickname")
                )
                events.append(faint)
        
        return events


class EventFileGenerator:
    """Generate event files for testing Lua script simulation."""
    
    def __init__(self, output_dir: Path):
        """Initialize with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.event_counter = 0
    
    def write_event(self, event: EventFixture, delay_ms: int = 0) -> Path:
        """Write event to JSON file with optional delay."""
        self.event_counter += 1
        timestamp = int((datetime.now(timezone.utc).timestamp() + delay_ms/1000) * 1000)
        filename = f"event_{self.event_counter:04d}_{event.type.value}_{timestamp}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(event.to_dict(), f, indent=2)
        
        return filepath
    
    def write_batch(self, events: List[EventFixture], interval_ms: int = 100) -> List[Path]:
        """Write batch of events with intervals between them."""
        paths = []
        for i, event in enumerate(events):
            delay = i * interval_ms
            path = self.write_event(event, delay)
            paths.append(path)
        return paths
    
    def write_scenario(self, scenario_name: str, events: List[EventFixture]) -> Path:
        """Write a complete scenario to a subdirectory."""
        scenario_dir = self.output_dir / scenario_name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        
        generator = EventFileGenerator(scenario_dir)
        paths = generator.write_batch(events)
        
        # Write manifest
        manifest = {
            "scenario": scenario_name,
            "event_count": len(events),
            "files": [str(p.name) for p in paths],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        manifest_path = scenario_dir / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return scenario_dir


def create_test_fixtures(
    num_runs: int = 1,
    num_players: int = 3,
    events_per_player: int = 10
) -> Dict[str, Any]:
    """Create comprehensive test fixtures for E2E testing."""
    fixtures = {
        "runs": [],
        "players": [],
        "events": []
    }
    
    factory = EventFixtureFactory()
    
    for run_idx in range(num_runs):
        run_id = str(uuid.uuid4())
        run = {
            "id": run_id,
            "name": f"Test Run {run_idx + 1}",
            "rules_json": {
                "dupe_clause": True,
                "first_encounter_only": True,
                "soul_link": True
            }
        }
        fixtures["runs"].append(run)
        
        for player_idx in range(num_players):
            player_id = str(uuid.uuid4())
            player = {
                "id": player_id,
                "run_id": run_id,
                "name": f"Player{player_idx + 1}",
                "game": "HeartGold" if player_idx % 2 == 0 else "SoulSilver",
                "region": "EU",
                "token": f"test-token-{player_id[:8]}"
            }
            fixtures["players"].append(player)
            
            # Create events for this player
            player_events = factory.create_complete_scenario(
                run_id=run_id,
                player_id=player_id,
                num_encounters=events_per_player
            )
            
            fixtures["events"].extend([e.to_dict() for e in player_events])
    
    return fixtures


def load_fixtures_from_file(filepath: Path) -> List[Dict[str, Any]]:
    """Load fixture events from NDJSON file."""
    events = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


def save_fixtures_to_file(fixtures: List[EventFixture], filepath: Path):
    """Save fixtures to NDJSON file."""
    with open(filepath, 'w') as f:
        for fixture in fixtures:
            f.write(json.dumps(fixture.to_dict()) + '\n')