from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.poi import POI
from app.models.preferences import POIInteraction, UserPreference

_ALPHA_PASSIVE = 0.15    # EMA smoothing for passive visit / removal signals
_ALPHA_REACTION = 0.22   # slightly stronger EMA for explicit like / dislike


async def get_preference_map(db: AsyncSession, user_id: uuid.UUID) -> dict[str, float]:
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    return {p.poi_kind: p.score for p in result.scalars().all()}


async def get_disliked_poi_xids(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    result = await db.execute(
        select(POIInteraction.poi_xid)
        .where(POIInteraction.user_id == user_id)
        .where(POIInteraction.interaction_type == "disliked")
    )
    return set(result.scalars().all())


async def update_on_visit(
    db: AsyncSession, user_id: uuid.UUID, poi: POI, route_id: uuid.UUID | None = None
) -> None:
    await _apply_ema(db, user_id, poi, target=1.0)
    db.add(
        POIInteraction(
            user_id=user_id,
            poi_xid=poi.xid,
            route_id=route_id,
            interaction_type="visited",
        )
    )
    await db.commit()


async def update_on_removal(
    db: AsyncSession, user_id: uuid.UUID, poi: POI, route_id: uuid.UUID | None = None
) -> None:
    await _apply_ema(db, user_id, poi, target=0.0)
    db.add(
        POIInteraction(
            user_id=user_id,
            poi_xid=poi.xid,
            route_id=route_id,
            interaction_type="removed",
        )
    )
    await db.commit()


async def update_on_like(
    db: AsyncSession, user_id: uuid.UUID, poi: POI, route_id: uuid.UUID | None = None
) -> None:
    await _apply_ema(db, user_id, poi, target=1.0, alpha=_ALPHA_REACTION)
    db.add(
        POIInteraction(
            user_id=user_id,
            poi_xid=poi.xid,
            route_id=route_id,
            interaction_type="liked",
        )
    )
    await db.commit()


async def update_on_dislike(
    db: AsyncSession, user_id: uuid.UUID, poi: POI, route_id: uuid.UUID | None = None
) -> None:
    await _apply_ema(db, user_id, poi, target=0.0, alpha=_ALPHA_REACTION)
    db.add(
        POIInteraction(
            user_id=user_id,
            poi_xid=poi.xid,
            route_id=route_id,
            interaction_type="disliked",
        )
    )
    await db.commit()


async def _apply_ema(
    db: AsyncSession, user_id: uuid.UUID, poi: POI, target: float, alpha: float = _ALPHA_PASSIVE
) -> None:
    kinds = [k.strip() for k in poi.kinds.split(",") if k.strip()]
    for kind in kinds:
        pref = await db.get(UserPreference, (user_id, kind))
        if pref is None:
            pref = UserPreference(user_id=user_id, poi_kind=kind, score=0.5, interactions=0)
            db.add(pref)
        pref.score = pref.score * (1 - alpha) + alpha * target
        pref.interactions += 1
        pref.last_updated_at = datetime.now(timezone.utc)
