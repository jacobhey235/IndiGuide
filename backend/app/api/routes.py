from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.route import Route, RouteStatus, RouteWaypoint
from app.models.user import User
from app.schemas.route import RouteGenerateRequest, RouteOut, RouteSummary, RouteUpdateRequest
from app.services import preferences as pref_svc
from app.services.route_generator import generate_route

router = APIRouter()

_ROUTE_OPTIONS = selectinload(Route.waypoints).selectinload(RouteWaypoint.poi)


async def _get_user_route(route_id: uuid.UUID, user: User, db: AsyncSession) -> Route:
    result = await db.execute(
        select(Route).options(_ROUTE_OPTIONS).where(Route.id == route_id)
    )
    route = result.scalar_one_or_none()
    if route is None or route.user_id != user.id:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.post("/generate", response_model=RouteOut, status_code=201)
async def generate(
    body: RouteGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        route = await generate_route(
            db=db,
            http_client=request.app.state.http_client,
            user=user,
            start_lat=body.start_lat,
            start_lon=body.start_lon,
            distance_m=body.distance_m,
            num_pois=body.num_pois,
            is_circular=body.is_circular,
            name=body.name,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=503, detail=f"External service error: {e.response.status_code}")

    result = await db.execute(
        select(Route).options(_ROUTE_OPTIONS).where(Route.id == route.id)
    )
    return result.scalar_one()


@router.get("/", response_model=list[RouteSummary])
async def list_routes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Route)
        .options(_ROUTE_OPTIONS)
        .where(Route.user_id == user.id, Route.is_saved == True)  # noqa: E712
        .order_by(Route.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{route_id}", response_model=RouteOut)
async def get_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_user_route(route_id, user, db)


@router.put("/{route_id}", response_model=RouteOut)
async def update_route(
    route_id: uuid.UUID,
    body: RouteUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)

    if body.name is not None:
        route.name = body.name

    if body.is_saved is not None:
        route.is_saved = body.is_saved

    if body.remove_poi_xids:
        to_remove = [w for w in route.waypoints if w.poi_xid in body.remove_poi_xids]
        for wp in to_remove:
            if route.status == RouteStatus.draft:
                await pref_svc.update_on_removal(db, user.id, wp.poi, route.id)
            route.waypoints.remove(wp)
            await db.delete(wp)
        # Re-index remaining waypoints
        for i, wp in enumerate(sorted(route.waypoints, key=lambda w: w.order_index)):
            wp.order_index = i

    if body.waypoint_order:
        xid_to_wp = {w.poi_xid: w for w in route.waypoints}
        for idx, xid in enumerate(body.waypoint_order):
            if xid in xid_to_wp:
                xid_to_wp[xid].order_index = idx

    await db.commit()
    return await _get_user_route(route_id, user, db)


@router.delete("/{route_id}", status_code=204)
async def delete_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)
    await db.delete(route)
    await db.commit()


@router.post("/{route_id}/start", response_model=RouteOut)
async def start_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)
    if route.status != RouteStatus.draft:
        raise HTTPException(status_code=400, detail="Route is not in draft status")
    route.status = RouteStatus.active
    route.started_at = datetime.now(timezone.utc)
    await db.commit()
    return await _get_user_route(route_id, user, db)


@router.post("/{route_id}/end", response_model=RouteOut)
async def end_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)
    if route.status != RouteStatus.active:
        raise HTTPException(status_code=400, detail="Route is not active")

    all_visited = all(w.is_visited for w in route.waypoints)
    route.status = RouteStatus.completed if all_visited else RouteStatus.abandoned
    route.ended_at = datetime.now(timezone.utc)
    await db.commit()
    return await _get_user_route(route_id, user, db)


@router.post("/{route_id}/waypoints/{waypoint_id}/visit", response_model=RouteOut)
async def visit_waypoint(
    route_id: uuid.UUID,
    waypoint_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)
    if route.status != RouteStatus.active:
        raise HTTPException(status_code=400, detail="Route is not active")

    wp = next((w for w in route.waypoints if w.id == waypoint_id), None)
    if wp is None:
        raise HTTPException(status_code=404, detail="Waypoint not found")

    wp.is_visited = True
    wp.visited_at = datetime.now(timezone.utc)

    await pref_svc.update_on_visit(db, user.id, wp.poi, route.id)

    return await _get_user_route(route_id, user, db)
