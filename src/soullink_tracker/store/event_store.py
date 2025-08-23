"""Event store implementation for append-only event persistence and replay.

This module provides the core event store functionality including:
- Appending events with automatic sequence numbering
- Querying events by run, sequence range, or event type
- Event replay for projection rebuilding
"""

from typing import Optional, List, Iterator
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..domain.events import DomainEvent, EventEnvelope
from ..db.models import Event as EventModel


class EventStoreError(Exception):
    """Base exception for event store operations."""

    pass


class EventStore:
    """Append-only event store with sequence numbering and replay capabilities."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def append(self, event: DomainEvent) -> EventEnvelope:
        """
        Append a new event to the store with automatic sequence numbering.

        Args:
            event: The domain event to store

        Returns:
            EventEnvelope with the assigned sequence number

        Raises:
            EventStoreError: If the event could not be stored
        """
        try:
            # Get next sequence number for this run
            current_max = self.db.execute(
                select(func.coalesce(func.max(EventModel.seq), 0)).where(
                    EventModel.run_id == event.run_id
                )
            ).scalar()

            next_seq = (current_max or 0) + 1

            # Create event record
            event_record = EventModel(
                id=event.event_id,
                run_id=event.run_id,
                player_id=event.player_id,
                type=event.event_type,
                payload_json=event.model_dump(mode="json"),
                created_at=event.timestamp,
                seq=next_seq,
            )

            self.db.add(event_record)
            self.db.flush()  # Ensure sequence number is assigned

            return EventEnvelope(
                sequence_number=next_seq, stored_at=event_record.created_at, event=event
            )

        except SQLAlchemyError as e:
            raise EventStoreError(f"Failed to append event: {e}") from e

    def get_events(
        self,
        run_id: UUID,
        since_seq: Optional[int] = None,
        until_seq: Optional[int] = None,
        event_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[EventEnvelope]:
        """
        Query events from the store with filtering options.

        Args:
            run_id: Run ID to filter by
            since_seq: Include events after this sequence number (exclusive)
            until_seq: Include events up to this sequence number (inclusive)
            event_types: Filter by specific event types
            limit: Maximum number of events to return

        Returns:
            List of event envelopes ordered by sequence number
        """
        try:
            query = select(EventModel).where(EventModel.run_id == run_id)

            # Apply sequence filters
            if since_seq is not None:
                query = query.where(EventModel.seq > since_seq)
            if until_seq is not None:
                query = query.where(EventModel.seq <= until_seq)

            # Apply event type filter
            if event_types:
                query = query.where(EventModel.type.in_(event_types))

            # Order by sequence and apply limit
            query = query.order_by(EventModel.seq)
            if limit:
                query = query.limit(limit)

            results = self.db.execute(query).scalars().all()

            # Convert to event envelopes
            envelopes = []
            for record in results:
                event = self._deserialize_event(record)
                envelope = EventEnvelope(
                    sequence_number=record.seq, stored_at=record.created_at, event=event
                )
                envelopes.append(envelope)

            return envelopes

        except SQLAlchemyError as e:
            raise EventStoreError(f"Failed to query events: {e}") from e

    def get_events_by_type(
        self, run_id: UUID, event_type: str, limit: Optional[int] = None
    ) -> List[EventEnvelope]:
        """
        Convenience method to get events of a specific type.
        
        Args:
            run_id: Run ID to filter by
            event_type: Specific event type to filter for
            limit: Maximum number of events to return
            
        Returns:
            List of event envelopes for the specified type
        """
        return self.get_events(run_id=run_id, event_types=[event_type], limit=limit)

    def get_event_by_id(self, run_id: UUID, event_id: UUID) -> Optional[EventEnvelope]:
        """
        Get a single event by its ID within a specific run.

        Args:
            run_id: Run ID to filter by
            event_id: Specific event ID to retrieve

        Returns:
            EventEnvelope for the specified event, or None if not found

        Raises:
            EventStoreError: If the query fails
        """
        try:
            record = self.db.execute(
                select(EventModel).where(
                    and_(EventModel.run_id == run_id, EventModel.id == event_id)
                )
            ).scalar_one_or_none()

            if not record:
                return None

            # Deserialize and wrap in envelope
            event = self._deserialize_event(record)
            return EventEnvelope(
                sequence_number=record.seq,
                stored_at=record.created_at,
                event=event
            )

        except SQLAlchemyError as e:
            raise EventStoreError(f"Failed to get event by ID: {e}") from e

    def get_latest_sequence(self, run_id: UUID) -> int:
        """
        Get the latest sequence number for a run.

        Args:
            run_id: Run ID to check

        Returns:
            Latest sequence number, or 0 if no events exist
        """
        try:
            result = self.db.execute(
                select(func.coalesce(func.max(EventModel.seq), 0)).where(
                    EventModel.run_id == run_id
                )
            ).scalar()

            return result or 0

        except SQLAlchemyError as e:
            raise EventStoreError(f"Failed to get latest sequence: {e}") from e

    def replay_events(
        self, run_id: UUID, from_sequence: int = 0
    ) -> Iterator[EventEnvelope]:
        """
        Replay events from a specific sequence number.

        This method streams events efficiently for projection rebuilding.

        Args:
            run_id: Run ID to replay events for
            from_sequence: Starting sequence number (inclusive)

        Yields:
            Event envelopes in sequence order
        """
        try:
            # Stream events in batches to avoid memory issues
            batch_size = 1000
            current_seq = from_sequence

            while True:
                query = (
                    select(EventModel)
                    .where(
                        and_(EventModel.run_id == run_id, EventModel.seq >= current_seq)
                    )
                    .order_by(EventModel.seq)
                    .limit(batch_size)
                )

                batch = self.db.execute(query).scalars().all()

                if not batch:
                    break

                for record in batch:
                    event = self._deserialize_event(record)
                    envelope = EventEnvelope(
                        sequence_number=record.seq,
                        stored_at=record.created_at,
                        event=event,
                    )
                    yield envelope
                    current_seq = record.seq + 1

                # If we got fewer results than batch size, we're done
                if len(batch) < batch_size:
                    break

        except SQLAlchemyError as e:
            raise EventStoreError(f"Failed to replay events: {e}") from e

    def _deserialize_event(self, record: EventModel) -> DomainEvent:
        """
        Deserialize an event record into a domain event.

        Args:
            record: Event record from database

        Returns:
            Deserialized domain event

        Raises:
            EventStoreError: If deserialization fails
        """
        try:
            # Import event classes dynamically to avoid circular imports
            from ..domain.events import (
                EncounterEvent,
                CatchResultEvent,
                FaintEvent,
                SoulLinkCreatedEvent,
                SoulLinkBrokenEvent,
                FamilyBlockedEvent,
                FirstEncounterFinalizedEvent,
            )

            event_class_map = {
                "encounter": EncounterEvent,
                "catch_result": CatchResultEvent,
                "faint": FaintEvent,
                "soul_link_created": SoulLinkCreatedEvent,
                "soul_link_broken": SoulLinkBrokenEvent,
                "family_blocked": FamilyBlockedEvent,
                "first_encounter_finalized": FirstEncounterFinalizedEvent,
            }

            event_class = event_class_map.get(record.type)
            if not event_class:
                raise EventStoreError(f"Unknown event type: {record.type}")

            return event_class.model_validate(record.payload_json)

        except Exception as e:
            raise EventStoreError(
                f"Failed to deserialize event {record.id}: {e}"
            ) from e
