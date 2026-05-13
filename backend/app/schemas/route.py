from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.route import RouteStatus
from app.schemas.poi import POIBasic


class WaypointOut(BaseModel):
    id: int
    poi_xid: str
    order_index: int
    is_visited: bool
    visited_at: datetime | None
    leg_duration_s: int | None
    poi: POIBasic

    model_config = ConfigDict(from_attributes=True)


class RouteOut(BaseModel):
    id: uuid.UUID
    name: str
    status: RouteStatus
    is_saved: bool
    is_published: bool
    start_lon: float
    start_lat: float
    total_distance_m: float
    osrm_geometry: dict | None
    leg_geometries: list[dict] | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    waypoints: list[WaypointOut]

    model_config = ConfigDict(from_attributes=True)


class RouteSummary(BaseModel):
    id: uuid.UUID
    name: str
    status: RouteStatus
    is_saved: bool
    is_published: bool
    total_distance_m: float
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    waypoints: list[WaypointOut]

    model_config = ConfigDict(from_attributes=True)


class UserRouteSummary(RouteSummary):
    author_username: str


class PublicRouteSummary(BaseModel):
    id: uuid.UUID
    name: str
    status: RouteStatus
    total_distance_m: float
    created_at: datetime
    waypoints: list[WaypointOut]
    author_username: str

    model_config = ConfigDict(from_attributes=True)


class PublicRouteOut(BaseModel):
    id: uuid.UUID
    name: str
    status: RouteStatus
    total_distance_m: float
    start_lon: float
    start_lat: float
    osrm_geometry: dict | None
    leg_geometries: list[dict] | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    waypoints: list[WaypointOut]
    author_username: str

    model_config = ConfigDict(from_attributes=True)


class RouteGenerateRequest(BaseModel):
    start_lat: float
    start_lon: float
    distance_m: float = Field(ge=500, le=20_000)
    num_pois: int = Field(ge=2, le=15)
    selected_categories: list[str] | None = Field(default=None, max_length=7)
    name: str | None = None


class RouteUpdateRequest(BaseModel):
    name: str | None = None
    waypoint_order: list[str] | None = None   # poi_xids in desired order
    remove_poi_xids: list[str] | None = None
    is_saved: bool | None = None
    is_published: bool | None = None


class RateWaypointRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


class NavigationResponse(BaseModel):
    geometry: dict      # GeoJSON LineString of the walking route
    distance_m: float
    duration_s: float
