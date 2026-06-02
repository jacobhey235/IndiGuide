from __future__ import annotations

import asyncio
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
from app.services.preferences import get_disliked_poi_xids, get_preference_map
from app.services.route_categories import CATEGORIES
from app.services.route_categories import expand as expand_categories

_OTM_LIMIT = 500              # OpenTripMap API hard limit
_WALKING_FACTOR = 1.3         # real walking distance ≈ 1.3× straight-line haversine
_ENDPOINT_RING_INIT_FRAC = 0.10   # initial half-width of endpoint ring as fraction of target distance
_ENDPOINT_RING_STEP_FRAC = 0.05   # expansion step when ring is empty (→ 15%, 20%, …)
_CORRIDOR_HALF_M = 400        # base perpendicular half-width of the start→end corridor (m)
_MAX_ENDPOINTS = 60           # cap on endpoint candidates evaluated
_DISTANCE_TOLERANCE_FRAC = 0.2  # accept routes whose estimated length is within ±20% of target


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
    return 0.7 * _linearity(start_lat, start_lon, pts) + 0.3 * _uniformity(start_lat, start_lon, pts)


def _assign_sectors(
    pois: list[OTMPlace], start_lat: float, start_lon: float
) -> dict[int, list[OTMPlace]]:
    sectors: dict[int, list[OTMPlace]] = {s: [] for s in range(6)}
    for p in pois:
        bearing = _calculate_bearing(start_lat, start_lon, p.lat, p.lon)
        sectors[int(bearing / 60) % 6].append(p)
    return sectors


