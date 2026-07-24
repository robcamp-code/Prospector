"""recreate client profile tables and add reports

Revision ID: 518f0583e5eb
Revises: e5089907aef2
Create Date: 2026-07-22 21:07:58.008821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '518f0583e5eb'
down_revision: Union[str, None] = 'e5089907aef2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create client_profiles table
    op.create_table(
        'client_profiles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('business_type', sa.String(length=100), nullable=True),
        sa.Column('service_description', sa.String(), nullable=True),
        sa.Column('conversation_id', sa.String(length=255), nullable=True),
        sa.Column('competitor_types', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('complimentary_types', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('target_income_min', sa.Integer(), nullable=True),
        sa.Column('target_income_max', sa.Integer(), nullable=True),
        sa.Column('location_preference', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id'),
    )
    op.create_index(op.f('ix_client_profiles_conversation_id'), 'client_profiles', ['conversation_id'], unique=True)

    # Create demographic_targets table
    op.create_table(
        'demographic_targets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_profile_id', sa.String(), nullable=False),
        sa.Column('demographic_key', sa.String(length=50), nullable=False),
        sa.Column('constraint_type', sa.String(length=20), nullable=False),
        sa.Column('min_value', sa.Float(), nullable=True),
        sa.Column('max_value', sa.Float(), nullable=True),
        sa.Column('target_percentage', sa.Float(), nullable=True),
        sa.Column('percentage_operator', sa.String(length=5), nullable=True),
        sa.Column('importance_weight', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['client_profile_id'], ['client_profiles.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_demographic_targets_client_profile_id'), 'demographic_targets', ['client_profile_id'], unique=False)

    # Create reports table
    op.create_table(
        'reports',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('client_profile_id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('subtitle', sa.String(), nullable=True),
        sa.Column('geography_type', sa.String(), nullable=False),
        sa.Column('geography_value', sa.String(), nullable=False),
        sa.Column('summary', postgresql.JSONB(), nullable=False),
        sa.Column('sections', postgresql.JSONB(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['client_profile_id'], ['client_profiles.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reports_client_profile_id'), 'reports', ['client_profile_id'], unique=False)
    op.create_index(op.f('ix_reports_conversation_id'), 'reports', ['conversation_id'], unique=False)


def downgrade() -> None:
    # Drop reports table
    op.drop_index(op.f('ix_reports_conversation_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_client_profile_id'), table_name='reports')
    op.drop_table('reports')

    # Drop demographic_targets table
    op.drop_index(op.f('ix_demographic_targets_client_profile_id'), table_name='demographic_targets')
    op.drop_table('demographic_targets')

    # Drop client_profiles table
    op.drop_index(op.f('ix_client_profiles_conversation_id'), table_name='client_profiles')
    op.drop_table('client_profiles')
