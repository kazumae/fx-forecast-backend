"""US-014: Create forex persistence schema

Revision ID: us014_forex_persistence
Revises: previous_revision
Create Date: 2024-06-29 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'us014_forex_persistence'
down_revision = None  # Update this with actual previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create forex rates and archive tables for US-014"""
    
    # Create main forex_rates table
    op.create_table(
        'forex_rates',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('bid', sa.DECIMAL(precision=10, scale=5), nullable=False),
        sa.Column('ask', sa.DECIMAL(precision=10, scale=5), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'timestamp', name='uq_symbol_timestamp')
    )
    
    # Create indexes for efficient time-series queries
    op.create_index('ix_forex_rates_id', 'forex_rates', ['id'])
    op.create_index('ix_forex_rates_symbol', 'forex_rates', ['symbol'])
    op.create_index('ix_forex_rates_timestamp', 'forex_rates', ['timestamp'])
    op.create_index('ix_symbol_timestamp_desc', 'forex_rates', ['symbol', 'timestamp'])
    
    # Create archive table
    op.create_table(
        'forex_rates_archive',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('bid', sa.DECIMAL(precision=10, scale=5), nullable=False),
        sa.Column('ask', sa.DECIMAL(precision=10, scale=5), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for archive table
    op.create_index('ix_forex_rates_archive_id', 'forex_rates_archive', ['id'])
    op.create_index('ix_forex_rates_archive_symbol', 'forex_rates_archive', ['symbol'])
    op.create_index('ix_forex_rates_archive_timestamp', 'forex_rates_archive', ['timestamp'])
    op.create_index('ix_archive_symbol_timestamp', 'forex_rates_archive', ['symbol', 'timestamp'])


def downgrade() -> None:
    """Drop forex persistence tables"""
    
    # Drop indexes first
    op.drop_index('ix_archive_symbol_timestamp', 'forex_rates_archive')
    op.drop_index('ix_forex_rates_archive_timestamp', 'forex_rates_archive')
    op.drop_index('ix_forex_rates_archive_symbol', 'forex_rates_archive')
    op.drop_index('ix_forex_rates_archive_id', 'forex_rates_archive')
    
    op.drop_index('ix_symbol_timestamp_desc', 'forex_rates')
    op.drop_index('ix_forex_rates_timestamp', 'forex_rates')
    op.drop_index('ix_forex_rates_symbol', 'forex_rates')
    op.drop_index('ix_forex_rates_id', 'forex_rates')
    
    # Drop tables
    op.drop_table('forex_rates_archive')
    op.drop_table('forex_rates')