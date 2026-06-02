from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.poi import POI
from app.models.route import Route, RouteStatus, RouteWaypoint
from app.models.user import User
from app.schemas.poi import POIBasic
from app.schemas.route import (
    NavigationResponse,
    PublicRouteOut,
    PublicRouteSummary,
    RouteGenerateRequest,
    RouteOut,
    RouteSummary,
    RouteUpdateRequest,
    SuggestWaypointRequest,
    UserRouteSummary,
)
from app.services import preferences as pref_svc
from app.services.opentripmap import OpenTripMapClient
from app.services.osrm import OSRMClient
from app.services.route_categories import CATEGORIES, expand
from app.services.route_generator import _upsert_pois, generate_route, haversine

router = APIRouter()

_ROUTE_OPTIONS = selectinload(Route.waypoints).selectinload(RouteWaypoint.poi)


def _best_insert_idx(
    poi_lat: float,
    poi_lon: float,
    start_lat: float,
    start_lon: float,
    sorted_wps: list[RouteWaypoint],
) -> int:
    """Best-insertion heuristic: 0-based index minimising extra walking distance."""
    points = [(start_lat, start_lon)] + [(w.poi.lat, w.poi.lon) for w in sorted_wps]
    best_idx, best_cost = len(sorted_wps), float("inf")
    for i in range(1, len(points) + 1):
        prev = points[i - 1]
        nxt = points[i] if i < len(points) else None
        cost = (
            haversine(prev[0], prev[1], poi_lat, poi_lon)
            + haversine(poi_lat, poi_lon, nxt[0], nxt[1])
            - haversine(prev[0], prev[1], nxt[0], nxt[1])
            if nxt
            else haversine(prev[0], prev[1], poi_lat, poi_lon)
        )
        if cost < best_cost:
            best_cost, best_idx = cost, i - 1
    return best_idx
_ROUTE_WITH_USER = [
    selectinload(Route.waypoints).selectinload(RouteWaypoint.poi),
    selectinload(Route.user),
]


async def _get_user_route(route_id: uuid.UUID, user: User, db: AsyncSession) -> Route:
    result = await db.execute(
        select(Route).options(_ROUTE_OPTIONS).where(Route.id == route_id)
    )
    route = result.scalar_one_or_none()
    if route is None or route.user_id != user.id:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    return route


def _score_by_prefs(route: Route, pref_map: dict[str, float]) -> float:
    kinds: list[str] = []
    for wp in route.waypoints:
        if wp.poi.kinds:
            kinds.extend(k.strip() for k in wp.poi.kinds.split(",") if k.strip())
    if not kinds:
        return 0.5
    return sum(pref_map.get(k, 0.5) for k in kinds) / len(kinds)


def _score_by_categories(route: Route, selected_kinds: set[str]) -> int:
    count = 0
    for wp in route.waypoints:
        if wp.poi.kinds:
            for k in wp.poi.kinds.split(","):
                if k.strip() in selected_kinds:
                    count += 1
    return count


def _to_user_summary(route: Route) -> UserRouteSummary:
    base = RouteSummary.model_validate(route)
    author = route.original_author_username or route.user.username
    return UserRouteSummary(**base.model_dump(), author_username=author)


def _to_public_summary(route: Route) -> PublicRouteSummary:
    base = RouteSummary.model_validate(route)
    return PublicRouteSummary(
        **{k: v for k, v in base.model_dump().items() if k in PublicRouteSummary.model_fields},
        author_username=route.user.username,
    )


def _to_public_out(route: Route) -> PublicRouteOut:
    base = RouteOut.model_validate(route)
    return PublicRouteOut(
        **{k: v for k, v in base.model_dump().items() if k in PublicRouteOut.model_fields},
        author_username=route.user.username,
    )


# ── Explore endpoints (must come before /{route_id} to avoid path conflict) ──

@router.get("/explore", response_model=list[PublicRouteSummary])
async def list_explore_routes(
    sort: str = Query(default="preferences", pattern="^(preferences|categories)$"),
    categories: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Route)
        .options(*_ROUTE_WITH_USER)
        .where(Route.is_published == True)  # noqa: E712
    )
    routes = list(result.scalars().all())

    if sort == "preferences":
        pref_map = await pref_svc.get_preference_map(db, user.id)
        routes.sort(key=lambda r: _score_by_prefs(r, pref_map), reverse=True)
    else:
        selected_keys = [k.strip() for k in (categories or "").split(",") if k.strip()]
        if not selected_keys:
            selected_keys = list(CATEGORIES.keys())
        selected_kinds = set(expand(selected_keys))
        routes = [r for r in routes if _score_by_categories(r, selected_kinds) > 0]
        routes.sort(key=lambda r: _score_by_categories(r, selected_kinds), reverse=True)

    return [_to_public_summary(r) for r in routes]


