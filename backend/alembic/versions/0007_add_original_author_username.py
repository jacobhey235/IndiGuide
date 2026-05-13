"""add original_author_username to routes

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-13 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("routes", sa.Column("original_author_username", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("routes", "original_author_username")
