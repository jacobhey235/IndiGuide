from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import polyline as pl

from app.core.config import settings


@dataclass
class OSRMTrip:
    geometry: dict          # GeoJSON LineString {type, coordinates: [[lon, lat], ...]}
    distance_m: float
    duration_s: float
    leg_durations: list[int]  # seconds per leg
    ordered_indices: list[int]  # visit order of input indices (excluding start)
    leg_geometries: list[dict]  # per-leg GeoJSON LineStrings


class OSRMClient:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._base = settings.OSRM_BASE_URL

    async def get_pairwise_routes(
        self,
        waypoints: list[tuple[float, float]],  # [(lat, lon), ...], in desired visit order
    ) -> OSRMTrip:
        """Build a route by calling OSRM independently for each consecutive pair, in parallel."""
        if len(waypoints) < 2:
            raise ValueError("Need at least 2 waypoints.")

        async def _segment(a: tuple[float, float], b: tuple[float, float]) -> dict:
            coords = f"{a[1]},{a[0]};{b[1]},{b[0]}"
            params = {"overview": "full", "geometries": "polyline", "steps": "true"}
            resp = await self._client.get(
                f"{self._base}/route/v1/walking/{coords}", params=params
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("routes"):
                raise ValueError(f"OSRM returned no route for {a} -> {b}.")
            route = data["routes"][0]
            leg = route["legs"][0]
            return {
                "geometry": _decode_polyline(route["geometry"]),
                "distance_m": float(route["distance"]),
                "duration_s": float(route["duration"]),
                "leg_duration": int(leg["duration"]),
                "leg_geometry": _leg_geometry_from_steps(leg["steps"]),
            }

        pairs = list(zip(waypoints[:-1], waypoints[1:]))
        segments = await asyncio.gather(*[_segment(a, b) for a, b in pairs])

        merged_coords: list[list[float]] = []
        for seg in segments:
            coords = seg["geometry"]["coordinates"]
            if merged_coords and coords:
                merged_coords.extend(coords[1:] if coords[0] == merged_coords[-1] else coords)
            else:
                merged_coords.extend(coords)

        n = len(waypoints) - 1
        return OSRMTrip(
            geometry={"type": "LineString", "coordinates": merged_coords},
            distance_m=sum(s["distance_m"] for s in segments),
            duration_s=sum(s["duration_s"] for s in segments),
            leg_durations=[s["leg_duration"] for s in segments],
            ordered_indices=list(range(1, n + 1)),
            leg_geometries=[s["leg_geometry"] for s in segments],
        )

    async def get_route(
        self,
        waypoints: list[tuple[float, float]],  # [(lat, lon), ...] in desired visit order
    ) -> OSRMTrip:
        """Linear route: visits waypoints in the given order via shortest walking paths."""
        coords = ";".join(f"{lon},{lat}" for lat, lon in waypoints)
        params: dict = {
            "overview": "full",
            "geometries": "polyline",
            "steps": "true",
        }
        url = f"{self._base}/route/v1/walking/{coords}"
        resp = await self._client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("routes"):
            raise ValueError("OSRM returned no routes for these coordinates.")

        route = data["routes"][0]
        geometry = _decode_polyline(route["geometry"])
        distance_m = float(route["distance"])
        duration_s = float(route["duration"])
        leg_durations = [int(leg["duration"]) for leg in route["legs"]]
        leg_geometries = [_leg_geometry_from_steps(leg["steps"]) for leg in route["legs"]]

        poi_count = len(waypoints) - 1
        ordered_indices = list(range(1, poi_count + 1))

        return OSRMTrip(
            geometry=geometry,
            distance_m=distance_m,
            duration_s=duration_s,
            leg_durations=leg_durations,
            ordered_indices=ordered_indices,
            leg_geometries=leg_geometries,
        )


def _decode_polyline(encoded: str) -> dict:
    # polyline.decode returns [(lat, lon), ...] — GeoJSON needs [lon, lat]
    coords = pl.decode(encoded)
    return {
        "type": "LineString",
        "coordinates": [[lon, lat] for lat, lon in coords],
    }


def _leg_geometry_from_steps(steps: list[dict]) -> dict:
    coords: list[list[float]] = []
    for step in steps:
        step_coords = _decode_polyline(step["geometry"])["coordinates"]
        if coords and step_coords:
            start = 1 if step_coords[0] == coords[-1] else 0
            coords.extend(step_coords[start:])
        else:
            coords.extend(step_coords)
    return {"type": "LineString", "coordinates": coords}
