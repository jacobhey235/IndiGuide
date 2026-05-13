"""fix poi_interactions route_id FK to SET NULL on route delete

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-13 00:00:00.000000
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "poi_interactions_route_id_fkey", "poi_interactions", type_="foreignkey"
    )
    op.create_foreign_key(
        "poi_interactions_route_id_fkey",
        "poi_interactions",
        "routes",
        ["route_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "poi_interactions_route_id_fkey", "poi_interactions", type_="foreignkey"
    )
    op.create_foreign_key(
        "poi_interactions_route_id_fkey",
        "poi_interactions",
        "routes",
        ["route_id"],
        ["id"],
    )
