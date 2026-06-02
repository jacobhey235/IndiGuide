"""Unit tests for the endpoint-corridor route-building algorithm (pure functions)."""

import math

from app.services.opentripmap import OTMPlace
from app.services.route_generator import (
    _WALKING_FACTOR,
    _build_best_route_v2,
    _build_corridor_route,
    _fallback_even_sample,
    _linearity,
    _select_endpoints,
    _to_local_xy,
)

START_LAT, START_LON = 55.75, 37.62
_M_PER_DEG = 6_371_000 * math.pi / 180  # metres per degree of latitude (~111195)


def poi(xid: str, north_m: float, east_m: float = 0.0, kinds: str = "museums", rate: float = 2.0):
    """Build a POI placed north_m metres north and east_m metres east of the start."""
    lat = START_LAT + north_m / _M_PER_DEG
    lon = START_LON + east_m / (_M_PER_DEG * math.cos(math.radians(START_LAT)))
    return OTMPlace(xid=xid, name=xid, lon=lon, lat=lat, kinds=kinds, rate=rate)


# ── _to_local_xy ──────────────────────────────────────────────────────────────

def test_to_local_xy_orientation():
    x, y = _to_local_xy(START_LAT + 0.001, START_LON, START_LAT, START_LON)
    assert abs(x) < 1.0 and y > 0           # due north → +y, ~0 x

    x, y = _to_local_xy(START_LAT, START_LON + 0.001, START_LAT, START_LON)
    assert x > 0 and abs(y) < 1.0           # due east → +x, ~0 y


# ── _select_endpoints ─────────────────────────────────────────────────────────

def test_select_endpoints_centered_on_r_target():
    pois = [poi("near", 300), poi("mid", 1500), poi("far", 3000)]
    r_target = 3900 / _WALKING_FACTOR  # ≈ 3000 → ring [2000, 4000]
    ends = {p.xid for p in _select_endpoints(pois, START_LAT, START_LON, r_target, {"museums"}, {})}
    assert "far" in ends
    assert "near" not in ends
    assert "mid" not in ends


def test_select_endpoints_relaxation_widens_until_found():
    pois = [poi("a", 500), poi("b", 700)]
    # Nothing sits near 3000; relaxation must widen the ring and still return candidates.
    ends = _select_endpoints(pois, START_LAT, START_LON, 3000, set(), {})
    assert ends


def test_select_endpoints_empty_pool():
    assert _select_endpoints([], START_LAT, START_LON, 2000, set(), {}) == []


# ── _build_corridor_route ─────────────────────────────────────────────────────

def test_build_corridor_route_orders_by_progress_with_end_last():
    end = poi("E", 3000)
    pool = [poi("p2", 2000), poi("p1", 1000), end, poi("noise", 500, east_m=5000)]
    route = _build_corridor_route(pool, START_LAT, START_LON, end, 3, {"museums"}, {})
    assert [p.xid for p in route] == ["p1", "p2", "E"]  # off-axis "noise" excluded


def test_build_corridor_route_exact_count_two():
    end = poi("E", 1335)
    pool = [poi("p1", 445), poi("p2", 890), end]
    route = _build_corridor_route(pool, START_LAT, START_LON, end, 2, {"museums"}, {})
    assert len(route) == 2
    assert route[-1].xid == "E"


# ── _build_best_route_v2 ──────────────────────────────────────────────────────

def test_build_best_route_v2_picks_linear_route_of_exact_count():
    end = poi("E", 2300)
    pool = [poi("p1", 800), poi("p2", 1500), end, poi("off", 1200, east_m=3000)]
    route = _build_best_route_v2(pool, START_LAT, START_LON, 3, {"museums"}, {}, 3000)
    assert len(route) == 3
    assert route[-1].xid == "E"
    assert "off" not in {p.xid for p in route}
    assert _linearity(START_LAT, START_LON, [(p.lat, p.lon) for p in route]) > 0.95


def test_build_best_route_v2_returns_exact_count_when_dense_line():
    pool = [poi(f"p{i}", 600 * (i + 1)) for i in range(4)]
    target = 600 * 4 * _WALKING_FACTOR  # r_target ≈ 2400 → farthest in ring
    route = _build_best_route_v2(pool, START_LAT, START_LON, 4, set(), {}, target)
    assert len(route) == 4
    assert len({p.xid for p in route}) == 4


def test_build_best_route_v2_empty_when_no_pois():
    assert _build_best_route_v2([], START_LAT, START_LON, 3, set(), {}, 2000) == []


# ── _fallback_even_sample (count guarantee) ───────────────────────────────────

def test_fallback_even_sample_guarantees_count():
    pool = [poi(f"p{i}", 400 * (i + 1)) for i in range(5)]
    sample = _fallback_even_sample(pool, START_LAT, START_LON, [pool[-1]], 3)
    assert len(sample) == 3
    assert len({p.xid for p in sample}) == 3


def test_fallback_even_sample_too_few_points():
    pool = [poi("a", 400), poi("b", 800)]
    assert _fallback_even_sample(pool, START_LAT, START_LON, [pool[-1]], 3) == []
