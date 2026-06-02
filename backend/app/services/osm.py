import httpx


_OSM_API = "https://api.openstreetmap.org/api/0.6"

_PREFIX_TO_TYPE = {"W": "way", "N": "node", "R": "relation"}


async def fetch_opening_hours(xid: str, client: httpx.AsyncClient) -> str | None:
    """Return raw OSM opening_hours string for a given OTM xid, or None.

    Wikidata-based xids (prefix 'Q') have no OSM counterpart and always return None.
    """
    prefix = xid[0].upper() if xid else ""
    osm_type = _PREFIX_TO_TYPE.get(prefix)
    if not osm_type:
        return None

    osm_id = xid[1:]
    try:
        resp = await client.get(
            f"{_OSM_API}/{osm_type}/{osm_id}.json",
            headers={"User-Agent": "IndiGuide/1.0"},
            timeout=8.0,
        )
        if resp.status_code != 200:
            return None
        elements = resp.json().get("elements", [])
        if not elements:
            return None
        return elements[0].get("tags", {}).get("opening_hours")
    except Exception:
        return None
