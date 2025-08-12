"""Tests for data retrieval API endpoints."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from uuid import uuid4

from soullink_tracker.db.models import (
    Run, Player, Species, Route, Encounter, Link, LinkMember, 
    Blocklist
)
from soullink_tracker.core.enums import EncounterMethod, EncounterStatus
from soullink_tracker.auth.security import create_access_token


class TestDataAPI:
    """Test cases for data retrieval API endpoints."""

    @pytest.fixture
    def sample_data(self, test_db):
        """Create comprehensive sample data for testing."""
        db = test_db()
        
        # Create run
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.flush()
        
        # Create players
        token1, token_hash1 = Player.generate_token()
        token2, token_hash2 = Player.generate_token()
        
        player1 = Player(
            run_id=run.id,
            name="Player1",
            game="HeartGold",
            region="EU",
            token_hash=token_hash1
        )
        player2 = Player(
            run_id=run.id,
            name="Player2",
            game="SoulSilver",
            region="EU",
            token_hash=token_hash2
        )
        db.add_all([player1, player2])
        db.flush()
        
        # Create species
        species1 = Species(id=1, name="Pidgey", family_id=16)
        species2 = Species(id=2, name="Rattata", family_id=19)
        species3 = Species(id=16, name="Pidgeotto", family_id=16)  # Same family as Pidgey
        db.add_all([species1, species2, species3])
        
        # Create routes
        route1 = Route(id=31, label="Route 31", region="EU")
        route2 = Route(id=32, label="Route 32", region="EU")
        db.add_all([route1, route2])
        
        # Create encounters
        encounter1 = Encounter(
            run_id=run.id,
            player_id=player1.id,
            route_id=31,
            species_id=1,
            family_id=16,
            level=5,
            shiny=False,
            method=EncounterMethod.GRASS,
            time=datetime.now(timezone.utc),
            status=EncounterStatus.CAUGHT,
            dupes_skip=False,
            fe_finalized=True
        )
        encounter2 = Encounter(
            run_id=run.id,
            player_id=player2.id,
            route_id=31,
            species_id=2,
            family_id=19,
            level=6,
            shiny=True,
            method=EncounterMethod.GRASS,
            time=datetime.now(timezone.utc),
            status=EncounterStatus.CAUGHT,
            dupes_skip=False,
            fe_finalized=True
        )
        db.add_all([encounter1, encounter2])
        db.flush()
        
        # Create link
        link = Link(run_id=run.id, route_id=31)
        db.add(link)
        db.flush()
        
        # Create link members
        link_member1 = LinkMember(
            link_id=link.id,
            player_id=player1.id,
            encounter_id=encounter1.id
        )
        link_member2 = LinkMember(
            link_id=link.id,
            player_id=player2.id,
            encounter_id=encounter2.id
        )
        db.add_all([link_member1, link_member2])
        
        # Create blocklist entry
        blocklist_entry = Blocklist(
            run_id=run.id,
            family_id=16,
            origin="caught",
            created_at=datetime.now(timezone.utc)
        )
        db.add(blocklist_entry)
        
        db.commit()
        
        # Refresh all objects
        for obj in [run, player1, player2, encounter1, encounter2, link]:
            db.refresh(obj)
        
        db.close()
        
        jwt_token1 = create_access_token(str(player1.id))
        jwt_token2 = create_access_token(str(player2.id))
        
        return {
            "run": run,
            "player1": player1,
            "player2": player2,
            "species1": species1,
            "species2": species2,
            "route1": route1,
            "route2": route2,
            "encounter1": encounter1,
            "encounter2": encounter2,
            "link": link,
            "jwt_token1": jwt_token1,
            "jwt_token2": jwt_token2
        }

    def test_get_encounters_success(self, client: TestClient, sample_data):
        """Test successful encounters retrieval."""
        response = client.get(f"/v1/runs/{sample_data['run'].id}/encounters")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["encounters"]) == 2
        assert data["total"] == 2
        assert data["limit"] == 100
        assert data["offset"] == 0
        
        # Check encounter data
        encounter_ids = [e["id"] for e in data["encounters"]]
        assert str(sample_data["encounter1"].id) in encounter_ids
        assert str(sample_data["encounter2"].id) in encounter_ids

    def test_get_encounters_with_filters(self, client: TestClient, sample_data):
        """Test encounters retrieval with various filters."""
        # Filter by player
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={"player_id": str(sample_data["player1"].id)}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["encounters"]) == 1
        assert data["encounters"][0]["player_id"] == str(sample_data["player1"].id)
        
        # Filter by route
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={"route_id": 31}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["encounters"]) == 2
        
        # Filter by species
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={"species_id": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["encounters"]) == 1
        assert data["encounters"][0]["species_id"] == 1
        
        # Filter by shiny
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={"shiny": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["encounters"]) == 1
        assert data["encounters"][0]["shiny"] is True

    def test_get_encounters_pagination(self, client: TestClient, sample_data):
        """Test encounters pagination."""
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={"limit": 1, "offset": 0}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["encounters"]) == 1
        assert data["total"] == 2
        assert data["limit"] == 1
        assert data["offset"] == 0
        
        # Get second page
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={"limit": 1, "offset": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["encounters"]) == 1
        assert data["total"] == 2
        assert data["offset"] == 1

    def test_get_encounters_run_not_found(self, client: TestClient):
        """Test encounters retrieval with non-existent run."""
        fake_run_id = uuid4()
        response = client.get(f"/v1/runs/{fake_run_id}/encounters")
        
        assert response.status_code == 404

    def test_get_blocklist_success(self, client: TestClient, sample_data):
        """Test successful blocklist retrieval."""
        response = client.get(f"/v1/runs/{sample_data['run'].id}/blocklist")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["blocked_families"]) == 1
        
        blocked_family = data["blocked_families"][0]
        assert blocked_family["family_id"] == 16
        assert blocked_family["origin"] == "caught"
        assert "Pidgey" in blocked_family["species_names"]

    def test_get_blocklist_empty(self, client: TestClient, test_db):
        """Test blocklist retrieval when no families are blocked."""
        # Create run with no blocklist entries
        db = test_db()
        run = Run(name="Empty Run", rules_json={})
        db.add(run)
        db.commit()
        db.refresh(run)
        db.close()
        
        response = client.get(f"/v1/runs/{run.id}/blocklist")
        
        assert response.status_code == 200
        data = response.json()
        assert data["blocked_families"] == []

    def test_get_blocklist_run_not_found(self, client: TestClient):
        """Test blocklist retrieval with non-existent run."""
        fake_run_id = uuid4()
        response = client.get(f"/v1/runs/{fake_run_id}/blocklist")
        
        assert response.status_code == 404

    def test_get_links_success(self, client: TestClient, sample_data):
        """Test successful soul links retrieval."""
        response = client.get(f"/v1/runs/{sample_data['run'].id}/links")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["links"]) == 1
        
        link = data["links"][0]
        assert link["id"] == str(sample_data["link"].id)
        assert link["route_id"] == 31
        assert link["route_label"] == "Route 31"
        assert len(link["members"]) == 2
        
        # Check members
        member_names = [m["player_name"] for m in link["members"]]
        assert "Player1" in member_names
        assert "Player2" in member_names

    def test_get_links_empty(self, client: TestClient, test_db):
        """Test links retrieval when no links exist."""
        # Create run with no links
        db = test_db()
        run = Run(name="No Links Run", rules_json={})
        db.add(run)
        db.commit()
        db.refresh(run)
        db.close()
        
        response = client.get(f"/v1/runs/{run.id}/links")
        
        assert response.status_code == 200
        data = response.json()
        assert data["links"] == []

    def test_get_links_run_not_found(self, client: TestClient):
        """Test links retrieval with non-existent run."""
        fake_run_id = uuid4()
        response = client.get(f"/v1/runs/{fake_run_id}/links")
        
        assert response.status_code == 404

    def test_get_route_status_success(self, client: TestClient, sample_data):
        """Test successful route status matrix retrieval."""
        response = client.get(f"/v1/runs/{sample_data['run'].id}/routes/status")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["routes"]) >= 1
        
        # Find Route 31 which should have catches
        route_31 = next((r for r in data["routes"] if r["route_id"] == 31), None)
        assert route_31 is not None
        assert route_31["route_label"] == "Route 31"
        
        # Check player statuses
        assert "Player1" in route_31["players_status"]
        assert "Player2" in route_31["players_status"]
        assert route_31["players_status"]["Player1"] is not None  # Should have caught something
        assert route_31["players_status"]["Player2"] is not None  # Should have caught something

    def test_get_route_status_run_not_found(self, client: TestClient):
        """Test route status retrieval with non-existent run."""
        fake_run_id = uuid4()
        response = client.get(f"/v1/runs/{fake_run_id}/routes/status")
        
        assert response.status_code == 404

    def test_encounter_response_includes_related_data(self, client: TestClient, sample_data):
        """Test that encounter responses include related entity names."""
        response = client.get(f"/v1/runs/{sample_data['run'].id}/encounters")
        
        assert response.status_code == 200
        data = response.json()
        
        encounter = data["encounters"][0]
        required_fields = [
            "id", "run_id", "player_id", "route_id", "species_id", 
            "family_id", "level", "shiny", "method", "time", "status",
            "dupes_skip", "fe_finalized", "player_name", "route_label", "species_name"
        ]
        
        for field in required_fields:
            assert field in encounter
        
        # Check that names are populated
        assert encounter["player_name"] in ["Player1", "Player2"]
        assert encounter["route_label"] == "Route 31"
        assert encounter["species_name"] in ["Pidgey", "Rattata"]

    def test_encounters_filter_validation(self, client: TestClient, sample_data):
        """Test validation of encounter filter parameters."""
        # Invalid limit (too high)
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={"limit": 2000}
        )
        assert response.status_code == 422
        
        # Invalid limit (negative)
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={"limit": -1}
        )
        assert response.status_code == 422
        
        # Invalid offset (negative)
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={"offset": -1}
        )
        assert response.status_code == 422

    def test_data_endpoints_uuid_validation(self, client: TestClient):
        """Test that data endpoints validate UUID format."""
        endpoints = [
            "/v1/runs/invalid-uuid/encounters",
            "/v1/runs/invalid-uuid/blocklist",
            "/v1/runs/invalid-uuid/links",
            "/v1/runs/invalid-uuid/routes/status"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 422

    def test_encounters_multiple_filters_combined(self, client: TestClient, sample_data):
        """Test encounters retrieval with multiple filters combined."""
        response = client.get(
            f"/v1/runs/{sample_data['run'].id}/encounters",
            params={
                "player_id": str(sample_data["player1"].id),
                "route_id": 31,
                "status": "caught",
                "shiny": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["encounters"]) == 1
        
        encounter = data["encounters"][0]
        assert encounter["player_id"] == str(sample_data["player1"].id)
        assert encounter["route_id"] == 31
        assert encounter["status"] == "caught"
        assert encounter["shiny"] is False

    def test_links_member_details(self, client: TestClient, sample_data):
        """Test that link members include detailed encounter information."""
        response = client.get(f"/v1/runs/{sample_data['run'].id}/links")
        
        assert response.status_code == 200
        data = response.json()
        
        link = data["links"][0]
        member = link["members"][0]
        
        required_member_fields = [
            "player_id", "player_name", "encounter_id", 
            "species_id", "species_name", "level", "shiny", "status"
        ]
        
        for field in required_member_fields:
            assert field in member
        
        # Validate field types
        assert isinstance(member["level"], int)
        assert isinstance(member["shiny"], bool)
        assert member["status"] in ["caught", "fled", "ko", "failed", "first_encounter", "dupe_skip"]