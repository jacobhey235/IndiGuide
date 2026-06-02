from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from itertools import combinations

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.poi import POI
from app.models.route import Route, RouteStatus, RouteWaypoint
from app.models.user import User
from app.services.opentripmap import OTMPlace, OpenTripMapClient
from app.services.osrm import OSRMClient
from app.services.preferences import get_preference_map
from app.services.route_categories import CATEGORIES
from app.services.route_categories import expand as expand_categories

_MAX_COMBO_POOL = 25       # top-N candidates by quality score fed into combination search
_MAX_COMBINATIONS = 3000   # max route variants to evaluate
_OTM_LIMIT = 500           # OpenTripMap API hard limit


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_lat1, r_lon1 = math.radians(lat1), math.radians(lon1)
    r_lat2, r_lon2 = math.radians(lat2), math.radians(lon2)
    d_lon = r_lon2 - r_lon1
    y = math.sin(d_lon) * math.cos(r_lat2)
    x = math.cos(r_lat1) * math.sin(r_lat2) - math.sin(r_lat1) * math.cos(r_lat2) * math.cos(d_lon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _poi_score(poi: OTMPlace, selected_kinds: set[str], user_prefs: dict[str, float]) -> float:
    kinds = [k.strip() for k in poi.kinds.split(",") if k.strip()]
    explicit = 1.0 if any(k in selected_kinds for k in kinds) else 0.0
    rating = min(poi.rate / 3.0, 1.0)
    implicit = sum(user_prefs.get(k, 0.5) for k in kinds) / len(kinds) if kinds else 0.5
    return 0.5 * explicit + 0.3 * rating + 0.2 * implicit


def _linearity(start_lat: float, start_lon: float, pts: list[tuple[float, float]]) -> float:
    """Net displacement / path length. 1.0 = perfectly straight."""
    if not pts:
        return 0.0
    path = [(start_lat, start_lon), *pts]
    path_len = sum(haversine(*path[i], *path[i + 1]) for i in range(len(path) - 1))
    if path_len <= 0:
        return 0.0
    displacement = haversine(start_lat, start_lon, pts[-1][0], pts[-1][1])
    return displacement / path_len


def _uniformity(start_lat: float, start_lon: float, pts: list[tuple[float, float]]) -> float:
    """1.0 when inter-point gaps are perfectly equal, decreases as variance grows."""
    if len(pts) < 2:
        return 1.0
    path = [(start_lat, start_lon), *pts]
    dists = [haversine(*path[i], *path[i + 1]) for i in range(len(path) - 1)]
    mean_d = sum(dists) / len(dists)
    if mean_d == 0:
        return 0.0
    std_d = math.sqrt(sum((d - mean_d) ** 2 for d in dists) / len(dists))
    # 1 / (1 + CV): CV=0 → 1.0, CV=1 → 0.5, asymptotically → 0
    return 1.0 / (1.0 + std_d / mean_d)


def _route_quality(ordered_pois: list[OTMPlace], start_lat: float, start_lon: float) -> float:
    pts = [(p.lat, p.lon) for p in ordered_pois]
    return 0.5 * _linearity(start_lat, start_lon, pts) + 0.5 * _uniformity(start_lat, start_lon, pts)


def _assign_sectors(
    pois: list[OTMPlace], start_lat: float, start_lon: float
) -> dict[int, list[OTMPlace]]:
    sectors: dict[int, list[OTMPlace]] = {s: [] for s in range(6)}
    for p in pois:
        bearing = _calculate_bearing(start_lat, start_lon, p.lat, p.lon)
        sectors[int(bearing / 60) % 6].append(p)
    return sectors


def _select_candidates(
    pois: list[OTMPlace],
    start_lat: float,
    start_lon: float,
    num_pois: int,
) -> list[OTMPlace]:
    """Return candidates by progressively widening the arc: 60° → 120° → 180°."""
    sectors = _assign_sectors(pois, start_lat, start_lon)
    best_sec = max(range(6), key=lambda s: len(sectors[s]))

    # 60° — best sector alone
    candidates = list(sectors[best_sec])
    if len(candidates) >= num_pois:
        return candidates

    # 120° — add the adjacent sector with more POIs
    left_sec = (best_sec - 1) % 6
    right_sec = (best_sec + 1) % 6
    extra_sec = left_sec if len(sectors[left_sec]) >= len(sectors[right_sec]) else right_sec
    candidates = list(sectors[best_sec]) + list(sectors[extra_sec])
    if len(candidates) >= num_pois:
        return candidates

    # 180° — add the remaining adjacent sector
    other_sec = right_sec if extra_sec == left_sec else left_sec
    return list(sectors[best_sec]) + list(sectors[extra_sec]) + list(sectors[other_sec])


def _build_best_route(
    candidates: list[OTMPlace],
    start_lat: float,
    start_lon: float,
    num_pois: int,
    selected_kinds: set[str],
    user_prefs: dict[str, float],
) -> list[OTMPlace]:
    """Select exactly num_pois POIs from candidates and find the ordering that
    maximises 0.5 * linearity + 0.5 * uniformity across all feasible variants."""
    scored = sorted(candidates, key=lambda p: _poi_score(p, selected_kinds, user_prefs), reverse=True)
    pool = scored[:_MAX_COMBO_POOL]

    if len(pool) < num_pois:
        return []

    best_pois: list[OTMPlace] = []
    best_score = -1.0

    def _try(combo: tuple[OTMPlace, ...] | list[OTMPlace]) -> None:
        nonlocal best_pois, best_score
        ordered = sorted(combo, key=lambda p: haversine(start_lat, start_lon, p.lat, p.lon))
        sc = _route_quality(ordered, start_lat, start_lon)
        if sc > best_score:
            best_score = sc
            best_pois = list(ordered)

    # Always try the "evenly spaced along distance" baseline
    sorted_pool = sorted(pool, key=lambda p: haversine(start_lat, start_lon, p.lat, p.lon))
    if len(sorted_pool) >= num_pois:
        step = len(sorted_pool) / num_pois
        baseline = [sorted_pool[int(i * step)] for i in range(num_pois)]
        _try(baseline)

    total_combos = math.comb(len(pool), num_pois)

    if total_combos <= _MAX_COMBINATIONS:
        for combo in combinations(pool, num_pois):
            _try(combo)
    else:
        seen: set[tuple[int, ...]] = set()
        pool_indices = list(range(len(pool)))
        attempts = 0
        max_attempts = _MAX_COMBINATIONS * 4
        while len(seen) < _MAX_COMBINATIONS and attempts < max_attempts:
            idxs = tuple(sorted(random.sample(pool_indices, num_pois)))
            if idxs not in seen:
                seen.add(idxs)
                _try([pool[i] for i in idxs])
            attempts += 1

    return best_pois


async def _fetch_pois_for_preferences(
    otm: OpenTripMapClient,
    lat: float,
    lon: float,
    radius: int,
    user_prefs: dict[str, float],
    num_pois: int,
) -> list[OTMPlace]:
    """Fetch with progressively more categories (top-1/3 → top-2/3 → all) until the
    best 60° sector has at least num_pois candidates, or we've exhausted all options."""
    cat_scores = sorted(
        (
            (key, sum(user_prefs.get(k, 0.5) for k in kinds) / len(kinds))
            for key, kinds in CATEGORIES.items()
        ),
        key=lambda x: -x[1],
    )
    all_keys = [k for k, _ in cat_scores]
    n = len(all_keys)

    tiers = [
        all_keys[: math.ceil(n / 3)],
        all_keys[: math.ceil(2 * n / 3)],
        all_keys,
    ]

    pois: list[OTMPlace] = []
    for tier_idx, tier_keys in enumerate(tiers):
        # Last tier: no kinds filter so OTM searches all interesting places
        kinds_param = expand_categories(tier_keys) if tier_idx < len(tiers) - 1 else None
        pois = await otm.fetch_radius(lat, lon, radius, limit=_OTM_LIMIT, kinds=kinds_param)

        sectors = _assign_sectors(pois, lat, lon)
        best_sec = max(range(6), key=lambda s: len(sectors[s]))
        if len(sectors[best_sec]) >= num_pois or tier_idx == len(tiers) - 1:
            break

    return pois


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
    is_explicit = bool(selected_categories)

    otm = OpenTripMapClient(http_client)
    fetch_radius = int(distance_m) + 1000

    # 1. Fetch POIs in (distance + 1 km) radius
    if is_explicit:
        otm_kinds = expand_categories(selected_categories)
        if not otm_kinds:
            raise ValueError("Не выбрано ни одной допустимой категории.")
        selected_kinds = set(otm_kinds)
        pois = await otm.fetch_radius(
            lat=start_lat, lon=start_lon,
            radius_m=fetch_radius, limit=_OTM_LIMIT, kinds=otm_kinds,
        )
    else:
        pois = await _fetch_pois_for_preferences(
            otm, start_lat, start_lon, fetch_radius, user_prefs, num_pois
        )
        selected_kinds = set(expand_categories(list(CATEGORIES.keys())))

    if not pois:
        raise ValueError(
            "В этом районе не найдено достопримечательностей. "
            "Попробуйте увеличить расстояние или изменить категории."
        )

    # 2. Select candidates: best 60° sector, expanding to 120° / 180° if needed
    candidates = _select_candidates(pois, start_lat, start_lon, num_pois)

    if len(candidates) < num_pois:
        raise ValueError(
            "Недостаточно объектов для построения маршрута. "
            "Попробуйте увеличить расстояние или изменить категории."
        )

    # 3. Find the most linear and uniformly distributed route of exactly num_pois points
    ordered_pois = _build_best_route(
        candidates=candidates,
        start_lat=start_lat,
        start_lon=start_lon,
        num_pois=num_pois,
        selected_kinds=selected_kinds,
        user_prefs=user_prefs,
    )

    if len(ordered_pois) != num_pois:
        raise ValueError(
            "Недостаточно объектов для построения маршрута. "
            "Попробуйте увеличить расстояние или изменить категории."
        )

    # 4. Build walking route via OSRM
    waypoints = [(start_lat, start_lon)] + [(p.lat, p.lon) for p in ordered_pois]
    osrm = OSRMClient(http_client)
    try:
        trip = await osrm.get_pairwise_routes(waypoints)
    except httpx.HTTPStatusError as e:
        raise httpx.HTTPStatusError(
            f"Routing service error: {e.response.status_code}",
            request=e.request,
            response=e.response,
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
