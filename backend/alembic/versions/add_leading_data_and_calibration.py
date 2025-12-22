"""Add leading data tables and columns for enhanced prediction

Revision ID: add_leading_data
Revises: add_training_table
Create Date: 2025-12-20 21:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_leading_data'
down_revision: Union[str, None] = 'add_training_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === 騎手テーブルにリーディングデータカラムを追加 ===
    op.add_column('jockeys', sa.Column('year_rank', sa.Integer(), nullable=True))
    op.add_column('jockeys', sa.Column('year_wins', sa.Integer(), nullable=True))
    op.add_column('jockeys', sa.Column('year_rides', sa.Integer(), nullable=True))
    op.add_column('jockeys', sa.Column('year_earnings', sa.Integer(), nullable=True))

    # === 調教師テーブルを作成 ===
    op.create_table('trainers',
        sa.Column('trainer_id', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('place_rate', sa.Float(), nullable=True),
        sa.Column('show_rate', sa.Float(), nullable=True),
        sa.Column('year_rank', sa.Integer(), nullable=True),
        sa.Column('year_wins', sa.Integer(), nullable=True),
        sa.Column('year_entries', sa.Integer(), nullable=True),
        sa.Column('year_earnings', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('trainer_id')
    )

    # === 種牡馬テーブルを作成 ===
    op.create_table('sires',
        sa.Column('sire_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('place_rate', sa.Float(), nullable=True),
        sa.Column('show_rate', sa.Float(), nullable=True),
        sa.Column('year_rank', sa.Integer(), nullable=True),
        sa.Column('year_wins', sa.Integer(), nullable=True),
        sa.Column('year_runners', sa.Integer(), nullable=True),
        sa.Column('year_earnings', sa.Integer(), nullable=True),
        sa.Column('turf_win_rate', sa.Float(), nullable=True),
        sa.Column('dirt_win_rate', sa.Float(), nullable=True),
        sa.Column('short_win_rate', sa.Float(), nullable=True),
        sa.Column('mile_win_rate', sa.Float(), nullable=True),
        sa.Column('middle_win_rate', sa.Float(), nullable=True),
        sa.Column('long_win_rate', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('sire_id')
    )


def downgrade() -> None:
    # === 種牡馬テーブルを削除 ===
    op.drop_table('sires')

    # === 調教師テーブルを削除 ===
    op.drop_table('trainers')

    # === 騎手テーブルからリーディングデータカラムを削除 ===
    op.drop_column('jockeys', 'year_earnings')
    op.drop_column('jockeys', 'year_rides')
    op.drop_column('jockeys', 'year_wins')
    op.drop_column('jockeys', 'year_rank')
