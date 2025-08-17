"""Unit tests for v3-only events API (no legacy v2 support)."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.soullink_tracker.main import app
from src.soullink_tracker.db.models import Run, Player, Species, Route
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus
from src.soullink_tracker.domain.events import EncounterEvent, CatchResultEvent
from src.soullink_tracker.auth.security import create_access_token


class TestEventsAPIV3Only:
    """Test events API with v3-only processing (no dual-write or legacy v2)."""
    
    @pytest.fixture
    def sample_data(self, test_db):
        """Create sample data for testing."""
        db = test_db()
        
        # Create run
        run = Run(name="Test Run", rules_json={})
        db.add(run)
        db.flush()
        
        # Create player
        token, token_hash = Player.generate_token()
        player = Player(
            run_id=run.id,
            name="TestPlayer",
            game="HeartGold",
            region="EU",
            token_hash=token_hash
        )
        db.add(player)
        db.flush()
        
        # Create species
        species = Species(id=1, name="Pidgey", family_id=16)
        db.add(species)
        
        # Create route
        route = Route(id=31, label="Route 31", region="EU")
        db.add(route)
        
        db.commit()
        db.refresh(run)
        db.refresh(player)
        
        # Generate JWT token for authentication
        jwt_token = create_access_token(str(player.id))
        
        db.close()
        
        return {
            "run": run,
            "player": player,
            "species": species,
            "route": route,
            "token": token,
            "jwt_token": jwt_token
        }
    
    def test_process_event_uses_v3_only(self, client: TestClient, sample_data):
        """Test that process_event always uses v3 event store, never legacy v2."""
        run = sample_data["run"]
        player = sample_data["player"]
        
        encounter_data = {
            "type": "encounter",
            "run_id": str(run.id),
            "player_id": str(player.id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 29,
            "species_id": 1,
            "level": 5,
            "shiny": False,
            "method": "grass"
        }
        
        with patch('src.soullink_tracker.api.events._process_event_v3') as mock_v3:
            mock_v3.return_value = (uuid4(), 1)  # event_id, sequence_number
            
            response = client.post(
                "/v1/events",
                json=encounter_data,
                headers={**auth_headers, "Idempotency-Key": str(uuid4())}
            )
        
        assert response.status_code == 202
        
        # Should have called v3 processing
        mock_v3.assert_called_once()
        
        # Should return v3 event structure
        result = response.json()
        assert "event_id" in result
        assert "seq" in result  # Sequence number for encounters
        assert "applied_rules" in result
        assert result["message"] == "Event processed successfully"
    
    def test_process_event_never_calls_legacy_functions(self, client: TestClient, sample_data):
        """Test that legacy v2 processing functions are never called."""
        run = sample_data["run"]
        player = sample_data["player"]
        
        catch_result_data = {
            "type": "catch_result",
            "run_id": str(run.id),
            "player_id": str(player.id),
            "time": datetime.now(timezone.utc).isoformat(),
            "encounter_id": str(uuid4()),
            "result": "caught"
        }
        
        with patch('src.soullink_tracker.api.events._process_event_v3') as mock_v3, \
             patch('src.soullink_tracker.api.events._process_encounter_event_legacy') as mock_legacy_encounter, \
             patch('src.soullink_tracker.api.events._process_catch_result_event_legacy') as mock_legacy_catch, \
             patch('src.soullink_tracker.api.events._process_faint_event_legacy') as mock_legacy_faint:
            
            mock_v3.return_value = (uuid4(), None)  # catch_result has no sequence
            
            response = client.post(
                "/v1/events",
                json=catch_result_data,
                headers={**auth_headers, "Idempotency-Key": str(uuid4())}
            )
        
        assert response.status_code == 202
        
        # v3 should be called
        mock_v3.assert_called_once()
        
        # Legacy functions should never be called
        mock_legacy_encounter.assert_not_called()
        mock_legacy_catch.assert_not_called()
        mock_legacy_faint.assert_not_called()
    
    def test_config_flag_ignored_always_v3(self, client: TestClient, sample_data):
        """Test that even if config tries to disable v3, it's ignored and v3 is used."""
        run = sample_data["run"]
        player = sample_data["player"]
        
        encounter_data = {
            "type": "encounter",
            "run_id": str(run.id),
            "player_id": str(player.id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 30,
            "species_id": 4,
            "level": 6,
            "shiny": False,
            "method": "grass"
        }
        
        # Mock config to try to disable v3 (should be ignored)
        with patch('src.soullink_tracker.api.events.get_config') as mock_config, \
             patch('src.soullink_tracker.api.events._process_event_v3') as mock_v3:
            
            # Create a mock config that tries to disable v3
            mock_config_obj = type('MockConfig', (), {})()
            mock_config_obj.app = type('MockApp', (), {'feature_v3_eventstore': False})()
            mock_config.return_value = mock_config_obj
            
            mock_v3.return_value = (uuid4(), 1)
            
            response = client.post(
                "/v1/events",
                json=encounter_data,
                headers={**auth_headers, "Idempotency-Key": str(uuid4())}
            )
        
        assert response.status_code == 202
        
        # Should still use v3 regardless of config flag
        mock_v3.assert_called_once()
    
    def test_no_dual_write_variables_in_processing(self, client: TestClient, sample_data):
        """Test that dual-write related variables and logic don't exist."""
        run = sample_data["run"]
        player = sample_data["player"]
        
        encounter_data = {
            "type": "encounter",
            "run_id": str(run.id),
            "player_id": str(player.id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 31,
            "species_id": 7,
            "level": 8,
            "shiny": True,
            "method": "surf"
        }
        
        with patch('src.soullink_tracker.api.events._process_event_v3') as mock_v3:
            mock_v3.return_value = (uuid4(), 1)
            
            response = client.post(
                "/v1/events",
                json=encounter_data,
                headers={**auth_headers, "Idempotency-Key": str(uuid4())}
            )
        
        assert response.status_code == 202
        
        # Import the events module to check for dual-write variables
        from src.soullink_tracker.api import events
        
        # These variables should not exist in the v3-only implementation
        processing_function = getattr(events, 'process_event', None)
        if processing_function:
            import inspect
            source = inspect.getsource(processing_function)
            
            # Should not contain dual-write related code
            assert 'enable_dualwrite' not in source
            assert 'feature_v3_dualwrite' not in source
            assert 'dual_err' not in source
            assert 'begin_nested' not in source
    
    def test_get_events_catchup_always_available(self, client: TestClient, sample_data):
        """Test that catch-up endpoint is always available (no 501 check for v3)."""
        run = sample_data["run"]
        
        response = client.get(
            f"/v1/events?run_id={run.id}&since_seq=0&limit=10",
            headers=auth_headers
        )
        
        # Should not return 501 "Feature Not Available"
        assert response.status_code != 501
        # Should return 200 (success) or other valid status
        assert response.status_code in [200, 403, 404]  # Valid status codes for this endpoint
    
    def test_all_event_types_use_v3_processing(self, client: TestClient, sample_data):
        """Test that encounter, catch_result, and faint events all use v3 processing."""
        run = sample_data["run"]
        player = sample_data["player"]
        encounter_id = uuid4()
        
        event_types = [
            {
                "type": "encounter",
                "run_id": str(run.id),
                "player_id": str(player.id),
                "time": datetime.now(timezone.utc).isoformat(),
                "route_id": 32,
                "species_id": 10,
                "level": 12,
                "shiny": False,
                "method": "fish",
                "rod_kind": "good"
            },
            {
                "type": "catch_result",
                "run_id": str(run.id),
                "player_id": str(player.id),
                "time": datetime.now(timezone.utc).isoformat(),
                "encounter_id": str(encounter_id),
                "result": "caught"
            },
            {
                "type": "faint",
                "run_id": str(run.id),
                "player_id": str(player.id),
                "time": datetime.now(timezone.utc).isoformat(),
                "pokemon_key": "test_pokemon_123",
                "party_index": 0
            }
        ]
        
        with patch('src.soullink_tracker.api.events._process_event_v3') as mock_v3:
            mock_v3.return_value = (uuid4(), 1)  # event_id, sequence (or None for non-encounters)
            
            for event_data in event_types:
                response = client.post(
                    "/v1/events",
                    json=event_data,
                    headers={**auth_headers, "Idempotency-Key": str(uuid4())}
                )
                
                assert response.status_code == 202, f"Failed for event type: {event_data['type']}"
        
        # Should have called v3 processing for all 3 event types
        assert mock_v3.call_count == 3
    
    def test_response_format_consistent_with_v3(self, client: TestClient, sample_data):
        """Test that response format matches v3 expectations."""
        run = sample_data["run"]
        player = sample_data["player"]
        test_event_id = uuid4()
        test_sequence = 42
        
        encounter_data = {
            "type": "encounter",
            "run_id": str(run.id),
            "player_id": str(player.id),
            "time": datetime.now(timezone.utc).isoformat(),
            "route_id": 33,
            "species_id": 13,
            "level": 15,
            "shiny": False,
            "method": "grass"
        }
        
        with patch('src.soullink_tracker.api.events._process_event_v3') as mock_v3:
            mock_v3.return_value = (test_event_id, test_sequence)
            
            response = client.post(
                "/v1/events",
                json=encounter_data,
                headers={**auth_headers, "Idempotency-Key": str(uuid4())}
            )
        
        assert response.status_code == 202
        result = response.json()
        
        # Should return v3 format
        assert result["event_id"] == str(test_event_id)
        assert result["seq"] == test_sequence
        assert "applied_rules" in result
        assert isinstance(result["applied_rules"], list)
        
        # Should not contain any v2-specific fields
        assert "v2_event_id" not in result
        assert "legacy_id" not in result