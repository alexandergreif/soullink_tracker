"""add_password_auth_and_player_sessions

Revision ID: b4ff90703237
Revises: 0094210dc7ad
Create Date: 2025-08-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Import custom types
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
import soullink_tracker.db.models


# revision identifiers, used by Alembic.
revision: str = 'b4ff90703237'
down_revision: Union[str, Sequence[str], None] = '0094210dc7ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add password-based authentication fields and player sessions."""
    
    # Add password fields to runs table
    op.add_column('runs', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('runs', sa.Column('password_salt', sa.String(length=64), nullable=True))
    
    # Create player_sessions table
    op.create_table('player_sessions',
        sa.Column('id', soullink_tracker.db.models.GUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('run_id', soullink_tracker.db.models.GUID(), nullable=False),
        sa.Column('player_id', soullink_tracker.db.models.GUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    
    # Create indexes for player_sessions
    op.create_index('ix_player_session_token_hash', 'player_sessions', ['token_hash'], unique=False)
    op.create_index('ix_player_session_expires_at', 'player_sessions', ['expires_at'], unique=False)
    op.create_index('ix_player_session_run_player', 'player_sessions', ['run_id', 'player_id'], unique=False)


def downgrade() -> None:
    """Remove password authentication fields and player sessions."""
    
    # Drop player_sessions table and its indexes
    op.drop_index('ix_player_session_run_player', table_name='player_sessions')
    op.drop_index('ix_player_session_expires_at', table_name='player_sessions')
    op.drop_index('ix_player_session_token_hash', table_name='player_sessions')
    op.drop_table('player_sessions')
    
    # Remove password fields from runs table
    op.drop_column('runs', 'password_salt')
    op.drop_column('runs', 'password_hash')