"""Unit tests for WebSocket broadcast using domain events."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from src.soullink_tracker.domain.events import EncounterEvent, CatchResultEvent, FaintEvent
from src.soullink_tracker.core.enums import EncounterMethod, EncounterStatus


class TestWebSocketBroadcastDomainEvents:
    """Test that WebSocket broadcasting uses domain events instead of API schema."""

    @pytest.fixture
    def mock_websocket_manager(self):
        """Mock WebSocket manager for testing."""
        with patch('src.soullink_tracker.api.events.websocket_manager') as mock:
            mock.broadcast_to_run = AsyncMock()
            yield mock

    async def test_broadcast_encounter_event_uses_domain_fields(self, mock_websocket_manager):
        """Test that encounter event broadcasting uses domain event fields."""
        from src.soullink_tracker.api.events import _broadcast_event_update
        
        # Create a domain encounter event
        encounter_event = EncounterEvent(
            event_id=uuid4(),
            run_id=uuid4(),
            player_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            route_id=31,
            species_id=1,
            family_id=1,
            level=5,
            shiny=False,
            encounter_method=EncounterMethod.GRASS,
            rod_kind=None,
            status=EncounterStatus.FIRST_ENCOUNTER,
            dupes_skip=False,
            fe_finalized=False
        )
        
        # Mock the _broadcast_event_update function to accept domain events
        await _broadcast_event_update(encounter_event, sequence_number=1)
        
        # Verify broadcast_to_run was called
        assert mock_websocket_manager.broadcast_to_run.called
        call_args = mock_websocket_manager.broadcast_to_run.call_args
        
        # Check that the message uses correct domain event fields
        message = call_args.kwargs['message']
        assert message.type == "encounter"
        assert message.data['route_id'] == 31
        assert message.data['species_id'] == 1
        assert message.data['family_id'] == 1
        assert message.data['method'] == 'grass'  # Should be 'method', not 'encounter_method'
        assert call_args.kwargs['sequence_number'] == 1

    async def test_broadcast_catch_result_uses_domain_fields(self, mock_websocket_manager):
        """Test that catch result event broadcasting uses domain event fields.""" 
        from src.soullink_tracker.api.events import _broadcast_event_update
        
        # Create a domain catch result event
        catch_event = CatchResultEvent(
            event_id=uuid4(),
            run_id=uuid4(),
            player_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            encounter_id=uuid4(),
            result=EncounterStatus.CAUGHT
        )
        
        await _broadcast_event_update(catch_event, sequence_number=2)
        
        # Verify broadcast_to_run was called
        assert mock_websocket_manager.broadcast_to_run.called
        call_args = mock_websocket_manager.broadcast_to_run.call_args
        
        # Check that the message uses correct domain event fields
        message = call_args.kwargs['message']
        assert message.type == "catch_result"
        assert message.data['encounter_ref'] is not None  # For now still using encounter_ref
        assert message.data['status'] == 'caught'  # For now still using 'status'
        assert call_args.kwargs['sequence_number'] == 2

    async def test_broadcast_faint_event_uses_domain_fields(self, mock_websocket_manager):
        """Test that faint event broadcasting uses domain event fields."""
        from src.soullink_tracker.api.events import _broadcast_event_update
        
        # Create a domain faint event
        faint_event = FaintEvent(
            event_id=uuid4(),
            run_id=uuid4(),
            player_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            pokemon_key="starter-1",
            party_index=0
        )
        
        await _broadcast_event_update(faint_event, sequence_number=3)
        
        # Verify broadcast_to_run was called
        assert mock_websocket_manager.broadcast_to_run.called
        call_args = mock_websocket_manager.broadcast_to_run.call_args
        
        # Check that the message uses correct domain event fields
        message = call_args.kwargs['message']
        assert message.type == "faint"
        assert message.data['pokemon_key'] == "starter-1"
        assert message.data['party_index'] == 0
        assert call_args.kwargs['sequence_number'] == 3

    def test_broadcast_function_signature_accepts_domain_events(self):
        """Test that the _broadcast_event_update function signature accepts domain events."""
        from src.soullink_tracker.api.events import _broadcast_event_update
        import inspect
        
        sig = inspect.signature(_broadcast_event_update)
        
        # Should accept domain events, not API schema events
        event_param = sig.parameters['event']
        annotation_str = str(event_param.annotation)
        
        # Should accept Union of domain events
        assert 'EncounterEvent' in annotation_str
        assert 'CatchResultEvent' in annotation_str  
        assert 'FaintEvent' in annotation_str