"""simplify client_profiles: drop demographic_targets, add preferences JSONB

Revision ID: f1a2b3c4d5e6
Revises: 518f0583e5eb
Create Date: 2026-07-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "518f0583e5eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("demographic_targets")
    op.add_column(
        "client_profiles",
        sa.Column("preferences", postgresql.JSONB(), nullable=True),
    )
    op.drop_column("client_profiles", "competitor_types")
    op.drop_column("client_profiles", "complimentary_types")
    op.drop_column("client_profiles", "target_income_min")
    op.drop_column("client_profiles", "target_income_max")
    op.drop_column("client_profiles", "location_preference")


def downgrade() -> None:
    op.add_column(
        "client_profiles",
        sa.Column("location_preference", sa.String(), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column("target_income_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column("target_income_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column("complimentary_types", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column("competitor_types", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.drop_column("client_profiles", "preferences")
    op.create_table(
        "demographic_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "client_profile_id",
            sa.String(),
            sa.ForeignKey("client_profiles.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("demographic_key", sa.String(length=50), nullable=False),
        sa.Column("constraint_type", sa.String(length=20), nullable=True),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("target_percentage", sa.Float(), nullable=True),
        sa.Column("percentage_operator", sa.String(length=5), nullable=True),
        sa.Column("importance_weight", sa.Float(), nullable=False),
    )