@router.get("/explore/{route_id}", response_model=PublicRouteOut)
async def get_explore_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Route)
        .options(*_ROUTE_WITH_USER)
        .where(Route.id == route_id, Route.is_published == True)  # noqa: E712
    )
    route = result.scalar_one_or_none()
    if route is None:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    return _to_public_out(route)


@router.post("/explore/{route_id}/clone", response_model=RouteOut, status_code=201)
async def clone_explore_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Route)
        .options(*_ROUTE_WITH_USER)
        .where(Route.id == route_id, Route.is_published == True)  # noqa: E712
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    clone = Route(
        user_id=user.id,
        name=source.name,
        status=RouteStatus.draft,
        is_saved=False,
        is_published=False,
        start_lon=source.start_lon,
        start_lat=source.start_lat,
        total_distance_m=source.total_distance_m,
        osrm_geometry=source.osrm_geometry,
        leg_geometries=source.leg_geometries,
        original_author_username=source.user.username,
    )
    db.add(clone)
    await db.flush()

    for wp in sorted(source.waypoints, key=lambda w: w.order_index):
        db.add(RouteWaypoint(
            route_id=clone.id,
            poi_xid=wp.poi_xid,
            order_index=wp.order_index,
            is_visited=False,
            visited_at=None,
            leg_duration_s=wp.leg_duration_s,
        ))

    await db.commit()

    result = await db.execute(
        select(Route).options(_ROUTE_OPTIONS).where(Route.id == clone.id)
    )
    return result.scalar_one()


# ── User's own routes ─────────────────────────────────────────────────────────

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
            selected_categories=body.selected_categories,
            name=body.name,
            include_disliked=body.include_disliked,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=503, detail=f"Ошибка внешнего сервиса: {e.response.status_code}")

    result = await db.execute(
        select(Route).options(_ROUTE_OPTIONS).where(Route.id == route.id)
    )
    return result.scalar_one()


@router.get("/", response_model=list[UserRouteSummary])
async def list_routes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Route)
        .options(*_ROUTE_WITH_USER)
        .where(Route.user_id == user.id, Route.is_saved == True)  # noqa: E712
        .order_by(Route.created_at.desc())
    )
    return [_to_user_summary(r) for r in result.scalars().all()]


@router.get("/{route_id}", response_model=RouteOut)
async def get_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_user_route(route_id, user, db)


@router.post("/{route_id}/waypoints/suggest", response_model=POIBasic)
async def suggest_waypoint(
    route_id: uuid.UUID,
    body: SuggestWaypointRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)
    if route.status != RouteStatus.draft:
        raise HTTPException(status_code=400, detail="Добавление точек доступно только для черновика")

    otm = OpenTripMapClient(request.app.state.http_client)
    pois = await otm.fetch_radius(body.tap_lat, body.tap_lon, radius_m=500, limit=20)

    existing_xids = {w.poi_xid for w in route.waypoints}
    candidates = [p for p in pois if p.xid not in existing_xids and p.name and p.lat and p.lon]

    if not candidates:
        raise HTTPException(status_code=404, detail="Рядом не найдено подходящих мест")

    nearest = min(candidates, key=lambda p: haversine(body.tap_lat, body.tap_lon, p.lat, p.lon))
    await _upsert_pois(db, [nearest])
    await db.commit()

    result = await db.execute(select(POI).where(POI.xid == nearest.xid))
    return result.scalar_one()


