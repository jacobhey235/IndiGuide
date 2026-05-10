from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.poi import POI


class RouteStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    completed = "completed"
    abandoned = "abandoned"


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[RouteStatus] = mapped_column(
        Enum(RouteStatus), default=RouteStatus.draft, nullable=False
    )
    is_circular: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    start_lon: Mapped[float] = mapped_column(Float, nullable=False)
    start_lat: Mapped[float] = mapped_column(Float, nullable=False)
    total_distance_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    osrm_geometry: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="routes")
    waypoints: Mapped[list[RouteWaypoint]] = relationship(
        back_populates="route",
        order_by="RouteWaypoint.order_index",
        cascade="all, delete-orphan",
    )


class RouteWaypoint(Base):
    __tablename__ = "route_waypoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routes.id"), nullable=False, index=True
    )
    poi_xid: Mapped[str] = mapped_column(ForeignKey("pois.xid"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_visited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leg_duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)

    route: Mapped[Route] = relationship(back_populates="waypoints")
    poi: Mapped[POI] = relationship()
