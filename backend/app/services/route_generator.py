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
from app.services.route_categories import auto_select as auto_select_categories
from app.services.route_categories import expand as expand_categories

_ROAD_FACTOR = 1.4      # walking distance ≈ straight-line × this in cities
_MIN_SCORE = 0.15       # drop very weak candidates
_STEP_SEARCH_FACTOR = 1.5   # initial search window = step_radius × this (widened on fallback)
_MAX_TURN_DEG = 120.0   # max turning angle at each waypoint; prevents backtracking/segment overlap
_OVERLAP_THRESHOLD_M = 25.0  # paths within this distance share the same road corridor
_MAX_OVERLAP_RATIO = 0.10    # max fraction of a new segment allowed to overlap existing ones
_OVERLAP_SAMPLE_M = 40.0     # sampling step for overlap detection


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    d_lon = math.radians(lon2 - lon1)
    x = math.sin(d_lon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(d_lon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _pt_to_seg_dist_m(
    plat: float, plon: float,
    alat: float, alon: float,
    blat: float, blon: float,
) -> float:
    """Approximate distance in metres from point P to segment AB (flat-earth)."""
    cos_lat = math.cos(math.radians((alat + blat + plat) / 3))
    M = 111_000.0
    px, py = plon * cos_lat * M, plat * M
    ax, ay = alon * cos_lat * M, alat * M
    bx, by = blon * cos_lat * M, blat * M
    dx, dy = bx - ax, by - ay
    seg_sq = dx * dx + dy * dy
    if seg_sq < 1e-6:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_sq))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _overlap_ok(
    from_lat: float, from_lon: float,
    to_lat: float, to_lon: float,
    route_points: list[tuple[float, float]],
) -> bool:
    """True if the proposed segment does not significantly overlap existing route segments.

    Samples points along the new segment (skipping the shared junction at t=0)
    and checks each against every already-walked segment. Returns False when
    more than _MAX_OVERLAP_RATIO of the new segment lies within
    _OVERLAP_THRESHOLD_M of a previously walked path.
    """
    if len(route_points) < 2:
        return True
    seg_dist = haversine(from_lat, from_lon, to_lat, to_lon)
    if seg_dist < _OVERLAP_SAMPLE_M:
        return True
    n = max(3, int(seg_dist / _OVERLAP_SAMPLE_M))
    segs = list(zip(route_points[:-1], route_points[1:]))
    close = 0
    for i in range(1, n):  # start at 1 to skip the shared junction point
        t = i / (n - 1)
        slat = from_lat + t * (to_lat - from_lat)
        slon = from_lon + t * (to_lon - from_lon)
        for (alat, alon), (blat, blon) in segs:
            if _pt_to_seg_dist_m(slat, slon, alat, alon, blat, blon) <= _OVERLAP_THRESHOLD_M:
                close += 1
                break
    return (close / (n - 1)) <= _MAX_OVERLAP_RATIO


def _score(poi: OTMPlace, selected_kinds: set[str], user_prefs: dict[str, float]) -> float:
    kinds = [k.strip() for k in poi.kinds.split(",") if k.strip()]
    explicit = 1.0 if any(k in selected_kinds for k in kinds) else 0.0
    rating = min(poi.rate / 3.0, 1.0)
    implicit = sum(user_prefs.get(k, 0.5) for k in kinds) / len(kinds) if kinds else 0.5
    return 0.5 * explicit + 0.3 * rating + 0.2 * implicit


