"""
Integrity policy for classifying and handling expected IntegrityError exceptions.

This module provides utilities to distinguish between expected database constraint
violations (which indicate successful race condition prevention) and unexpected
integrity errors that should be treated as actual failures.
"""

from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy.exc import IntegrityError  # type: ignore
from ..utils.logging_config import get_logger


logger = get_logger('database')


class ExpectedIntegrityTag(Enum):
    """Tags for expected integrity constraint violations."""

    ROUTE_ALREADY_FINALIZED = "route_already_finalized"
    BLOCK_ALREADY_EXISTS = "block_already_exists"
    PLAYER_NAME_DUPLICATE = "player_name_duplicate"
    # ROUTE_PROGRESS_DUPLICATE removed - this should never happen with proper UPSERT logic


class IntegrityViolationResult(Enum):
    """Result of handling an integrity violation."""

    ALREADY_EXISTS = "already_exists"
    RACE_CONDITION_LOST = "race_condition_lost"
    DUPLICATE_IGNORED = "duplicate_ignored"


# Map constraint names to their expected tags
# Note: These constraint names match the database schema
CONSTRAINT_TAG_MAP: Dict[str, ExpectedIntegrityTag] = {
    # Route finalization unique constraint (one finalized FE per route)
    "route_progress.run_id, route_progress.route_id": ExpectedIntegrityTag.ROUTE_ALREADY_FINALIZED,
    # Blocklist unique constraint (one block per family per run)
    "blocklist.run_id, blocklist.family_id": ExpectedIntegrityTag.BLOCK_ALREADY_EXISTS,
    # Player name uniqueness within run
    "players.run_id, players.name": ExpectedIntegrityTag.PLAYER_NAME_DUPLICATE,
    # NOTE: route_progress.player_id, run_id, route_id (primary key) is NOT mapped
    # Primary key violations should never happen with proper UPSERT logic
}


def is_unique_violation(exc: IntegrityError) -> bool:
    """Check if the IntegrityError is a unique constraint violation."""
    # For SQLite, check if error message contains "UNIQUE constraint failed"
    error_msg = str(exc.orig) if exc.orig else str(exc)
    return "UNIQUE constraint failed" in error_msg


def extract_constraint_name(exc: IntegrityError) -> Optional[str]:
    """Extract constraint name from IntegrityError."""
    # For SQLite, constraint name is usually in the error message
    error_msg = str(exc.orig) if exc.orig else str(exc)

    # SQLite format: "UNIQUE constraint failed: table.column" or "table.column1, table.column2"
    if "UNIQUE constraint failed:" in error_msg:
        # Extract the part after the colon
        constraint_part = error_msg.split("UNIQUE constraint failed:", 1)[1].strip()

        # Return the exact constraint part - this matches our CONSTRAINT_TAG_MAP keys
        return constraint_part

    return None


def classify_integrity_error(exc: IntegrityError) -> Optional[ExpectedIntegrityTag]:
    """
    Classify an IntegrityError to determine if it's an expected constraint violation.

    Args:
        exc: The IntegrityError exception to classify

    Returns:
        ExpectedIntegrityTag if this is an expected violation, None otherwise
    """
    if not is_unique_violation(exc):
        return None

    constraint_name = extract_constraint_name(exc)
    if constraint_name is None:
        return None

    return CONSTRAINT_TAG_MAP.get(constraint_name)


def log_expected_violation(
    tag: ExpectedIntegrityTag, exc: IntegrityError, context: Dict[str, Any]
) -> None:
    """
    Log an expected integrity violation at INFO level with structured context.

    Args:
        tag: The classification tag for this violation
        exc: The original IntegrityError
        context: Additional context for logging (operation, entity IDs, etc.)
    """
    constraint_name = extract_constraint_name(exc)

    logger.info(
        "Expected integrity violation (treated as success)",
        extra={
            "integrity_tag": tag.value,
            "constraint_name": constraint_name,
            "operation": context.get("operation", "unknown"),
            "entity_type": context.get("entity_type", "unknown"),
            "entity_id": context.get("entity_id"),
            "outcome": "noop",
            "component": "projection_engine",
        },
    )


def get_violation_result(tag: ExpectedIntegrityTag) -> IntegrityViolationResult:
    """
    Get the result type for a given integrity tag.

    Args:
        tag: The expected integrity tag

    Returns:
        The appropriate result enum value
    """
    result_map = {
        ExpectedIntegrityTag.ROUTE_ALREADY_FINALIZED: IntegrityViolationResult.RACE_CONDITION_LOST,
        ExpectedIntegrityTag.BLOCK_ALREADY_EXISTS: IntegrityViolationResult.ALREADY_EXISTS,
        ExpectedIntegrityTag.PLAYER_NAME_DUPLICATE: IntegrityViolationResult.DUPLICATE_IGNORED,
    }

    return result_map.get(tag, IntegrityViolationResult.ALREADY_EXISTS)


def log_unexpected_violation(exc: IntegrityError, context: Dict[str, Any]) -> None:
    """
    Log an unexpected integrity violation at ERROR level.

    Args:
        exc: The IntegrityError that was not expected
        context: Additional context for logging
    """
    constraint_name = extract_constraint_name(exc)

    logger.error(
        "Unexpected integrity violation",
        extra={
            "constraint_name": constraint_name,
            "operation": context.get("operation", "unknown"),
            "entity_type": context.get("entity_type", "unknown"),
            "entity_id": context.get("entity_id"),
            "error_message": str(exc),
            "component": "projection_engine",
        },
        exc_info=exc,
    )
