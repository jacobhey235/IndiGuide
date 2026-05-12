from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services import preferences as pref_svc
from app.services.route_categories import CATEGORIES

router = APIRouter()


class CategoryScore(BaseModel):
    category: str
    score: float


@router.get("/categories", response_model=list[CategoryScore])
async def get_category_preferences(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pref_map = await pref_svc.get_preference_map(db, user.id)
    result: list[CategoryScore] = []
    for cat_key, kinds in CATEGORIES.items():
        scores = [pref_map.get(k, 0.5) for k in kinds]
        result.append(CategoryScore(category=cat_key, score=sum(scores) / len(scores)))
    return result
