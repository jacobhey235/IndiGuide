from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.route import Route
    from app.models.preferences import UserPreference, POIInteraction


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    routes: Mapped[list[Route]] = relationship(back_populates="user", cascade="all, delete-orphan")
    preferences: Mapped[list[UserPreference]] = relationship(back_populates="user", cascade="all, delete-orphan")
    interactions: Mapped[list[POIInteraction]] = relationship(back_populates="user", cascade="all, delete-orphan")
