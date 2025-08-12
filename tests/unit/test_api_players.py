"""Tests for players API endpoints."""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from soullink_tracker.db.models import Run, Player


class TestPlayersAPI:
    """Test cases for player management API endpoints."""

    @pytest.fixture
    def sample_run(self, test_db):
        """Create a sample run for testing."""
        db = test_db()
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.commit()
        db.refresh(run)
        db.close()
        return run

    def test_create_player_success(self, client: TestClient, sample_run):
        """Test successful player creation."""
        player_data = {
            "name": "TestPlayer",
            "game": "HeartGold",
            "region": "EU"
        }
        
        response = client.post(f"/v1/runs/{sample_run.id}/players", json=player_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "TestPlayer"
        assert data["game"] == "HeartGold"
        assert data["region"] == "EU"
        assert data["run_id"] == str(sample_run.id)
        assert "id" in data
        assert "created_at" in data
        assert "player_token" in data  # Token should be included in response
        assert len(data["player_token"]) > 20  # Should be a decent length token

    def test_create_player_invalid_game(self, client: TestClient, sample_run):
        """Test player creation with invalid game version."""
        player_data = {
            "name": "TestPlayer",
            "game": "InvalidGame",
            "region": "EU"
        }
        
        response = client.post(f"/v1/runs/{sample_run.id}/players", json=player_data)
        
        assert response.status_code == 422

    def test_create_player_invalid_region(self, client: TestClient, sample_run):
        """Test player creation with invalid region."""
        player_data = {
            "name": "TestPlayer",
            "game": "HeartGold",
            "region": "INVALID"
        }
        
        response = client.post(f"/v1/runs/{sample_run.id}/players", json=player_data)
        
        assert response.status_code == 422

    def test_create_player_empty_name(self, client: TestClient, sample_run):
        """Test player creation with empty name."""
        player_data = {
            "name": "",
            "game": "HeartGold",
            "region": "EU"
        }
        
        response = client.post(f"/v1/runs/{sample_run.id}/players", json=player_data)
        
        assert response.status_code == 422

    def test_create_player_duplicate_name_same_run(self, client: TestClient, sample_run, test_db):
        """Test that duplicate player names in same run are rejected."""
        # Create first player
        db = test_db()
        token, token_hash = Player.generate_token()
        player1 = Player(
            run_id=sample_run.id,
            name="DuplicateName",
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        db.add(player1)
        db.commit()
        
        # Try to create second player with same name
        player_data = {
            "name": "DuplicateName",
            "game": "SoulSilver",
            "region": "US"
        }
        
        response = client.post(f"/v1/runs/{sample_run.id}/players", json=player_data)
        
        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["detail"].lower()

    def test_create_player_run_not_found(self, client: TestClient):
        """Test player creation with non-existent run."""
        fake_run_id = uuid4()
        player_data = {
            "name": "TestPlayer",
            "game": "HeartGold",
            "region": "EU"
        }
        
        response = client.post(f"/v1/runs/{fake_run_id}/players", json=player_data)
        
        assert response.status_code == 404

    def test_get_players_in_run_success(self, client: TestClient, sample_run, test_db):
        """Test successful retrieval of players in a run."""
        # Create test players
        db = test_db()
        token1, token_hash1 = Player.generate_token()
        token2, token_hash2 = Player.generate_token()
        
        player1 = Player(
            run_id=sample_run.id,
            name="Player1",
            game="HeartGold",
            region="EU",
            token_hash=token_hash1
        )
        player2 = Player(
            run_id=sample_run.id,
            name="Player2",
            game="SoulSilver",
            region="US",
            token_hash=token_hash2
        )
        db.add_all([player1, player2])
        db.commit()
        
        response = client.get(f"/v1/runs/{sample_run.id}/players")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["players"]) == 2
        
        player_names = [p["name"] for p in data["players"]]
        assert "Player1" in player_names
        assert "Player2" in player_names
        
        # Tokens should NOT be included in GET response
        for player in data["players"]:
            assert "player_token" not in player

    def test_get_players_empty_run(self, client: TestClient, sample_run):
        """Test getting players from a run with no players."""
        response = client.get(f"/v1/runs/{sample_run.id}/players")
        
        assert response.status_code == 200
        data = response.json()
        assert data["players"] == []

    def test_get_players_run_not_found(self, client: TestClient):
        """Test getting players from non-existent run."""
        fake_run_id = uuid4()
        
        response = client.get(f"/v1/runs/{fake_run_id}/players")
        
        assert response.status_code == 404

    def test_player_token_generation_uniqueness(self, client: TestClient, sample_run):
        """Test that each created player gets a unique token."""
        player_data = {
            "name": "Player1",
            "game": "HeartGold",
            "region": "EU"
        }
        
        response1 = client.post(f"/v1/runs/{sample_run.id}/players", json=player_data)
        
        player_data["name"] = "Player2"
        response2 = client.post(f"/v1/runs/{sample_run.id}/players", json=player_data)
        
        assert response1.status_code == 201
        assert response2.status_code == 201
        
        token1 = response1.json()["player_token"]
        token2 = response2.json()["player_token"]
        
        assert token1 != token2
        assert len(token1) > 20
        assert len(token2) > 20

    def test_player_response_format(self, client: TestClient, sample_run):
        """Test that player response has correct format and fields."""
        player_data = {
            "name": "FormatTest",
            "game": "SoulSilver",
            "region": "JP"
        }
        
        response = client.post(f"/v1/runs/{sample_run.id}/players", json=player_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Check required fields for creation response
        create_fields = ["id", "run_id", "name", "game", "region", "created_at", "player_token"]
        for field in create_fields:
            assert field in data
        
        # Validate UUID formats
        from uuid import UUID
        UUID(data["id"])
        UUID(data["run_id"])
        
        # Check field types
        assert isinstance(data["name"], str)
        assert isinstance(data["game"], str)
        assert isinstance(data["region"], str)
        assert isinstance(data["created_at"], str)
        assert isinstance(data["player_token"], str)

    def test_multiple_runs_same_player_name(self, client: TestClient, test_db):
        """Test that same player name can exist in different runs."""
        # Create two runs
        db = test_db()
        run1 = Run(name="Run 1", rules_json={})
        run2 = Run(name="Run 2", rules_json={})
        db.add_all([run1, run2])
        db.commit()
        db.refresh(run1)
        db.refresh(run2)
        
        player_data = {
            "name": "SameName",
            "game": "HeartGold",
            "region": "EU"
        }
        
        # Create player in first run
        response1 = client.post(f"/v1/runs/{run1.id}/players", json=player_data)
        assert response1.status_code == 201
        
        # Create player with same name in second run (should work)
        response2 = client.post(f"/v1/runs/{run2.id}/players", json=player_data)
        assert response2.status_code == 201
        
        # Verify they have different IDs and run_ids
        data1 = response1.json()
        data2 = response2.json()
        assert data1["id"] != data2["id"]
        assert data1["run_id"] != data2["run_id"]
        assert data1["player_token"] != data2["player_token"]

    def test_create_player_all_game_region_combinations(self, client: TestClient, sample_run):
        """Test creating players with all valid game/region combinations."""
        combinations = [
            ("HeartGold", "EU"),
            ("HeartGold", "US"), 
            ("HeartGold", "JP"),
            ("SoulSilver", "EU"),
            ("SoulSilver", "US"),
            ("SoulSilver", "JP")
        ]
        
        for i, (game, region) in enumerate(combinations):
            player_data = {
                "name": f"Player{i}",
                "game": game,
                "region": region
            }
            
            response = client.post(f"/v1/runs/{sample_run.id}/players", json=player_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["game"] == game
            assert data["region"] == region