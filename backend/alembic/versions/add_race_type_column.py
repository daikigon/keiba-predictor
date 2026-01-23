"""add_race_type_column

Revision ID: add_race_type
Revises: ae226a6d8178
Create Date: 2026-01-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_race_type'
down_revision: Union[str, None] = 'ae226a6d8178'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add race_type column with default 'central' for existing data
    op.add_column('races', sa.Column('race_type', sa.String(length=10), nullable=True))

    # Set default value for existing records
    op.execute("UPDATE races SET race_type = 'central' WHERE race_type IS NULL")

    # Make column NOT NULL after setting defaults
    op.alter_column('races', 'race_type', nullable=False)

    # Create index for race_type column
    op.create_index('ix_races_race_type', 'races', ['race_type'])


def downgrade() -> None:
    op.drop_index('ix_races_race_type', table_name='races')
    op.drop_column('races', 'race_type')
