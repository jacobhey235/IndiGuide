from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.poi import POI
from app.models.user import User
from app.schemas.poi import POIDetail
from app.services.opentripmap import OpenTripMapClient

router = APIRouter()

_CACHE_TTL = timedelta(days=7)


@router.get("/{xid}", response_model=POIDetail)
async def get_poi(
    xid: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    poi = await db.get(POI, xid)
    now = datetime.now(timezone.utc)

    if poi is not None:
        age = now - poi.last_fetched_at.replace(tzinfo=timezone.utc)
        if age < _CACHE_TTL and poi.wikipedia_excerpt is not None:
            return poi

    try:
        otm = OpenTripMapClient(request.app.state.http_client)
        detail = await otm.fetch_detail(xid)
    except Exception:
        if poi is not None:
            return poi
        raise HTTPException(status_code=502, detail="Could not fetch POI details")

    if poi is None:
        poi = POI(xid=xid)
        db.add(poi)

    poi.name = detail.name
    poi.lon = detail.lon
    poi.lat = detail.lat
    poi.kinds = detail.kinds
    poi.rate = detail.rate
    poi.wikipedia_excerpt = detail.wikipedia_excerpt
    poi.image_url = detail.image_url
    poi.address = detail.address
    poi.last_fetched_at = now

    await db.commit()
    await db.refresh(poi)
    return poi
