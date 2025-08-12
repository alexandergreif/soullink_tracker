"""Unit tests for secure token API endpoints."""

import pytest
from fastapi import status
from uuid import uuid4

from soullink_tracker.db.models import Run, Player


@pytest.mark.unit
class TestAdminRunCreation:
    """Test admin run creation endpoint."""
    
    def test_create_run_success(self, client, test_db):
        """Test successful run creation."""
        response = client.post("/v1/admin/runs", json={
            "name": "Test SoulLink Run",
            "rules_json": {"dupes_clause": True, "first_encounter_only": True}
        })
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == "Test SoulLink Run"
        assert data["rules_json"]["dupes_clause"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_run_invalid_data(self, client, test_db):
        """Test run creation with invalid data."""
        response = client.post("/v1/admin/runs", json={
            "name": "",  # Empty name should fail validation
            "rules_json": {}
        })
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_run_missing_name(self, client, test_db):
        """Test run creation with missing name."""
        response = client.post("/v1/admin/runs", json={
            "rules_json": {"dupes_clause": True}
        })
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.unit  
class TestAdminPlayerCreation:
    """Test admin player creation endpoint."""
    
    def test_create_player_success(self, client, test_db):
        """Test successful player creation with token."""
        # First create a run
        db = test_db()
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.commit()
        db.refresh(run)
        
        # Create player
        response = client.post(f"/v1/admin/runs/{run.id}/players", json={
            "name": "TestPlayer",
            "game": "HeartGold",
            "region": "EU"
        })
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["name"] == "TestPlayer"
        assert data["game"] == "HeartGold"
        assert data["region"] == "EU"
        assert data["run_id"] == str(run.id)
        assert "player_token" in data
        assert len(data["player_token"]) > 20  # Should be a secure token
        assert "id" in data
        assert "created_at" in data

    def test_create_player_run_not_found(self, client, test_db):
        """Test player creation with non-existent run."""
        fake_run_id = str(uuid4())
        response = client.post(f"/v1/admin/runs/{fake_run_id}/players", json={
            "name": "TestPlayer",
            "game": "HeartGold", 
            "region": "EU"
        })
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        # Check both possible response formats
        if "title" in data:
            assert "Run Not Found" in data["title"]
        else:
            assert "Run" in data["detail"] and "not" in data["detail"].lower()

    def test_create_player_duplicate_name(self, client, test_db):
        """Test creating player with duplicate name in same run."""
        # Setup run and first player
        db = test_db()
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.commit()
        db.refresh(run)
        
        token, token_hash = Player.generate_token()
        player1 = Player(
            run_id=run.id,
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        db.add(player1)
        db.commit()
        
        # Try to create second player with same name
        response = client.post(f"/v1/admin/runs/{run.id}/players", json={
            "name": "TestPlayer",  # Same name
            "game": "SoulSilver",
            "region": "US"
        })
        
        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        # Check for error message about duplicate player
        error_text = data.get("title", data.get("detail", "")).lower()
        assert "player" in error_text and ("exist" in error_text or "duplicate" in error_text)

    def test_create_player_invalid_data(self, client, test_db):
        """Test player creation with invalid data."""
        # Create run first
        db = test_db()
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.commit()
        db.refresh(run)
        
        response = client.post(f"/v1/admin/runs/{run.id}/players", json={
            "name": "",  # Empty name
            "game": "InvalidGame",
            "region": "InvalidRegion"
        })
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.unit
class TestTokenRotation:
    """Test token rotation endpoint."""
    
    def test_rotate_token_success(self, client, test_db):
        """Test successful token rotation."""
        # Setup player
        db = test_db()
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.commit()
        
        original_token, original_hash = Player.generate_token()
        player = Player(
            run_id=run.id,
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash=original_hash
        )
        db.add(player)
        db.commit()
        db.refresh(player)
        
        # Rotate token (using original token for auth)
        response = client.post(
            f"/v1/players/{player.id}/rotate-token",
            headers={"Authorization": f"Bearer {original_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["message"] == "Token rotated successfully"
        assert data["player_id"] == str(player.id)
        assert data["player_name"] == "TestPlayer"
        assert "new_token" in data
        assert data["new_token"] != original_token  # Should be different
        assert len(data["new_token"]) > 20
        assert "warning" in data

    def test_rotate_token_unauthorized(self, client, test_db):
        """Test token rotation without authentication."""
        # Setup player
        db = test_db()
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.commit()
        
        token, token_hash = Player.generate_token()
        player = Player(
            run_id=run.id,
            name="TestPlayer", 
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        db.add(player)
        db.commit()
        db.refresh(player)
        
        # Try to rotate without auth
        response = client.post(f"/v1/players/{player.id}/rotate-token")
        
        # Could be 401 (no auth header) or 403 (invalid/missing credentials)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_rotate_token_wrong_player(self, client, test_db):
        """Test trying to rotate another player's token."""
        # Setup two players
        db = test_db()
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.commit()
        
        # Player 1
        token1, hash1 = Player.generate_token()
        player1 = Player(
            run_id=run.id,
            name="Player1",
            game="HeartGold",
            region="EU",
            token_hash=hash1
        )
        
        # Player 2  
        token2, hash2 = Player.generate_token()
        player2 = Player(
            run_id=run.id,
            name="Player2",
            game="SoulSilver",
            region="US", 
            token_hash=hash2
        )
        
        db.add(player1)
        db.add(player2)
        db.commit()
        db.refresh(player1)
        db.refresh(player2)
        
        # Player 1 tries to rotate Player 2's token
        response = client.post(
            f"/v1/players/{player2.id}/rotate-token",
            headers={"Authorization": f"Bearer {token1}"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        # Check for error message about authorization
        error_text = data.get("title", data.get("detail", "")).lower()
        assert ("forbidden" in error_text or "own token" in error_text or 
                "not authorized" in error_text or "authorization" in error_text)

    def test_rotate_token_player_not_found(self, client, test_db):
        """Test token rotation for non-existent player."""
        # Setup player for authentication
        db = test_db()
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.commit()
        
        token, token_hash = Player.generate_token()
        player = Player(
            run_id=run.id,
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        db.add(player)
        db.commit()
        
        # Try to rotate token for non-existent player
        fake_player_id = str(uuid4())
        response = client.post(
            f"/v1/players/{fake_player_id}/rotate-token",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        # Check for error message about player not found
        error_text = data.get("title", data.get("detail", "")).lower()
        assert "player" in error_text and ("not found" in error_text or "does not exist" in error_text)


@pytest.mark.unit  
class TestProtectedEndpoints:
    """Test that protected endpoints require authentication."""
    
    def test_events_endpoint_requires_auth(self, client, test_db):
        """Test that events endpoint requires Bearer token."""
        response = client.post("/v1/events", json={
            "type": "encounter",
            "run_id": str(uuid4()),
            "player_id": str(uuid4()),
            "time": "2025-08-10T18:23:05Z",
            "route_id": 31,
            "species_id": 1,
            "level": 7,
            "shiny": False,
            "method": "grass"
        })
        
        # Could be 401 (no auth header) or 403 (missing credentials)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_events_endpoint_invalid_token(self, client, test_db):
        """Test events endpoint with invalid token."""
        response = client.post("/v1/events", 
            json={
                "type": "encounter",
                "run_id": str(uuid4()),
                "player_id": str(uuid4()),
                "time": "2025-08-10T18:23:05Z",
                "route_id": 31,
                "species_id": 1, 
                "level": 7,
                "shiny": False,
                "method": "grass"
            },
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_player_routes_require_auth(self, client, test_db):
        """Test that player-specific routes require authentication."""
        fake_player_id = str(uuid4())
        
        # Test token rotation without auth
        response = client.post(f"/v1/players/{fake_player_id}/rotate-token")
        # Could be 401 (no auth header) or 403 (missing credentials)
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]