def _to_local_xy(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Equirectangular projection to local metres (x=east, y=north) relative to (lat0, lon0).
    Accurate at city scale (a few km)."""
    R = 6_371_000
    x = math.radians(lon - lon0) * math.cos(math.radians(lat0)) * R
    y = math.radians(lat - lat0) * R
    return x, y


def _select_endpoints(
    pois: list[OTMPlace],
    start_lat: float,
    start_lon: float,
    r_target: float,
    selected_kinds: set[str],
    user_prefs: dict[str, float],
) -> list[OTMPlace]:
    """Endpoint candidates: POIs whose straight-line distance from start lies in a ring
    centred on r_target. The endpoint fixes both the direction and the length of the route.
    The ring is widened (relaxation) until at least one candidate appears."""
    with_dist = [(p, haversine(start_lat, start_lon, p.lat, p.lon)) for p in pois]
    if not with_dist:
        return []
    max_dist = max(d for _, d in with_dist)

    target_m = r_target * _WALKING_FACTOR  # user-specified walking distance
    h_step = _ENDPOINT_RING_INIT_FRAC * target_m
    h = min(h_step, 0.6 * r_target)
    ring: list[OTMPlace] = []
    while not ring:
        lo, hi = r_target - h, r_target + h
        ring = [p for p, d in with_dist if lo <= d <= hi]
        if ring or h >= r_target + max_dist:  # found, or ring already spans every POI
            break
        h += _ENDPOINT_RING_STEP_FRAC * target_m  # expand: 10% → 15% → 20% …

    ring.sort(key=lambda p: _poi_score(p, selected_kinds, user_prefs), reverse=True)
    return ring[:_MAX_ENDPOINTS]


def _build_corridor_route(
    pool: list[OTMPlace],
    start_lat: float,
    start_lon: float,
    end: OTMPlace,
    num_pois: int,
    selected_kinds: set[str],
    user_prefs: dict[str, float],
) -> list[OTMPlace]:
    """Lay out exactly num_pois POIs (end being the last) along the start→end axis so the
    path is linear and evenly spaced. Intermediate points are chosen one per equal-length
    slot of the axis, preferring points close to the line with a high POI score. Returns the
    ordered route start→…→end, or [] when num_pois cannot be filled even after relaxing."""
    ex, ey = _to_local_xy(end.lat, end.lon, start_lat, start_lon)
    seg_len2 = ex * ex + ey * ey
    if seg_len2 <= 0:
        return []
    seg_len = math.sqrt(seg_len2)

    # Project every candidate onto the axis: t = progress fraction, perp = offset in metres.
    projected: list[tuple[OTMPlace, float, float]] = []
    for p in pool:
        if p.xid == end.xid:
            continue
        px, py = _to_local_xy(p.lat, p.lon, start_lat, start_lon)
        t = (px * ex + py * ey) / seg_len2
        perp = abs(px * ey - py * ex) / seg_len
        projected.append((p, t, perp))

    n_intermediate = num_pois - 1
    if n_intermediate <= 0:
        return [end]

    selected: list[tuple[OTMPlace, float]] = []
    used: set[int] = set()
    for slot in range(n_intermediate):
        lo = slot / num_pois
        hi = (slot + 1) / num_pois
        corridor_half = _CORRIDOR_HALF_M
        t_pad = 0.0
        window: list[tuple[int, OTMPlace, float, float]] = []
        while not window:
            window = [
                (i, p, t, perp)
                for i, (p, t, perp) in enumerate(projected)
                if i not in used
                and 0.0 <= t <= 1.0
                and (lo - t_pad) <= t <= (hi + t_pad)
                and perp <= corridor_half
            ]
            if window:
                break
            # Relaxation: widen the slot window along the axis and the corridor width.
            t_pad += 0.5 / num_pois
            corridor_half += _CORRIDOR_HALF_M
            if t_pad >= 1.0 and corridor_half >= seg_len:
                break
        if not window:
            continue
        best = max(
            window,
            key=lambda w: _poi_score(w[1], selected_kinds, user_prefs)
            - 0.5 * (w[3] / max(corridor_half, 1.0)),
        )
        selected.append((best[1], best[2]))
        used.add(best[0])

    if len(selected) < n_intermediate:
        return []

    selected.sort(key=lambda x: x[1])
    return [p for p, _ in selected] + [end]


def _fallback_even_sample(
    candidates: list[OTMPlace],
    start_lat: float,
    start_lon: float,
    endpoints: list[OTMPlace],
    num_pois: int,
) -> list[OTMPlace]:
    """Last-resort guarantee of exactly num_pois points: project all candidates onto the
    axis of the endpoint that captures the most of them, then sample num_pois evenly by
    progress. Returns [] only when fewer than num_pois candidates exist in total."""
    if len(candidates) < num_pois:
        return []

    best_proj: list[tuple[OTMPlace, float]] | None = None
    best_count = -1
    for end in endpoints:
        ex, ey = _to_local_xy(end.lat, end.lon, start_lat, start_lon)
        seg_len2 = ex * ex + ey * ey
        if seg_len2 <= 0:
            continue
        proj = [
            (p, (lambda xy: (xy[0] * ex + xy[1] * ey) / seg_len2)(
                _to_local_xy(p.lat, p.lon, start_lat, start_lon)))
            for p in candidates
        ]
        count = sum(1 for _, t in proj if 0.0 <= t <= 1.2)
        if count > best_count:
            best_count = count
            best_proj = proj

    if best_proj is not None:
        ordered = [p for p, _ in sorted(best_proj, key=lambda x: x[1])]
    else:
        ordered = sorted(candidates, key=lambda p: haversine(start_lat, start_lon, p.lat, p.lon))

    step = len(ordered) / num_pois
    return [ordered[min(int(i * step), len(ordered) - 1)] for i in range(num_pois)]


def _build_best_route_v2(
    candidates: list[OTMPlace],
    start_lat: float,
    start_lon: float,
    num_pois: int,
    selected_kinds: set[str],
    user_prefs: dict[str, float],
    target_distance_m: float,
) -> list[OTMPlace]:
    """Pick an endpoint from the outer ring, build a linear corridor route to it, and keep
    the most linear + uniform variant whose estimated length is within ±tolerance of the
    target. Always returns exactly num_pois points unless the area physically holds fewer."""
    r_target = target_distance_m / _WALKING_FACTOR
    endpoints = _select_endpoints(
        candidates, start_lat, start_lon, r_target, selected_kinds, user_prefs
    )
    if not endpoints:
        return []

    tol = _DISTANCE_TOLERANCE_FRAC * target_distance_m
    best_in_range: list[OTMPlace] = []
    best_quality: float = -1.0
    fallback: list[OTMPlace] = []
    fallback_err: float = float("inf")

    for end in endpoints:
        route = _build_corridor_route(
            candidates, start_lat, start_lon, end, num_pois, selected_kinds, user_prefs
        )
        if len(route) != num_pois:
            continue
        pts = [(p.lat, p.lon) for p in route]
        path = [(start_lat, start_lon), *pts]
        estimated_dist = (
            sum(haversine(*path[i], *path[i + 1]) for i in range(len(path) - 1))
            * _WALKING_FACTOR
        )
        quality = 0.5 * _linearity(start_lat, start_lon, pts) + 0.5 * _uniformity(
            start_lat, start_lon, pts
        )
        err = abs(estimated_dist - target_distance_m)
        if err <= tol and quality > best_quality:
            best_quality = quality
            best_in_range = route
        if err < fallback_err:
            fallback_err = err
            fallback = route

    result = best_in_range or fallback
    if len(result) == num_pois:
        return result

    # Count guarantee: no endpoint yielded a full corridor route → even-sample instead.
    return _fallback_even_sample(candidates, start_lat, start_lon, endpoints, num_pois)


async def _fetch_pois_explicit(
    otm: OpenTripMapClient,
    lat: float,
    lon: float,
    radius: int,
    selected_categories: list[str],
) -> list[OTMPlace]:
    """One parallel OTM call per user-facing category; merge and deduplicate.

    Sending all kinds in a single request causes OTM to return the 500 nearest
    POIs across all types, starving the outer ring of candidates.  Per-category
    calls each get their own 500-slot budget and cover the full radius.
    """
    tasks = [
        otm.fetch_radius(lat=lat, lon=lon, radius_m=radius, limit=_OTM_LIMIT, kinds=CATEGORIES[cat])
        for cat in selected_categories if cat in CATEGORIES
    ]
    if not tasks:
        return []
    batches = await asyncio.gather(*tasks)
    seen: dict[str, OTMPlace] = {}
    for batch in batches:
        for p in batch:
            seen.setdefault(p.xid, p)
    return list(seen.values())


async def _fetch_pois_for_preferences(
    otm: OpenTripMapClient,
    lat: float,
    lon: float,
    radius: int,
    user_prefs: dict[str, float],
    num_pois: int,
) -> list[OTMPlace]:
    """Fetch with progressively more categories (top-1/3 → top-2/3 → all) until the
    densest 60° sector has at least num_pois candidates, or we've exhausted all options."""
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
        if tier_idx < len(tiers) - 1:
            # Per-category parallel calls so each type gets its own 500-slot budget
            tasks = [
                otm.fetch_radius(lat=lat, lon=lon, radius_m=radius, limit=_OTM_LIMIT, kinds=CATEGORIES[k])
                for k in tier_keys if k in CATEGORIES
            ]
            batches = await asyncio.gather(*tasks)
            seen: dict[str, OTMPlace] = {}
            for batch in batches:
                for p in batch:
                    seen.setdefault(p.xid, p)
            pois = list(seen.values())
        else:
            # Last tier: no kinds filter — OTM searches all interesting places
            pois = await otm.fetch_radius(lat, lon, radius, limit=_OTM_LIMIT, kinds=None)

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
    include_disliked: bool = False,
) -> Route:
    user_prefs = await get_preference_map(db, user.id)
    disliked_xids = set() if include_disliked else await get_disliked_poi_xids(db, user.id)
    is_explicit = bool(selected_categories)

    otm = OpenTripMapClient(http_client)
    # Search all tourist POIs within (route length + 1 km) of the start point.
    fetch_radius = max(int(distance_m + 1000), 500)

    # 1. Fetch POIs in (distance + 1 km) radius
    if is_explicit:
        otm_kinds = expand_categories(selected_categories)
        if not otm_kinds:
            raise ValueError("Не выбрано ни одной допустимой категории.")
        selected_kinds = set(otm_kinds)
        pois = await _fetch_pois_explicit(
            otm, start_lat, start_lon, fetch_radius, selected_categories,
        )
    else:
        pois = await _fetch_pois_for_preferences(
            otm, start_lat, start_lon, fetch_radius, user_prefs, num_pois
        )
        selected_kinds = set(expand_categories(list(CATEGORIES.keys())))

    if disliked_xids:
        pois = [p for p in pois if p.xid not in disliked_xids]

    if not pois:
        raise ValueError(
            "В этом районе не найдено достопримечательностей. "
            "Попробуйте увеличить расстояние или изменить категории."
        )

    if len(pois) < num_pois:
        raise ValueError(
            "Недостаточно объектов для построения маршрута. "
            "Попробуйте увеличить расстояние или изменить категории."
        )

    # 2. Pick an endpoint from the outer ring (r_target = distance / walking factor) that
    #    sets the route's direction and length, then lay out a linear, evenly spaced
    #    corridor of exactly num_pois points toward it.
    ordered_pois = _build_best_route_v2(
        candidates=pois,
        start_lat=start_lat,
        start_lon=start_lon,
        num_pois=num_pois,
        selected_kinds=selected_kinds,
        user_prefs=user_prefs,
        target_distance_m=distance_m,
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
