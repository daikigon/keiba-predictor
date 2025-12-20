"""Add training table

Revision ID: add_training_table
Revises: 27d1d595ca74
Create Date: 2025-12-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_training_table'
down_revision: Union[str, None] = '27d1d595ca74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('trainings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('race_id', sa.String(length=20), nullable=False),
        sa.Column('horse_id', sa.String(length=20), nullable=False),
        sa.Column('horse_number', sa.Integer(), nullable=True),
        sa.Column('training_course', sa.String(length=50), nullable=True),
        sa.Column('training_time', sa.String(length=20), nullable=True),
        sa.Column('lap_times', sa.String(length=50), nullable=True),
        sa.Column('training_rank', sa.String(length=5), nullable=True),
        sa.Column('training_date', sa.String(length=20), nullable=True),
        sa.Column('rider', sa.String(length=50), nullable=True),
        sa.Column('comment', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['horse_id'], ['horses.horse_id'], ),
        sa.ForeignKeyConstraint(['race_id'], ['races.race_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trainings_horse_id'), 'trainings', ['horse_id'], unique=False)
    op.create_index(op.f('ix_trainings_race_id'), 'trainings', ['race_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trainings_race_id'), table_name='trainings')
    op.drop_index(op.f('ix_trainings_horse_id'), table_name='trainings')
    op.drop_table('trainings')
