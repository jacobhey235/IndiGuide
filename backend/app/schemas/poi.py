from pydantic import BaseModel, ConfigDict


class POIBasic(BaseModel):
    xid: str
    name: str
    lon: float
    lat: float
    kinds: str
    rate: float

    model_config = ConfigDict(from_attributes=True)


class POIDetail(POIBasic):
    wikipedia_excerpt: str | None
    image_url: str | None
    address: str | None
