"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.database.session import check_database
from app.llm.provider_store import resolve_llm

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: bool
    llm_configured: bool
    embedding_provider: str
    vector_backend: str
    llm_source: str
    llm_provider: str
    llm_model: str


@router.get("/health", response_model=HealthResponse, summary="Service health")
async def health() -> HealthResponse:
    db_ok = await check_database()
    llm = resolve_llm()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        environment=settings.environment,
        database=db_ok,
        # Reflects the active provider, which may be a runtime override rather
        # than the .env key.
        llm_configured=llm.configured,
        embedding_provider=settings.embedding_provider,
        vector_backend=settings.vector_backend,
        llm_source=llm.source,
        llm_provider=llm.label,
        llm_model=llm.model,
    )
