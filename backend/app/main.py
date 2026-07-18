from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import cases, health, operations, orchestrator, policies
from app.config import get_settings
from app.db.session import dispose_engine
from app.middleware import CorrelationIdMiddleware
from app.mock_apis import mock_endpoints


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    dispose_engine()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.app_debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIdMiddleware)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(cases.router)
api_v1_router.include_router(orchestrator.router)
api_v1_router.include_router(operations.router)
api_v1_router.include_router(policies.router)
if settings.enable_mock_apis:
    api_v1_router.include_router(mock_endpoints.router)
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
