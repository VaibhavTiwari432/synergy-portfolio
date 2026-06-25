"""
Alembic migration 014: Two-table event log architecture (Item #8)

Creates human_control_signals and ai_action_log tables.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    # Create human_control_signals table
    op.create_table(
        'human_control_signals',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('turn_id', sa.Integer, nullable=False),
        sa.Column('control_signal_type',
                  sa.String(50), nullable=False),  # 'selective_rejection', 'exogenous_injection', etc.
        sa.Column('source_neuron_id', sa.String(32)),
        sa.Column('confidence', sa.Float),
        sa.Column('provenance', sa.String(50)),  # 'displayed' or 'implied'
        sa.Column('timestamp', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('session_id', 'turn_id', 'control_signal_type',
                            name='uc_human_control_signals'),
    )
    op.create_index('ix_human_control_signals_session', 'human_control_signals', ['session_id'])
    op.create_index('ix_human_control_signals_turn', 'human_control_signals', ['turn_id'])

    # Create ai_action_log table
    op.create_table(
        'ai_action_log',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('turn_id', sa.Integer, nullable=False),
        sa.Column('ai_act_type',
                  sa.String(50), nullable=False),  # 'retrieval', 'generation', 'structuring', etc.
        sa.Column('content_ref', sa.String(256)),
        sa.Column('confidence', sa.Float),
        sa.Column('timestamp', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('session_id', 'turn_id', 'ai_act_type',
                            name='uc_ai_action_log'),
    )
    op.create_index('ix_ai_action_log_session', 'ai_action_log', ['session_id'])
    op.create_index('ix_ai_action_log_turn', 'ai_action_log', ['turn_id'])


def downgrade():
    op.drop_table('ai_action_log')
    op.drop_table('human_control_signals')