@router.put("/{route_id}", response_model=RouteOut)
async def update_route(
    route_id: uuid.UUID,
    body: RouteUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)

    if body.name is not None:
        route.name = body.name

    if body.is_saved is not None:
        route.is_saved = body.is_saved

    if body.is_published is not None:
        if body.is_published and not route.is_saved:
            raise HTTPException(status_code=422, detail="Нельзя опубликовать несохранённый маршрут")
        route.is_published = body.is_published

    needs_reroute = False

    if body.remove_poi_xids:
        to_remove = [w for w in route.waypoints if w.poi_xid in body.remove_poi_xids]
        for wp in to_remove:
            if route.status == RouteStatus.draft:
                await pref_svc.update_on_removal(db, user.id, wp.poi, route.id)
            route.waypoints.remove(wp)
            await db.delete(wp)
        if len(route.waypoints) < 2:
            await db.delete(route)
            await db.commit()
            return Response(status_code=204)
        for i, wp in enumerate(sorted(route.waypoints, key=lambda w: w.order_index)):
            wp.order_index = i
        needs_reroute = True

    if body.waypoint_order:
        xid_to_wp = {w.poi_xid: w for w in route.waypoints}
        for idx, xid in enumerate(body.waypoint_order):
            if xid in xid_to_wp:
                xid_to_wp[xid].order_index = idx
        needs_reroute = True

    if body.add_poi_xid:
        if route.status != RouteStatus.draft:
            raise HTTPException(status_code=400, detail="Добавление точек доступно только для черновика")
        poi_result = await db.execute(select(POI).where(POI.xid == body.add_poi_xid))
        new_poi = poi_result.scalar_one_or_none()
        if new_poi is None:
            raise HTTPException(status_code=404, detail="Точка не найдена — сначала вызовите suggest")
        if any(w.poi_xid == body.add_poi_xid for w in route.waypoints):
            raise HTTPException(status_code=409, detail="Точка уже есть в маршруте")
        sorted_wps = sorted(route.waypoints, key=lambda w: w.order_index)
        insert_idx = _best_insert_idx(new_poi.lat, new_poi.lon, route.start_lat, route.start_lon, sorted_wps)
        for wp in sorted_wps[insert_idx:]:
            wp.order_index += 1
        new_wp = RouteWaypoint(
            route_id=route.id,
            poi_xid=new_poi.xid,
            order_index=insert_idx,
            is_visited=False,
        )
        new_wp.poi = new_poi
        db.add(new_wp)
        route.waypoints.append(new_wp)
        await db.flush()
        needs_reroute = True

    if needs_reroute:
        remaining = sorted(route.waypoints, key=lambda w: w.order_index)
        if remaining:
            osrm = OSRMClient(request.app.state.http_client)
            wps = [(route.start_lat, route.start_lon)] + [(w.poi.lat, w.poi.lon) for w in remaining]
            try:
                trip = await osrm.get_route(wps)
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=503, detail=f"Ошибка службы маршрутизации: {e.response.status_code}")
            route.osrm_geometry = trip.geometry
            route.leg_geometries = trip.leg_geometries
            route.total_distance_m = trip.distance_m
            for i, wp in enumerate(remaining):
                wp.leg_duration_s = trip.leg_durations[i] if i < len(trip.leg_durations) else None
        else:
            route.osrm_geometry = None
            route.leg_geometries = None
            route.total_distance_m = 0.0

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


@router.get("/{route_id}/navigate", response_model=NavigationResponse)
async def navigate_to_waypoint(
    route_id: uuid.UUID,
    waypoint_id: int,
    current_lat: float,
    current_lon: float,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the actual walking route from the user's current GPS position to a waypoint."""
    route = await _get_user_route(route_id, user, db)
    wp = next((w for w in route.waypoints if w.id == waypoint_id), None)
    if wp is None:
        raise HTTPException(status_code=404, detail="Точка маршрута не найдена")

    osrm = OSRMClient(request.app.state.http_client)
    try:
        trip = await osrm.get_route([
            (current_lat, current_lon),
            (wp.poi.lat, wp.poi.lon),
        ])
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=503, detail=f"Routing service error: {e.response.status_code}")

    return NavigationResponse(
        geometry=trip.geometry,
        distance_m=trip.distance_m,
        duration_s=trip.duration_s,
    )


@router.post("/{route_id}/start", response_model=RouteOut)
async def start_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)
    if route.status != RouteStatus.draft:
        raise HTTPException(status_code=400, detail="Маршрут не является черновиком")
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
        raise HTTPException(status_code=400, detail="Маршрут не активен")

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
        raise HTTPException(status_code=400, detail="Маршрут не активен")

    wp = next((w for w in route.waypoints if w.id == waypoint_id), None)
    if wp is None:
        raise HTTPException(status_code=404, detail="Точка маршрута не найдена")

    wp.is_visited = True
    wp.visited_at = datetime.now(timezone.utc)

    await pref_svc.update_on_visit(db, user.id, wp.poi, route.id)

    return await _get_user_route(route_id, user, db)


@router.post("/{route_id}/waypoints/{waypoint_id}/like", status_code=204)
async def like_waypoint(
    route_id: uuid.UUID,
    waypoint_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)
    wp = next((w for w in route.waypoints if w.id == waypoint_id), None)
    if wp is None:
        raise HTTPException(status_code=404, detail="Точка маршрута не найдена")
    if not wp.is_visited:
        raise HTTPException(status_code=400, detail="Нельзя оценить непосещённую точку")

    await pref_svc.update_on_like(db, user.id, wp.poi, route.id)


@router.post("/{route_id}/waypoints/{waypoint_id}/dislike", status_code=204)
async def dislike_waypoint(
    route_id: uuid.UUID,
    waypoint_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    route = await _get_user_route(route_id, user, db)
    wp = next((w for w in route.waypoints if w.id == waypoint_id), None)
    if wp is None:
        raise HTTPException(status_code=404, detail="Точка маршрута не найдена")
    if not wp.is_visited:
        raise HTTPException(status_code=400, detail="Нельзя оценить непосещённую точку")

    await pref_svc.update_on_dislike(db, user.id, wp.poi, route.id)
