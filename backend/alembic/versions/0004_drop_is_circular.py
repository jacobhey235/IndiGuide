"""drop is_circular from routes

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("routes", "is_circular")


def downgrade() -> None:
    op.add_column(
        "routes",
        sa.Column("is_circular", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
