from __future__ import annotations

import math
import uuid
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

_MIN_DIST_M = 400  # minimum spacing between selected POIs


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


def _decluster(candidates: list[OTMPlace], num_pois: int) -> list[OTMPlace]:
    accepted: list[OTMPlace] = []
    for candidate in candidates:
        if len(accepted) >= num_pois * 2:
            break
        too_close = any(
            haversine(candidate.lat, candidate.lon, a.lat, a.lon) < _MIN_DIST_M
            for a in accepted
        )
        if not too_close:
            accepted.append(candidate)
    return accepted[:num_pois]


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
    radius_m = int(min(distance_m / 2.5, 3000))
    # Dense urban areas have hundreds of POIs within a few hundred metres.
    # A small limit returns only the nearest cluster, leaving nothing to
    # decluster across the full radius. Cap at the OTM API maximum (500).
    fetch_limit = min(max(num_pois * 20, 200), 500)

    otm = OpenTripMapClient(http_client)
    candidates = await otm.fetch_radius(
        lat=start_lat, lon=start_lon, radius_m=radius_m, limit=fetch_limit
    )

    if not candidates:
        raise ValueError("No points of interest found in this area. Try a larger distance.")

    prefs = await get_preference_map(db, user.id)
    candidates.sort(key=lambda p: _preference_score(p, prefs), reverse=True)

    selected = _decluster(candidates, num_pois)
    if len(selected) < 2:
        raise ValueError("Not enough spread-out POIs found. Try a larger distance or area.")

    await _upsert_pois(db, selected)
    await db.commit()

    osrm = OSRMClient(http_client)
    # Start anchor + POIs; OSRM roundtrip=True handles the return leg automatically
    waypoints: list[tuple[float, float]] = [(start_lat, start_lon)]
    waypoints += [(p.lat, p.lon) for p in selected]

    trip = await osrm.get_trip(waypoints, roundtrip=is_circular)

    ordered_pois = [selected[i - 1] for i in trip.ordered_indices]

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
    )
    db.add(route)
    await db.flush()  # get route.id before adding waypoints

    # leg_durations[0] = start→poi[0], [1] = poi[0]→poi[1], ...
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
