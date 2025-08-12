"""NDJSON file reader and event validation utilities."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Iterator

logger = logging.getLogger(__name__)


def iter_ndjson(path: Path) -> Iterator[Dict[str, Any]]:
    """
    Iterate over lines in an NDJSON file, yielding parsed JSON objects.
    
    Args:
        path: Path to the NDJSON file
    
    Yields:
        Parsed JSON objects from each line
    
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If a line contains invalid JSON
    """
    with path.open('r', encoding='utf-8') as f:
        line_number = 0
        
        for line in f:
            line_number += 1
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON on line {line_number} in {path}: {e}")
                raise json.JSONDecodeError(
                    f"Line {line_number}: {e.msg}",
                    e.doc,
                    e.pos
                )


def validate_event_minimal(
    event: Dict[str, Any], 
    run_id: str, 
    player_id: str
) -> Dict[str, Any]:
    """
    Perform minimal validation and normalization of an event.
    
    This ensures the event has the minimum required fields for the API
    and injects missing run_id/player_id if needed.
    
    Args:
        event: Raw event dictionary
        run_id: Run ID to inject if missing
        player_id: Player ID to inject if missing
    
    Returns:
        Normalized event dictionary
    
    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Make a copy to avoid mutating the original
    normalized = event.copy()
    
    # Ensure 'type' field exists
    if 'type' not in normalized:
        raise ValueError("Event missing required 'type' field")
    
    event_type = normalized['type']
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError(f"Invalid event type: {event_type}")
    
    # Inject run_id and player_id if missing
    if 'run_id' not in normalized:
        normalized['run_id'] = run_id
        logger.debug(f"Injected run_id {run_id} into {event_type} event")
    
    if 'player_id' not in normalized:
        normalized['player_id'] = player_id
        logger.debug(f"Injected player_id {player_id} into {event_type} event")
    
    # Ensure 'time' field exists with current timestamp if missing
    if 'time' not in normalized:
        now_iso = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        normalized['time'] = now_iso
        logger.debug(f"Injected current timestamp into {event_type} event")
    
    # Validate time format (basic check)
    try:
        time_str = normalized['time']
        if isinstance(time_str, str) and time_str:
            # Try to parse the timestamp to validate format
            if time_str.endswith('Z'):
                datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            else:
                datetime.fromisoformat(time_str)
        else:
            raise ValueError("Time must be a non-empty string")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid time format in {event_type} event: {e}")
    
    # Type-specific validation
    if event_type == "encounter":
        _validate_encounter_event(normalized)
    elif event_type == "catch_result":
        _validate_catch_result_event(normalized)
    elif event_type == "faint":
        _validate_faint_event(normalized)
    
    return normalized


def _validate_encounter_event(event: Dict[str, Any]) -> None:
    """Validate encounter event specific fields."""
    required_fields = ['route_id', 'species_id', 'level', 'shiny', 'method']
    
    for field in required_fields:
        if field not in event:
            raise ValueError(f"Encounter event missing required field: {field}")
    
    # Validate field types
    if not isinstance(event['route_id'], int):
        raise ValueError(f"Invalid route_id: must be integer, got {type(event['route_id'])}")
    
    if not isinstance(event['species_id'], int):
        raise ValueError(f"Invalid species_id: must be integer, got {type(event['species_id'])}")
    
    if not isinstance(event['level'], int) or event['level'] < 1:
        raise ValueError(f"Invalid level: must be positive integer, got {event['level']}")
    
    if not isinstance(event['shiny'], bool):
        raise ValueError(f"Invalid shiny: must be boolean, got {type(event['shiny'])}")
    
    if not isinstance(event['method'], str) or not event['method'].strip():
        raise ValueError(f"Invalid method: must be non-empty string, got {event['method']}")
    
    # Validate method is one of the known types
    valid_methods = ['grass', 'surf', 'fish', 'static', 'unknown']
    if event['method'] not in valid_methods:
        logger.warning(f"Unknown encounter method: {event['method']} (valid: {valid_methods})")


def _validate_catch_result_event(event: Dict[str, Any]) -> None:
    """Validate catch result event specific fields."""
    required_fields = ['encounter_ref', 'status']
    
    for field in required_fields:
        if field not in event:
            raise ValueError(f"Catch result event missing required field: {field}")
    
    # Validate encounter_ref is a dictionary with required fields
    encounter_ref = event['encounter_ref']
    if not isinstance(encounter_ref, dict):
        raise ValueError(f"Invalid encounter_ref: must be dictionary, got {type(encounter_ref)}")
    
    if 'route_id' not in encounter_ref or 'species_id' not in encounter_ref:
        raise ValueError("encounter_ref must contain route_id and species_id")
    
    # Validate status
    if not isinstance(event['status'], str) or not event['status'].strip():
        raise ValueError(f"Invalid status: must be non-empty string, got {event['status']}")
    
    valid_statuses = ['caught', 'fled', 'ko', 'failed']
    if event['status'] not in valid_statuses:
        logger.warning(f"Unknown catch status: {event['status']} (valid: {valid_statuses})")


def _validate_faint_event(event: Dict[str, Any]) -> None:
    """Validate faint event specific fields."""
    required_fields = ['pokemon_key', 'party_index']
    
    for field in required_fields:
        if field not in event:
            raise ValueError(f"Faint event missing required field: {field}")
    
    # Validate field types
    if not isinstance(event['pokemon_key'], str) or not event['pokemon_key'].strip():
        raise ValueError(f"Invalid pokemon_key: must be non-empty string, got {event['pokemon_key']}")
    
    if not isinstance(event['party_index'], int) or event['party_index'] < 0:
        raise ValueError(f"Invalid party_index: must be non-negative integer, got {event['party_index']}")


def count_events_in_file(path: Path) -> int:
    """
    Count the number of valid events in an NDJSON file.
    
    Args:
        path: Path to the NDJSON file
    
    Returns:
        Number of valid JSON lines (excluding empty lines and comments)
    """
    count = 0
    try:
        for _ in iter_ndjson(path):
            count += 1
    except (FileNotFoundError, json.JSONDecodeError):
        return 0
    
    return count


def preview_events(path: Path, limit: int = 5) -> Iterator[str]:
    """
    Preview the first few events in an NDJSON file as formatted strings.
    
    Args:
        path: Path to the NDJSON file
        limit: Maximum number of events to preview
    
    Yields:
        Formatted string representations of events
    """
    count = 0
    try:
        for event in iter_ndjson(path):
            if count >= limit:
                break
            
            event_type = event.get('type', 'unknown')
            timestamp = event.get('time', 'no-time')
            yield f"{count + 1:2d}. {event_type:12s} at {timestamp}"
            count += 1
            
    except Exception as e:
        yield f"Error reading file: {e}"