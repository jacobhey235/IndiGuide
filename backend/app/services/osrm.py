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
    ordered_indices: list[int]  # re-ordered input indices (excluding start anchor)


class OSRMClient:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._base = settings.OSRM_BASE_URL

    async def get_trip(
        self,
        waypoints: list[tuple[float, float]],  # [(lat, lon), ...], start is index 0
        roundtrip: bool,
    ) -> OSRMTrip:
        # OSRM expects lon,lat order in the URL
        coords = ";".join(f"{lon},{lat}" for lat, lon in waypoints)

        # For roundtrip, OSRM handles the return leg automatically — no destination param.
        # For one-way, pin start and end explicitly.
        if roundtrip:
            params: dict = {
                "overview": "full",
                "geometries": "polyline",
                "annotations": "false",
                "roundtrip": "true",
                "source": "first",
            }
        else:
            params = {
                "overview": "full",
                "geometries": "polyline",
                "annotations": "false",
                "roundtrip": "false",
                "source": "first",
                "destination": "last",
            }

        url = f"{self._base}/trip/v1/walking/{coords}"
        resp = await self._client.get(url, params=params)

        # Public OSRM sometimes rejects roundtrip=false — retry as circular
        if resp.status_code != 200 and not roundtrip:
            params = {
                "overview": "full",
                "geometries": "polyline",
                "annotations": "false",
                "roundtrip": "true",
                "source": "first",
            }
            resp = await self._client.get(url, params=params)

        resp.raise_for_status()
        data = resp.json()

        if not data.get("trips"):
            raise ValueError("OSRM returned no trips for these coordinates.")

        trip = data["trips"][0]
        osrm_waypoints = data["waypoints"]

        geometry = _decode_polyline(trip["geometry"])
        distance_m = float(trip["distance"])
        duration_s = float(trip["duration"])
        leg_durations = [int(leg["duration"]) for leg in trip["legs"]]

        # waypoints[0] = start anchor; waypoints[1..N] = POIs
        poi_count = len(waypoints) - 1
        poi_input_indices = list(range(1, poi_count + 1))
        ordered_indices = sorted(
            poi_input_indices,
            key=lambda i: osrm_waypoints[i]["waypoint_index"],
        )

        return OSRMTrip(
            geometry=geometry,
            distance_m=distance_m,
            duration_s=duration_s,
            leg_durations=leg_durations,
            ordered_indices=ordered_indices,
        )


def _decode_polyline(encoded: str) -> dict:
    # polyline.decode returns [(lat, lon), ...] — GeoJSON needs [lon, lat]
    coords = pl.decode(encoded)
    return {
        "type": "LineString",
        "coordinates": [[lon, lat] for lat, lon in coords],
    }
