"""Unit tests for database models."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from soullink_tracker.db.models import (
    Run, Player, Species, Route, Encounter, Link, LinkMember, 
    Blocklist, PartyStatus, IdempotencyKey
)
from soullink_tracker.core.enums import EncounterMethod, EncounterStatus, RodKind


@pytest.mark.unit
class TestRunModel:
    """Test the Run model."""

    def test_run_creation(self):
        """Test creating a new run."""
        run = Run(
            id=uuid4(),
            name="Test SoulLink Run",
            rules_json={"dupes_clause": True, "fishing_enabled": True},
            created_at=datetime.now(timezone.utc)
        )
        
        assert run.name == "Test SoulLink Run"
        assert run.rules_json["dupes_clause"] is True
        assert run.rules_json["fishing_enabled"] is True
        assert isinstance(run.created_at, datetime)

    def test_run_repr(self):
        """Test run string representation."""
        run = Run(name="Test Run", rules_json={})
        assert "Test Run" in str(run)


@pytest.mark.unit  
class TestPlayerModel:
    """Test the Player model."""

    def test_player_creation(self):
        """Test creating a new player."""
        run_id = uuid4()
        player = Player(
            id=uuid4(),
            run_id=run_id,
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash="hashed_token_value",
            created_at=datetime.now(timezone.utc)
        )
        
        assert player.name == "TestPlayer"
        assert player.game == "HeartGold"
        assert player.region == "EU"
        assert player.run_id == run_id

    def test_player_token_verification(self):
        """Test token verification method."""
        player = Player(
            name="Test",
            game="SoulSilver", 
            region="EU",
            token_hash="test_hash"
        )
        
        # This method should be implemented to verify tokens
        assert hasattr(player, 'verify_token')


@pytest.mark.unit
class TestSpeciesModel:
    """Test the Species model."""

    def test_species_creation(self):
        """Test creating a species."""
        species = Species(
            id=1,
            name="Bulbasaur",
            family_id=1
        )
        
        assert species.id == 1
        assert species.name == "Bulbasaur"
        assert species.family_id == 1


@pytest.mark.unit
class TestRouteModel:
    """Test the Route model."""

    def test_route_creation(self):
        """Test creating a route."""
        route = Route(
            id=31,
            label="Route 31",
            region="EU"
        )
        
        assert route.id == 31
        assert route.label == "Route 31"
        assert route.region == "EU"


@pytest.mark.unit
class TestEncounterModel:
    """Test the Encounter model."""

    def test_encounter_creation(self):
        """Test creating an encounter."""
        encounter = Encounter(
            id=uuid4(),
            run_id=uuid4(),
            player_id=uuid4(),
            route_id=31,
            species_id=1,
            family_id=1,
            level=7,
            shiny=False,
            method=EncounterMethod.FISH,
            rod_kind=RodKind.GOOD,
            time=datetime.now(timezone.utc),
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=True
        )
        
        assert encounter.level == 7
        assert encounter.shiny is False
        assert encounter.method == EncounterMethod.FISH
        assert encounter.rod_kind == RodKind.GOOD
        assert encounter.status == EncounterStatus.FIRST_ENCOUNTER

    def test_encounter_without_rod_kind(self):
        """Test creating encounter without rod kind (non-fishing)."""
        encounter = Encounter(
            run_id=uuid4(),
            player_id=uuid4(),
            route_id=1,
            species_id=1,
            family_id=1,
            level=5,
            method=EncounterMethod.GRASS,
            time=datetime.now(timezone.utc),
            status=EncounterStatus.FIRST_ENCOUNTER
        )
        
        assert encounter.method == EncounterMethod.GRASS
        assert encounter.rod_kind is None


@pytest.mark.unit
class TestLinkModels:
    """Test Link and LinkMember models."""

    def test_link_creation(self):
        """Test creating a soul link."""
        link = Link(
            id=uuid4(),
            run_id=uuid4(),
            route_id=31
        )
        
        assert link.route_id == 31

    def test_link_member_creation(self):
        """Test creating a link member."""
        link_member = LinkMember(
            link_id=uuid4(),
            player_id=uuid4(),
            encounter_id=uuid4()
        )
        
        assert link_member.link_id is not None
        assert link_member.player_id is not None
        assert link_member.encounter_id is not None


@pytest.mark.unit
class TestBlocklistModel:
    """Test the Blocklist model."""

    def test_blocklist_creation(self):
        """Test creating a blocklist entry."""
        blocklist = Blocklist(
            run_id=uuid4(),
            family_id=1,
            origin="first_encounter",
            created_at=datetime.now(timezone.utc)
        )
        
        assert blocklist.family_id == 1
        assert blocklist.origin == "first_encounter"


@pytest.mark.unit
class TestPartyStatusModel:
    """Test the PartyStatus model."""

    def test_party_status_creation(self):
        """Test creating party status."""
        party_status = PartyStatus(
            run_id=uuid4(),
            player_id=uuid4(),
            pokemon_key="test_personality_value",
            alive=True,
            last_update=datetime.now(timezone.utc)
        )
        
        assert party_status.pokemon_key == "test_personality_value"
        assert party_status.alive is True


@pytest.mark.unit
class TestIdempotencyKeyModel:
    """Test the IdempotencyKey model."""

    def test_idempotency_key_creation(self):
        """Test creating idempotency key."""
        key = IdempotencyKey(
            key="test-uuid-key",
            run_id=uuid4(),
            player_id=uuid4(),
            request_hash="sha256_hash",
            response_json={"status": "success"},
            created_at=datetime.now(timezone.utc)
        )
        
        assert key.key == "test-uuid-key"
        assert key.request_hash == "sha256_hash"
        assert key.response_json["status"] == "success"