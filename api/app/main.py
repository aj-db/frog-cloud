"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import cors_origin_list
from app.db import dispose_engine
from app.routers import crawls, internal, profiles, results, schedules, tenants


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    dispose_engine()


app = FastAPI(
    title="Vulpes API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origin_list(),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "svix-id", "svix-timestamp", "svix-signature"],
)

app.include_router(tenants.router, prefix="/api")
app.include_router(tenants.webhook_router, prefix="/api")
app.include_router(crawls.router, prefix="/api")
app.include_router(results.router, prefix="/api/crawls")
app.include_router(profiles.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(internal.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
