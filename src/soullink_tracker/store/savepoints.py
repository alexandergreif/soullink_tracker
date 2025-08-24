"""
Savepoint utilities for handling expected database constraint violations.

This module provides context managers to isolate database operations that
might trigger expected IntegrityError exceptions, preventing them from
poisoning the outer transaction.
"""

from contextlib import contextmanager
from typing import Set, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .integrity_policy import (
    ExpectedIntegrityTag,
    classify_integrity_error,
    log_expected_violation,
    log_unexpected_violation,
    get_violation_result,
)


from ..utils.logging_config import get_logger

logger = get_logger('database')


@contextmanager
def expected_conflict_savepoint(
    session: Session,
    expected_tags: Set[ExpectedIntegrityTag],
    operation_context: Dict[str, Any],
):
    """
    Context manager that wraps operations in a savepoint and handles expected IntegrityError.

    This allows operations that might hit expected constraint violations to be isolated
    from the main transaction, preventing them from marking the transaction as failed.

    Args:
        session: SQLAlchemy session
        expected_tags: Set of expected integrity violation tags to handle gracefully
        operation_context: Context dict that will be updated with results

    Usage:
        context = {"operation": "finalize_route", "entity_id": str(route_id)}
        with expected_conflict_savepoint(session, {ExpectedIntegrityTag.ROUTE_ALREADY_FINALIZED}, context):
            # Perform potentially conflicting operation
            session.add(RouteProgress(...))
            session.flush()

        # Check result
        if "integrity_tag" in context:
            # Operation hit expected constraint - handle gracefully
            return get_appropriate_result(context["integrity_tag"])
        else:
            # Operation succeeded normally
            return success_result()
    """
    # Create a nested transaction (savepoint)
    nested_transaction = session.begin_nested()

    try:
        yield
        # If we get here, the operation succeeded without constraint violations
        nested_transaction.commit()

    except IntegrityError as exc:
        # Rollback the savepoint to prevent poisoning the outer transaction
        nested_transaction.rollback()

        # Classify the integrity error
        tag = classify_integrity_error(exc)

        if tag and tag in expected_tags:
            # This is an expected constraint violation - handle gracefully
            operation_context["integrity_tag"] = tag
            operation_context["violation_result"] = get_violation_result(tag)

            # Log at INFO level as this is expected behavior
            log_expected_violation(tag, exc, operation_context)

        else:
            # This is an unexpected integrity error - log and re-raise
            log_unexpected_violation(exc, operation_context)
            raise

    except Exception:
        # Any other exception - rollback and re-raise
        nested_transaction.rollback()
        raise


@contextmanager
def graceful_upsert(
    session: Session,
    expected_tag: ExpectedIntegrityTag,
    operation_context: Dict[str, Any],
):
    """
    Simplified context manager for single-tag upsert operations.

    This is a convenience wrapper around expected_conflict_savepoint for
    the common case of handling a single type of constraint violation.

    Args:
        session: SQLAlchemy session
        expected_tag: The expected integrity violation tag to handle
        operation_context: Context dict for logging and results

    Returns:
        True if the operation succeeded normally
        False if it hit the expected constraint violation

    Usage:
        context = {"operation": "add_to_blocklist", "entity_id": f"{run_id}:{family_id}"}
        with graceful_upsert(session, ExpectedIntegrityTag.BLOCK_ALREADY_EXISTS, context) as succeeded:
            session.add(Blocklist(run_id=run_id, family_id=family_id, ...))
            session.flush()

        if not succeeded:
            # Blocklist entry already existed - this is fine
            return BlockResult.ALREADY_EXISTS
        else:
            return BlockResult.CREATED
    """
    with expected_conflict_savepoint(session, {expected_tag}, operation_context):
        yield True  # Indicate success initially

    # If we hit the expected constraint, the context will be updated
    if "integrity_tag" in operation_context:
        yield False  # Indicate the operation was a duplicate/conflict
    # Otherwise the True yield above was correct


class GracefulProjectionError(Exception):
    """Exception for projection errors that have been handled gracefully."""

    def __init__(self, message: str, integrity_tag: ExpectedIntegrityTag):
        super().__init__(message)
        self.integrity_tag = integrity_tag


def handle_projection_integrity_error(
    exc: IntegrityError,
    operation_context: Dict[str, Any],
    expected_tags: Optional[Set[ExpectedIntegrityTag]] = None,
) -> None:
    """
    Handle an IntegrityError that escaped from a projection operation.

    This is a fallback handler for when IntegrityError exceptions bubble up
    from projection operations that weren't wrapped in savepoints.

    Args:
        exc: The IntegrityError exception
        operation_context: Context for logging
        expected_tags: Optional set of expected tags (defaults to all known tags)

    Raises:
        GracefulProjectionError: If this was an expected constraint violation
        IntegrityError: If this was an unexpected violation (re-raises original)
    """
    if expected_tags is None:
        # Default to all known expected tags
        expected_tags = {
            ExpectedIntegrityTag.ROUTE_ALREADY_FINALIZED,
            ExpectedIntegrityTag.BLOCK_ALREADY_EXISTS,
            ExpectedIntegrityTag.PLAYER_NAME_DUPLICATE,
        }

    tag = classify_integrity_error(exc)

    if tag and tag in expected_tags:
        # This is an expected constraint violation
        log_expected_violation(tag, exc, operation_context)
        raise GracefulProjectionError(
            f"Expected constraint violation: {tag.value}", integrity_tag=tag
        )
    else:
        # This is unexpected - log and re-raise
        log_unexpected_violation(exc, operation_context)
        raise
