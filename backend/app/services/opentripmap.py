from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class OTMPlace:
    xid: str
    name: str
    lon: float
    lat: float
    kinds: str
    rate: float


@dataclass
class OTMDetail:
    xid: str
    name: str
    lon: float
    lat: float
    kinds: str
    rate: float
    wikipedia_excerpt: str | None
    image_url: str | None
    address: str | None


class OpenTripMapClient:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._key = settings.OTM_API_KEY
        self._base = settings.OTM_BASE_URL

    async def fetch_radius(
        self,
        lat: float,
        lon: float,
        radius_m: int,
        limit: int = 30,
        kinds: list[str] | None = None,
    ) -> list[OTMPlace]:
        params = {
            "radius": radius_m,
            "lon": lon,
            "lat": lat,
            "kinds": ",".join(kinds) if kinds else "interesting_places",
            "rate": "1",
            "limit": limit,
            "format": "json",
            "apikey": self._key,
        }
        resp = await self._client.get(f"{self._base}/radius", params=params)
        resp.raise_for_status()
        data = resp.json()

        results: list[OTMPlace] = []
        for item in data:
            point = item.get("point", {})
            results.append(
                OTMPlace(
                    xid=item["xid"],
                    name=item.get("name") or item["xid"],
                    lon=float(point.get("lon", 0)),
                    lat=float(point.get("lat", 0)),
                    kinds=item.get("kinds", ""),
                    rate=float(item.get("rate", 0)),
                )
            )
        return results

    async def fetch_detail(self, xid: str) -> OTMDetail:
        params = {"apikey": self._key}
        resp = await self._client.get(f"{self._base}/xid/{xid}", params=params)
        resp.raise_for_status()
        d = resp.json()

        point = d.get("point", {})
        lon = float(point.get("lon", 0))
        lat = float(point.get("lat", 0))

        # wikipedia_extracts is a nested object: {"text": "...", "html": "..."}
        wiki = d.get("wikipedia_extracts")
        wikipedia_excerpt = wiki.get("text") if isinstance(wiki, dict) else None

        image_url = d.get("image") or None

        addr = d.get("address", {})
        address_parts = [addr.get("road"), addr.get("city"), addr.get("country")]
        address = ", ".join(p for p in address_parts if p) or None

        return OTMDetail(
            xid=d.get("xid", xid),
            name=d.get("name") or xid,
            lon=lon,
            lat=lat,
            kinds=d.get("kinds", ""),
            rate=float(d.get("rate", 0)),
            wikipedia_excerpt=wikipedia_excerpt,
            image_url=image_url,
            address=address,
        )
