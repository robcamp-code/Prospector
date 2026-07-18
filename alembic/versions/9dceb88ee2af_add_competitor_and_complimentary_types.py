"""add_competitor_and_complimentary_types

Revision ID: 9dceb88ee2af
Revises: 4266e2b64014
Create Date: 2026-07-17 17:11:52.514204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9dceb88ee2af'
down_revision: Union[str, None] = '4266e2b64014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the missing columns for place type arrays
    op.add_column('client_profiles', sa.Column('competitor_types', postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column('client_profiles', sa.Column('complimentary_types', postgresql.ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column('client_profiles', 'complimentary_types')
    op.drop_column('client_profiles', 'competitor_types')
