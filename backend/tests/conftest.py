"""Test setup: isolated indiguide_test database + mocks for OTM/OSRM.

DB connection is configured via environment variables (defaults work for local dev):
  TEST_DB_USER  — PostgreSQL user (default: current OS user)
  TEST_DB_PASS  — password, omit for passwordless/trust auth (default: empty)
  TEST_DB_HOST  — host (default: localhost)
  TEST_DB_PORT  — port (default: 5432)
  TEST_DB_NAME  — database name (default: indiguide_test)

For Docker Compose setup, set:
  TEST_DB_USER=indiguide TEST_DB_PASS=changeme TEST_DB_HOST=db
"""

import getpass
import os

_user = os.getenv("TEST_DB_USER", "indiguide")
_pass = os.getenv("TEST_DB_PASS", "indiguide1234")
_host = os.getenv("TEST_DB_HOST", "127.0.0.1")
_port = os.getenv("TEST_DB_PORT", "5433")
_name = os.getenv("TEST_DB_NAME", "indiguide_test")

_auth = f"{_user}:{_pass}@{_host}:{_port}" if _pass else f"{_user}@{_host}:{_port}"
_ADMIN_URL = f"postgresql://{_auth}/postgres"
_TEST_DB_URL = f"postgresql+asyncpg://{_auth}/{_name}"

# Must be set before any app import so pydantic-settings picks up the test DB.
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-1234567890abcdef1234")
os.environ.setdefault("OTM_API_KEY", "test-key")

import asyncpg
import httpx
import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.core.database import Base, engine
from app.main import app
from app.services.opentripmap import OTMPlace
from app.services.osrm import OSRMTrip

# ── Fake external-service data ─────────────────────────────────────────────────
# Three POIs spaced ~440 m apart due north of start (55.755, 37.617).
# All clear the 400 m decluster threshold and the 40° corridor filter.
FAKE_POIS = [
    OTMPlace(xid="t001", name="Музей",  lon=37.617, lat=55.759, kinds="museums",  rate=2.5),
    OTMPlace(xid="t002", name="Парк",   lon=37.617, lat=55.763, kinds="parks",    rate=2.0),
    OTMPlace(xid="t003", name="Собор",  lon=37.617, lat=55.767, kinds="churches", rate=2.0),
]

_C = [[37.617, 55.755], [37.617, 55.759], [37.617, 55.763], [37.617, 55.767]]
FAKE_TRIP = OSRMTrip(
    geometry={"type": "LineString", "coordinates": _C},
    distance_m=1800.0,
    duration_s=1350.0,
    leg_durations=[450, 450, 450],
    ordered_indices=[1, 2, 3],
    leg_geometries=[
        {"type": "LineString", "coordinates": _C[0:2]},
        {"type": "LineString", "coordinates": _C[1:3]},
        {"type": "LineString", "coordinates": _C[2:4]},
    ],
)

# ── Database fixtures ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Create indiguide_test DB (if absent) and build schema once per session."""
    conn = await asyncpg.connect(_ADMIN_URL)
    try:
        await conn.execute("CREATE DATABASE indiguide_test")
    except asyncpg.exceptions.DuplicateDatabaseError:
        pass
    finally:
        await conn.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Wipe all rows between tests for full isolation."""
    yield
    async with engine.connect() as conn:
        await conn.execute(sa.text(
            "TRUNCATE TABLE poi_interactions, route_waypoints, user_preferences, "
            "routes, pois, users RESTART IDENTITY CASCADE"
        ))
        await conn.commit()


# ── HTTP client ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    # ASGITransport does not run the ASGI lifespan, so set http_client manually.
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        app.state.http_client = http_client
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c


# ── External-service mock ──────────────────────────────────────────────────────

@pytest.fixture
def mock_external():
    """Replace OTM and OSRM HTTP calls with fixed fake responses."""
    otm = AsyncMock()
    otm.fetch_radius.return_value = FAKE_POIS
    osrm = AsyncMock()
    osrm.get_pairwise_routes.return_value = FAKE_TRIP
    osrm.get_route.return_value = FAKE_TRIP
    with (
        patch("app.services.route_generator.OpenTripMapClient", return_value=otm),
        patch("app.services.route_generator.OSRMClient", return_value=osrm),
        patch("app.api.routes.OSRMClient", return_value=osrm),
    ):
        yield


# ── User helpers ───────────────────────────────────────────────────────────────

_U1 = {"email": "user1@test.com", "username": "user1", "password": "password123"}
_U2 = {"email": "user2@test.com", "username": "user2", "password": "password123"}


async def _register_and_login(client: AsyncClient, user: dict) -> dict:
    await client.post("/api/auth/register", json=user)
    r = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth1(client):
    return await _register_and_login(client, _U1)


@pytest_asyncio.fixture
async def auth2(client):
    return await _register_and_login(client, _U2)


# ── Route helpers ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def route(client, auth1, mock_external):
    """Draft route with 2 waypoints owned by user1."""
    r = await client.post(
        "/api/routes/generate",
        headers=auth1,
        json={
            "start_lat": 55.755,
            "start_lon": 37.617,
            "distance_m": 2000,
            "num_pois": 2,
            "selected_categories": ["museums"],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest_asyncio.fixture
async def route3(client, auth1, mock_external):
    """Draft route with 3 waypoints owned by user1 (for edit/clone scenarios)."""
    r = await client.post(
        "/api/routes/generate",
        headers=auth1,
        json={
            "start_lat": 55.755,
            "start_lon": 37.617,
            "distance_m": 2000,
            "num_pois": 3,
            "selected_categories": ["museums"],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest_asyncio.fixture
async def published_route(client, auth1, route3):
    """User1's route saved and published (3 waypoints)."""
    rid = route3["id"]
    await client.put(f"/api/routes/{rid}", headers=auth1, json={"is_saved": True})
    r = await client.put(f"/api/routes/{rid}", headers=auth1, json={"is_published": True})
    assert r.status_code == 200, r.text
    return r.json()
