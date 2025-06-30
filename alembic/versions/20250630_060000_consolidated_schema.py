"""Consolidated schema for forex trading system

Revision ID: consolidated_001
Revises: 
Create Date: 2025-06-30 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'consolidated_001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create forex_rates table
    op.create_table('forex_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('currency_pair', sa.String(), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.Column('bid', sa.Float(), nullable=True),
        sa.Column('ask', sa.Float(), nullable=True),
        sa.Column('volume', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_forex_rates_currency_pair'), 'forex_rates', ['currency_pair'], unique=False)
    op.create_index(op.f('ix_forex_rates_id'), 'forex_rates', ['id'], unique=False)
    op.create_index(op.f('ix_forex_rates_timestamp'), 'forex_rates', ['timestamp'], unique=False)
    
    # Create candlestick_data table
    op.create_table('candlestick_data',
        sa.Column('symbol', sa.TEXT(), nullable=False),
        sa.Column('timeframe', sa.TEXT(), nullable=False),
        sa.Column('open_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('close_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('open_price', sa.DECIMAL(precision=12, scale=6), nullable=False),
        sa.Column('high_price', sa.DECIMAL(precision=12, scale=6), nullable=False),
        sa.Column('low_price', sa.DECIMAL(precision=12, scale=6), nullable=False),
        sa.Column('close_price', sa.DECIMAL(precision=12, scale=6), nullable=False),
        sa.Column('tick_count', sa.INTEGER(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('symbol', 'timeframe', 'open_time')
    )
    
    # Create technical_indicators table
    op.create_table('technical_indicators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('timeframe', sa.String(length=5), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ema_5', sa.Float(), nullable=True),
        sa.Column('ema_10', sa.Float(), nullable=True),
        sa.Column('ema_15', sa.Float(), nullable=True),
        sa.Column('ema_20', sa.Float(), nullable=True),
        sa.Column('ema_50', sa.Float(), nullable=True),
        sa.Column('ema_100', sa.Float(), nullable=True),
        sa.Column('ema_200', sa.Float(), nullable=True),
        sa.Column('rsi_14', sa.Float(), nullable=True),
        sa.Column('macd', sa.Float(), nullable=True),
        sa.Column('macd_signal', sa.Float(), nullable=True),
        sa.Column('macd_histogram', sa.Float(), nullable=True),
        sa.Column('bb_upper', sa.Float(), nullable=True),
        sa.Column('bb_middle', sa.Float(), nullable=True),
        sa.Column('bb_lower', sa.Float(), nullable=True),
        sa.Column('atr_14', sa.Float(), nullable=True),
        sa.Column('stoch_k', sa.Float(), nullable=True),
        sa.Column('stoch_d', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_technical_indicators_symbol_timeframe_timestamp', 'technical_indicators', ['symbol', 'timeframe', 'timestamp'], unique=False)
    op.create_index(op.f('ix_technical_indicators_id'), 'technical_indicators', ['id'], unique=False)
    
    # Create entry_signals table
    op.create_table('entry_signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('timeframe', sa.String(length=5), nullable=False),
        sa.Column('signal_type', sa.String(length=10), nullable=False),
        sa.Column('pattern_type', sa.String(length=50), nullable=True),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_entry_signals_id'), 'entry_signals', ['id'], unique=False)
    op.create_index('idx_entry_signals_symbol_timeframe', 'entry_signals', ['symbol', 'timeframe'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_entry_signals_symbol_timeframe', table_name='entry_signals')
    op.drop_index(op.f('ix_entry_signals_id'), table_name='entry_signals')
    op.drop_table('entry_signals')
    op.drop_index(op.f('ix_technical_indicators_id'), table_name='technical_indicators')
    op.drop_index('idx_technical_indicators_symbol_timeframe_timestamp', table_name='technical_indicators')
    op.drop_table('technical_indicators')
    op.drop_table('candlestick_data')
    op.drop_index(op.f('ix_forex_rates_timestamp'), table_name='forex_rates')
    op.drop_index(op.f('ix_forex_rates_id'), table_name='forex_rates')
    op.drop_index(op.f('ix_forex_rates_currency_pair'), table_name='forex_rates')
    op.drop_table('forex_rates')