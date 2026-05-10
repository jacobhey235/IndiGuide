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

_MIN_DIST_M = 400   # minimum spacing between selected POIs
_ROAD_FACTOR = 1.4  # OSRM walking distance ≈ straight-line × this in urban areas


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _preference_score(poi: OTMPlace, prefs: dict[str, float]) -> float:
    kinds = [k.strip() for k in poi.kinds.split(",") if k.strip()]
    if kinds:
        avg_pref = sum(prefs.get(k, 0.5) for k in kinds) / len(kinds)
    else:
        avg_pref = 0.5
    normalized_rate = min(poi.rate / 3.0, 1.0)
    return normalized_rate * 0.6 + avg_pref * 0.4


def _decluster(candidates: list[OTMPlace], pool_size: int) -> list[OTMPlace]:
    """Greedy decluster: keep up to pool_size candidates spaced ≥ _MIN_DIST_M apart."""
    accepted: list[OTMPlace] = []
    for candidate in candidates:
        if len(accepted) >= pool_size:
            break
        if not any(haversine(candidate.lat, candidate.lon, a.lat, a.lon) < _MIN_DIST_M for a in accepted):
            accepted.append(candidate)
    return accepted


def _haversine_chain(start_lat: float, start_lon: float, pois: list[OTMPlace]) -> float:
    """Sum of straight-line leg distances for start → pois in given order."""
    pts = [(start_lat, start_lon)] + [(p.lat, p.lon) for p in pois]
    return sum(haversine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1))


def _select_pois_for_distance(
    start_lat: float,
    start_lon: float,
    scored_pool: list[OTMPlace],  # preference-sorted (best first), already declustered
    num_pois: int,
    target_m: float,
) -> list[OTMPlace]:
    """
    Binary-search on d_max (max allowed distance from start) to find the num_pois
    whose estimated walking distance is closest to target_m.

    Within each d_max window we prefer higher-scored POIs (scored_pool is
    preference-sorted), then sort the selection nearest-to-farthest for the walk.
    """
    if len(scored_pool) <= num_pois:
        return sorted(scored_pool, key=lambda p: haversine(start_lat, start_lon, p.lat, p.lon))

    dist_from_start = {p.xid: haversine(start_lat, start_lon, p.lat, p.lon) for p in scored_pool}
    by_dist = sorted(scored_pool, key=lambda p: dist_from_start[p.xid])

    # Binary search bounds: lo = minimum d_max that still yields num_pois candidates
    lo = dist_from_start[by_dist[num_pois - 1].xid]
    hi = dist_from_start[by_dist[-1].xid]

    best: list[OTMPlace] = []
    best_err = float("inf")

    for _ in range(20):
        d_max = (lo + hi) / 2
        # Take top num_pois by preference from those within d_max
        within = [p for p in scored_pool if dist_from_start[p.xid] <= d_max]
        if len(within) < num_pois:
            lo = d_max
            continue
        selection = sorted(within[:num_pois], key=lambda p: dist_from_start[p.xid])
        est = _haversine_chain(start_lat, start_lon, selection) * _ROAD_FACTOR
        err = abs(est - target_m)
        if err < best_err:
            best_err = err
            best = selection
        if est < target_m:
            lo = d_max
        else:
            hi = d_max

    return best if best else sorted(scored_pool[:num_pois], key=lambda p: dist_from_start[p.xid])


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
    is_circular: bool,
    name: str | None,
) -> Route:
    # Search radius = straight-line equivalent of the target walking distance.
    # _ROAD_FACTOR accounts for road detours (walking distance ≈ straight-line × 1.4).
    # Cap at 5 km — searching further returns unrelated places in most cities.
    radius_m = min(int(distance_m / _ROAD_FACTOR), 5000)
    fetch_limit = min(max(num_pois * 20, 200), 500)

    otm = OpenTripMapClient(http_client)
    candidates = await otm.fetch_radius(
        lat=start_lat, lon=start_lon, radius_m=radius_m, limit=fetch_limit
    )

    if not candidates:
        raise ValueError("No points of interest found in this area. Try a larger distance.")

    prefs = await get_preference_map(db, user.id)
    candidates.sort(key=lambda p: _preference_score(p, prefs), reverse=True)

    # Build a pool 4× larger than needed so the distance binary-search has
    # well-spaced candidates at many distances to choose from.
    pool = _decluster(candidates, num_pois * 4)
    if len(pool) < 2:
        raise ValueError("Not enough spread-out POIs found. Try a larger distance or area.")

    osrm = OSRMClient(http_client)
    if is_circular:
        selected = pool[:num_pois]
        waypoints: list[tuple[float, float]] = [(start_lat, start_lon)] + [
            (p.lat, p.lon) for p in selected
        ]
        trip = await osrm.get_trip(waypoints)
        ordered_pois = [selected[i - 1] for i in trip.ordered_indices]
    else:
        # Pick the num_pois whose estimated route length best matches distance_m,
        # then get the real walking geometry from OSRM in that fixed order.
        ordered_pois = _select_pois_for_distance(start_lat, start_lon, pool, num_pois, distance_m)
        waypoints = [(start_lat, start_lon)] + [(p.lat, p.lon) for p in ordered_pois]
        trip = await osrm.get_route(waypoints)

    await _upsert_pois(db, ordered_pois)
    await db.commit()

    route_name = name or f"Route on {datetime.now(timezone.utc).strftime('%b %d')}"
    route = Route(
        user_id=user.id,
        name=route_name,
        status=RouteStatus.draft,
        is_circular=is_circular,
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
