"""add_demographic_targets

Revision ID: a1b2c3d4e5f6
Revises: 9dceb88ee2af
Create Date: 2026-07-18 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9dceb88ee2af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create demographic_targets table
    op.create_table(
        "demographic_targets",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "client_profile_id",
            sa.Integer(),
            sa.ForeignKey("client_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Target criteria
        sa.Column("demographic_key", sa.String(50), nullable=False),
        sa.Column("constraint_type", sa.String(20), nullable=False, server_default="range"),
        # Range-based constraints
        sa.Column("min_value", sa.Double(), nullable=True),
        sa.Column("max_value", sa.Double(), nullable=True),
        # Percentage-based constraints
        sa.Column("target_percentage", sa.Double(), nullable=True),
        sa.Column("percentage_operator", sa.String(5), nullable=True),
        # Weight for scoring
        sa.Column("importance_weight", sa.Double(), nullable=False, server_default="0.5"),
    )

    # Create index on client_profile_id for efficient lookups
    op.create_index(
        "ix_demographic_targets_client_profile_id",
        "demographic_targets",
        ["client_profile_id"],
    )

    # Drop old columns from client_profiles that are now replaced
    # by the demographic_targets relationship
    op.drop_column("client_profiles", "target_income_min")
    op.drop_column("client_profiles", "target_income_max")
    op.drop_column("client_profiles", "target_age_min")
    op.drop_column("client_profiles", "target_age_max")
    op.drop_column("client_profiles", "target_home_ownership_min")
    op.drop_column("client_profiles", "target_education_min")
    op.drop_column("client_profiles", "custom_weights")


def downgrade() -> None:
    # Re-add old columns to client_profiles
    op.add_column(
        "client_profiles",
        sa.Column("target_income_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column("target_income_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column("target_age_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column("target_age_max", sa.Integer(), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column("target_home_ownership_min", sa.Double(), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column("target_education_min", sa.Double(), nullable=True),
    )
    op.add_column(
        "client_profiles",
        sa.Column(
            "custom_weights",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
    )

    # Drop the demographic_targets table
    op.drop_index("ix_demographic_targets_client_profile_id", table_name="demographic_targets")
    op.drop_table("demographic_targets")
