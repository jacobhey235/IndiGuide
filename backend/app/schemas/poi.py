from pydantic import BaseModel, ConfigDict


class POIBasic(BaseModel):
    xid: str
    name: str
    lon: float
    lat: float
    kinds: str
    rate: float
    opening_hours: str | None = None

    model_config = ConfigDict(from_attributes=True)


class POIDetail(POIBasic):
    wikipedia_excerpt: str | None
    image_url: str | None
    address: str | None
    opening_hours: str | None
