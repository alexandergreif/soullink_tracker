"""add_race_safety_constraints_for_fe_and_blocklist

Revision ID: 0094210dc7ad
Revises: fc70a33205b2
Create Date: 2025-08-10 18:42:53.600558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0094210dc7ad'
down_revision: Union[str, Sequence[str], None] = 'fc70a33205b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add race safety constraints for first encounter finalization and blocklist."""
    
    from sqlalchemy import text
    bind = op.get_bind()
    
    # First, drop the incorrect constraint from the previous migration
    # It was UNIQUE(run_id, route_id) but should be UNIQUE(run_id, route_id) globally
    # meaning only one player can finalize per route per run
    try:
        op.execute(text("DROP INDEX IF EXISTS uq_route_progress_fe_finalized"))
    except Exception:
        pass  # Ignore if it doesn't exist
    
    # Add the correct partial unique constraint for route_progress table
    # This prevents multiple players from finalizing first encounter on the same route
    # UNIQUE(run_id, route_id) WHERE fe_finalized=TRUE (globally across all players)
    # Note: SQLite doesn't support CONCURRENTLY, so we detect the database type
    
    if 'sqlite' in str(bind.dialect.name).lower():
        # SQLite version without CONCURRENTLY
        op.execute(text("""
            CREATE UNIQUE INDEX ix_route_progress_fe_unique
            ON route_progress (run_id, route_id)
            WHERE fe_finalized = true
        """))
        
        # Add index to improve performance of race condition checks
        op.execute(text("""
            CREATE INDEX ix_blocklist_family_lookup
            ON blocklist (run_id, family_id, created_at)
        """))
    else:
        # PostgreSQL version with CONCURRENTLY
        op.execute(text("""
            CREATE UNIQUE INDEX CONCURRENTLY ix_route_progress_fe_unique
            ON route_progress (run_id, route_id)
            WHERE fe_finalized = true
        """))
        
        # Add index to improve performance of race condition checks
        op.execute(text("""
            CREATE INDEX CONCURRENTLY ix_blocklist_family_lookup
            ON blocklist (run_id, family_id, created_at)
        """))


def downgrade() -> None:
    """Remove race safety constraints."""
    
    # Remove the unique constraint for first encounter finalization
    from sqlalchemy import text
    bind = op.get_bind()
    
    if 'sqlite' in str(bind.dialect.name).lower():
        # SQLite version
        op.execute(text("DROP INDEX IF EXISTS ix_route_progress_fe_unique"))
        op.execute(text("DROP INDEX IF EXISTS ix_blocklist_family_lookup"))
    else:
        # PostgreSQL version with CONCURRENTLY
        op.execute(text("DROP INDEX CONCURRENTLY IF EXISTS ix_route_progress_fe_unique"))
        op.execute(text("DROP INDEX CONCURRENTLY IF EXISTS ix_blocklist_family_lookup"))
