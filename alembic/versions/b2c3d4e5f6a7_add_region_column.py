"""add_region_column

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-18 10:01:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Region mapping based on _docs.md
REGION_MAP = {
    "East Coast": [
        "Maine",
        "New Hampshire",
        "Vermont",
        "Massachusetts",
        "Rhode Island",
        "Connecticut",
        "New York",
        "New Jersey",
        "Pennsylvania",
        "Delaware",
        "Maryland",
        "Virginia",
        "North Carolina",
        "South Carolina",
        "Georgia",
        "Florida",
    ],
    "West Coast": [
        "California",
        "Oregon",
        "Washington",
        "Alaska",
        "Hawaii",
    ],
    "Midwest": [
        "Ohio",
        "Indiana",
        "Illinois",
        "Michigan",
        "Wisconsin",
        "Minnesota",
        "Iowa",
        "Missouri",
        "North Dakota",
        "South Dakota",
        "Nebraska",
        "Kansas",
    ],
    "South": [
        "Texas",
        "Oklahoma",
        "Arkansas",
        "Louisiana",
        "Mississippi",
        "Alabama",
        "Tennessee",
        "Kentucky",
        "West Virginia",
    ],
    "Mountain West": [
        "Montana",
        "Idaho",
        "Wyoming",
        "Colorado",
        "New Mexico",
        "Arizona",
        "Utah",
        "Nevada",
    ],
}


def upgrade() -> None:
    # Add region column to uszips
    op.add_column("uszips", sa.Column("region", sa.String(20), nullable=True))

    # Create index for region queries
    op.create_index("ix_uszips_region", "uszips", ["region"])

    # Populate region based on state_name
    for region, states in REGION_MAP.items():
        # Build a properly escaped list of states
        states_list = ", ".join(f"'{state}'" for state in states)
        op.execute(
            f"UPDATE uszips SET region = '{region}' WHERE state_name IN ({states_list})"
        )


def downgrade() -> None:
    op.drop_index("ix_uszips_region", table_name="uszips")
    op.drop_column("uszips", "region")
