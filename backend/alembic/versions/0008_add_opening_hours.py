"""add opening_hours to pois

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-02 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pois", sa.Column("opening_hours", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("pois", "opening_hours")