def _select_by_steps(
    scored: list[tuple[OTMPlace, float]],
    start_lat: float,
    start_lon: float,
    num_pois: int,
    step_radius: float,
) -> list[OTMPlace]:
    """
    Iterative greedy selection based on desired step distance between POIs.

    From the current position, picks the best-scored POI within
    step_radius * _STEP_SEARCH_FACTOR subject to:
      - min_dist: POIs must be spaced ≥ step_radius*0.5 (floor 150 m) apart
      - turn angle: turning angle at each waypoint must be ≤ _MAX_TURN_DEG,
        which prevents backtracking
      - overlap: new straight-line segment must not heavily coincide with
        previously walked segments (prevents re-using the same road corridors)

    Falls back through four progressively relaxed phases to guarantee num_pois:
      1. radius + turn + min_dist + overlap
      2. no radius  + turn + min_dist + overlap
      3. no radius  + no turn + min_dist  (overlap dropped with turn)
      4. no constraints at all
    """
    min_dist = max(step_radius * 0.5, 150.0)
    current_lat, current_lon = start_lat, start_lon
    prev_lat, prev_lon = start_lat, start_lon  # position before current (for turn calc)
    has_direction = False  # no incoming bearing on the first step
    selected: list[OTMPlace] = []
    remaining = list(scored)
    route_points: list[tuple[float, float]] = [(start_lat, start_lon)]

    for _ in range(num_pois):
        if not remaining:
            break

        def _turn_ok(plat: float, plon: float) -> bool:
            if not has_direction:
                return True
            incoming = _bearing(prev_lat, prev_lon, current_lat, current_lon)
            outgoing = _bearing(current_lat, current_lon, plat, plon)
            turn = abs((outgoing - incoming + 180) % 360 - 180)
            return turn <= _MAX_TURN_DEG

        def _dist_ok(poi: OTMPlace) -> bool:
            return all(haversine(poi.lat, poi.lon, s.lat, s.lon) >= min_dist for s in selected)

        def _no_overlap(plat: float, plon: float) -> bool:
            return _overlap_ok(current_lat, current_lon, plat, plon, route_points)

        best: tuple[OTMPlace, float] | None = None

        # Phase 1: radius + turn + min_dist + overlap
        for mult in (1.0, 1.8, 3.5):
            search_r = step_radius * _STEP_SEARCH_FACTOR * mult
            candidates = [
                (poi, sc) for poi, sc in remaining
                if (haversine(current_lat, current_lon, poi.lat, poi.lon) <= search_r
                    and _dist_ok(poi) and _turn_ok(poi.lat, poi.lon)
                    and _no_overlap(poi.lat, poi.lon))
            ]
            if candidates:
                best = max(candidates, key=lambda x: x[1])
                break

        # Phase 2: drop radius, keep turn + min_dist + overlap
        if best is None:
            candidates = [
                (poi, sc) for poi, sc in remaining
                if _dist_ok(poi) and _turn_ok(poi.lat, poi.lon) and _no_overlap(poi.lat, poi.lon)
            ]
            if candidates:
                best = max(candidates, key=lambda x: x[1])

        # Phase 3: drop turn + overlap constraints, keep min_dist
        if best is None:
            candidates = [
                (poi, sc) for poi, sc in remaining if _dist_ok(poi)
            ]
            if candidates:
                best = max(candidates, key=lambda x: x[1])

        # Phase 4: drop all constraints — absolute last resort
        if best is None and remaining:
            best = max(remaining, key=lambda x: x[1])

        if best is None:
            break

        best_poi, _ = best
        prev_lat, prev_lon = current_lat, current_lon
        current_lat, current_lon = best_poi.lat, best_poi.lon
        has_direction = True
        selected.append(best_poi)
        route_points.append((best_poi.lat, best_poi.lon))
        remaining = [(p, sc) for p, sc in remaining if p.xid != best_poi.xid]

    return selected


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
    selected_categories: list[str] | None,
    name: str | None,
) -> Route:
    user_prefs = await get_preference_map(db, user.id)

    if not selected_categories:
        selected_categories = auto_select_categories(user_prefs)

    otm_kinds = expand_categories(selected_categories)
    if not otm_kinds:
        raise ValueError("Не выбрано ни одной допустимой категории.")
    selected_kinds = set(otm_kinds)

    # step_radius: expected straight-line distance between consecutive POIs
    step_distance = distance_m / num_pois
    step_radius = step_distance / _ROAD_FACTOR

    # Fetch all candidates covering the full route area from the start point
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

    scored = [(p, _score(p, selected_kinds, user_prefs)) for p in candidates]
    scored = [(p, s) for p, s in scored if s >= _MIN_SCORE]

    ordered_pois = _select_by_steps(scored, start_lat, start_lon, num_pois, step_radius)
    if len(ordered_pois) < 2:
        raise ValueError("Недостаточно объектов в данном районе. Попробуйте увеличить расстояние или изменить категории.")

    waypoints = [(start_lat, start_lon)] + [(p.lat, p.lon) for p in ordered_pois]
    osrm = OSRMClient(http_client)
    try:
        trip = await osrm.get_pairwise_routes(waypoints)
    except httpx.HTTPStatusError as e:
        raise httpx.HTTPStatusError(
            f"Routing service error: {e.response.status_code}", request=e.request, response=e.response
        )

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
