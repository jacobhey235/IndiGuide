from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=15.0) as client:
        app.state.http_client = client
        yield


app = FastAPI(title="IndiGuide API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import auth, pois, routes  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(routes.router, prefix="/api/routes", tags=["routes"])
app.include_router(pois.router, prefix="/api/pois", tags=["pois"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
