from __future__ import annotations

import math
from datetime import datetime, timezone

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.poi import POI
from app.models.route import Route, RouteStatus, RouteWaypoint
from app.models.user import User
from app.services.opentripmap import OTMPlace, OpenTripMapClient
from app.services.osrm import OSRMClient
from app.services.preferences import get_preference_map
from app.services.route_categories import expand as expand_categories

_MIN_DIST_M = 400   # minimum spacing between selected POIs
_ROAD_FACTOR = 1.4  # walking distance ≈ straight-line × this in cities
_MIN_SCORE = 0.15   # drop very weak candidates


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _score(poi: OTMPlace, selected_kinds: set[str], user_prefs: dict[str, float]) -> float:
    kinds = [k.strip() for k in poi.kinds.split(",") if k.strip()]
    explicit = 1.0 if any(k in selected_kinds for k in kinds) else 0.0
    rating = min(poi.rate / 3.0, 1.0)
    implicit = sum(user_prefs.get(k, 0.5) for k in kinds) / len(kinds) if kinds else 0.5
    return 0.5 * explicit + 0.3 * rating + 0.2 * implicit


def _decluster(candidates: list[tuple[OTMPlace, float]]) -> list[tuple[OTMPlace, float]]:
    """Greedy decluster by descending score: keep POIs spaced ≥ _MIN_DIST_M apart."""
    by_score = sorted(candidates, key=lambda x: x[1], reverse=True)
    kept: list[tuple[OTMPlace, float]] = []
    for poi, sc in by_score:
        if not any(haversine(poi.lat, poi.lon, k.lat, k.lon) < _MIN_DIST_M for k, _ in kept):
            kept.append((poi, sc))
    return kept


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing in degrees [0, 360) from point 1 to point 2."""
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    d_lon = math.radians(lon2 - lon1)
    x = math.sin(d_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _corridor_filter(
    start_lat: float, start_lon: float, pool: list[tuple[OTMPlace, float]]
) -> list[tuple[OTMPlace, float]]:
    """
    Keep POIs within a narrow corridor from the start.

    The spine direction is seeded by the weighted circular mean bearing of all
    candidates, then adapts gradually as POIs are accepted nearest-first.
    That slow drift is what lets the corridor curve slightly over distance.
    """
    if len(pool) <= 1:
        return pool

    tagged = [
        (poi, sc, haversine(start_lat, start_lon, poi.lat, poi.lon),
         _bearing(start_lat, start_lon, poi.lat, poi.lon))
        for poi, sc in pool
    ]
    tagged.sort(key=lambda t: t[2])  # nearest-first

    # Seed: score-weighted circular mean bearing of all candidates.
    sin_sum = sum(sc * math.sin(math.radians(bear)) for _, sc, _, bear in tagged)
    cos_sum = sum(sc * math.cos(math.radians(bear)) for _, sc, _, bear in tagged)
    corridor_dir = (math.degrees(math.atan2(sin_sum, cos_sum)) + 360) % 360

    HALF_ANGLE = 40.0  # degrees either side of the spine
    ADAPT_RATE = 0.25  # how much accepted POIs nudge the spine direction

    kept: list[tuple[OTMPlace, float]] = []
    for poi, sc, _dist, bear in tagged:
        diff = (bear - corridor_dir + 180) % 360 - 180
        if abs(diff) <= HALF_ANGLE:
            kept.append((poi, sc))
            corridor_dir = (corridor_dir + ADAPT_RATE * diff + 360) % 360

    # Fallback: widen to a hemisphere if the corridor captured too few POIs.
    if len(kept) < 2:
        tagged_hem = [(poi, sc, bear) for poi, sc, _dist, bear in tagged]
        tagged_hem.sort(key=lambda t: t[2])
        bearings = [t[2] for t in tagged_hem]
        scores = [t[1] for t in tagged_hem]
        n = len(tagged_hem)
        bearings2 = bearings + [b + 360 for b in bearings]
        scores2 = scores + scores
        best_score, best_start, best_end, j, window_score = -1.0, 0, 0, 0, 0.0
        for i in range(n):
            while j < len(bearings2) and bearings2[j] < bearings2[i] + 180:
                window_score += scores2[j]
                j += 1
            if window_score > best_score:
                best_score, best_start, best_end = window_score, i, j
            window_score -= scores2[i]
        chosen = {idx % n for idx in range(best_start, best_end)}
        kept = [(tagged_hem[idx][0], tagged_hem[idx][1]) for idx in range(n) if idx in chosen]

    return kept if kept else pool


async def _upsert_pois(db: AsyncSession, pois: list[OTMPlace]) -> None:
    now = datetime.now(timezone.utc)
    for poi in pois:
        stmt = (
            pg_insert(POI)
            .values(
                xid=poi.xid,
                name=poi.name,
                lon=poi.lon,
                lat=poi.lat,
                kinds=poi.kinds,
                rate=poi.rate,
                last_fetched_at=now,
            )
            .on_conflict_do_update(
                index_elements=["xid"],
                set_={
                    "name": poi.name,
                    "kinds": poi.kinds,
                    "rate": poi.rate,
                    "last_fetched_at": now,
                },
            )
        )
        await db.execute(stmt)


async def generate_route(
    db: AsyncSession,
    http_client: httpx.AsyncClient,
    user: User,
    start_lat: float,
    start_lon: float,
    distance_m: float,
    num_pois: int,
    selected_categories: list[str],
    name: str | None,
) -> Route:
    otm_kinds = expand_categories(selected_categories)
    if not otm_kinds:
        raise ValueError("Не выбрано ни одной допустимой категории.")
    selected_kinds = set(otm_kinds)

    radius_m = min(int(distance_m / _ROAD_FACTOR), 5000)
    fetch_limit = min(max(num_pois * 30, 200), 500)

    otm = OpenTripMapClient(http_client)
    candidates = await otm.fetch_radius(
        lat=start_lat, lon=start_lon, radius_m=radius_m, limit=fetch_limit, kinds=otm_kinds
    )
    # Fallback: too few matches — broaden to all interesting_places.
    if len(candidates) < num_pois * 3:
        broader = await otm.fetch_radius(
            lat=start_lat, lon=start_lon, radius_m=radius_m, limit=fetch_limit, kinds=None
        )
        seen = {c.xid for c in candidates}
        candidates.extend(c for c in broader if c.xid not in seen)

    if not candidates:
        raise ValueError("В этом районе не найдено достопримечательностей. Попробуйте увеличить расстояние.")

    user_prefs = await get_preference_map(db, user.id)
    scored = [(p, _score(p, selected_kinds, user_prefs)) for p in candidates]
    scored = [(p, s) for p, s in scored if s >= _MIN_SCORE]

    pool = _decluster(scored)
    pool = _corridor_filter(start_lat, start_lon, pool)
    if len(pool) < 2:
        raise ValueError("Недостаточно объектов в данном районе. Попробуйте увеличить расстояние или изменить категории.")

    top = sorted(
        (p for p, _ in pool[:num_pois]),
        key=lambda p: haversine(start_lat, start_lon, p.lat, p.lon),
    )
    waypoints = [(start_lat, start_lon)] + [(p.lat, p.lon) for p in top]
    osrm = OSRMClient(http_client)
    try:
        trip = await osrm.get_pairwise_routes(waypoints)
    except httpx.HTTPStatusError as e:
        raise httpx.HTTPStatusError(
            f"Routing service error: {e.response.status_code}", request=e.request, response=e.response
        )

    ordered_pois = top

    await _upsert_pois(db, ordered_pois)
    await db.commit()

    route_name = name or f"Маршрут от {datetime.now(timezone.utc).strftime('%d.%m')}"
    route = Route(
        user_id=user.id,
        name=route_name,
        status=RouteStatus.draft,
        start_lon=start_lon,
        start_lat=start_lat,
        total_distance_m=trip.distance_m,
        osrm_geometry=trip.geometry,
        leg_geometries=trip.leg_geometries,
    )
    db.add(route)
    await db.flush()

    for idx, poi in enumerate(ordered_pois):
        leg_dur = trip.leg_durations[idx] if idx < len(trip.leg_durations) else None
        db.add(
            RouteWaypoint(
                route_id=route.id,
                poi_xid=poi.xid,
                order_index=idx,
                leg_duration_s=leg_dur,
            )
        )

    await db.commit()
    await db.refresh(route)
    return route
