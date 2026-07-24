"""drop client profile tables

Revision ID: e5089907aef2
Revises: bb3e5221d186
Create Date: 2026-07-22 19:43:41.862151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5089907aef2'
down_revision: Union[str, None] = 'bb3e5221d186'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop demographic_targets first (foreign key dependency)
    op.drop_table('demographic_targets')
    # Then drop client_profiles
    op.drop_table('client_profiles')


def downgrade() -> None:
    # Recreate client_profiles
    op.create_table(
        'client_profiles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('business_type', sa.String(length=100), nullable=True),
        sa.Column('service_description', sa.String(), nullable=True),
        sa.Column('conversation_id', sa.String(length=255), nullable=True),
        sa.Column('competitor_types', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('complimentary_types', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id'),
    )
    # Recreate demographic_targets
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
