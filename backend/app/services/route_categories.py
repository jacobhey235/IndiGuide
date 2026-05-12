"""Curated POI categories exposed to users.

Each entry maps a UI-facing key to one or more OpenTripMap `kinds` strings.
The OpenTripMap API accepts comma-separated kinds in its `kinds` query param,
and POI.kinds (returned by the API) is also a comma-separated list, so the
membership test `kind in poi.kinds.split(",")` works for the values below.

Keep this file in sync with `frontend/src/constants/categories.ts`.
"""

from __future__ import annotations

CATEGORIES: dict[str, list[str]] = {
    "historic": ["historic", "historical_places"],
    "architecture": ["architecture", "monuments_and_memorials"],
    "museums": ["museums"],
    "religion": ["religion"],
    "cultural": ["cultural", "theatres_and_entertainments"],
    "natural": ["natural", "gardens_and_parks"],
    "interesting_places": ["interesting_places"],
}


def expand(selected_keys: list[str]) -> list[str]:
    """Flatten user-selected category keys into the underlying OpenTripMap kinds."""
    out: list[str] = []
    for key in selected_keys:
        out.extend(CATEGORIES.get(key, []))
    seen: set[str] = set()
    return [k for k in out if not (k in seen or seen.add(k))]


def auto_select(user_prefs: dict[str, float]) -> list[str]:
    """Pick category keys based on user preference scores (threshold ≥ 0.5).

    Falls back to all categories when the user has no stored preferences yet,
    or when nothing clears the threshold (pathological case).
    """
    if not user_prefs:
        return list(CATEGORIES.keys())
    selected = [
        key for key, kinds in CATEGORIES.items()
        if sum(user_prefs.get(k, 0.5) for k in kinds) / len(kinds) >= 0.5
    ]
    return selected if selected else list(CATEGORIES.keys())
