"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "pois",
        sa.Column("xid", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("kinds", sa.String(), nullable=False, server_default=""),
        sa.Column("rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("wikipedia_excerpt", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "last_fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("xid"),
    )
    # PostGIS generated column for spatial queries
    op.execute(
        "ALTER TABLE pois ADD COLUMN location geography(Point, 4326) "
        "GENERATED ALWAYS AS (ST_MakePoint(lon, lat)) STORED"
    )

    op.create_table(
        "routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "completed", "abandoned", name="routestatus"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("is_circular", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("start_lon", sa.Float(), nullable=False),
        sa.Column("start_lat", sa.Float(), nullable=False),
        sa.Column("total_distance_m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("osrm_geometry", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_routes_user_id", "routes", ["user_id"])

    op.create_table(
        "route_waypoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("poi_xid", sa.String(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_visited", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("leg_duration_s", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["poi_xid"], ["pois.xid"]),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_route_waypoints_route_id", "route_waypoints", ["route_id"])

    op.create_table(
        "user_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("poi_kind", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("interactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "poi_kind"),
    )

    op.create_table(
        "poi_interactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("poi_xid", sa.String(), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("interaction_type", sa.String(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["poi_xid"], ["pois.xid"]),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_poi_interactions_user_id", "poi_interactions", ["user_id"])


def downgrade() -> None:
    op.drop_table("poi_interactions")
    op.drop_table("user_preferences")
    op.drop_table("route_waypoints")
    op.drop_table("routes")
    op.execute("DROP TYPE IF EXISTS routestatus")
    op.drop_table("pois")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS postgis")
