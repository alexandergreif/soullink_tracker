"""add idempotency key unique constraint

Revision ID: 85c1bb586534
Revises: b4ff90703237
Create Date: 2025-08-23 17:36:34.768662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85c1bb586534'
down_revision: Union[str, Sequence[str], None] = 'b4ff90703237'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint to idempotency_keys to prevent race conditions."""
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('idempotency_keys') as batch_op:
        batch_op.create_unique_constraint(
            'uq_idempotency_full',
            ['key', 'run_id', 'player_id', 'request_hash']
        )


def downgrade() -> None:
    """Remove the unique constraint."""
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('idempotency_keys') as batch_op:
        batch_op.drop_constraint('uq_idempotency_full', type_='unique')
