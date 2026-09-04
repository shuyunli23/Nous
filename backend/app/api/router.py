"""Aggregate router for API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    chat,
    chat_modes,
    conversations,
    files,
    harmony,
    health,
    llm_config,
    memory,
    pack_archives,
    plugins,
    skills,
    tools,
    usage,
)
from app.nexusmind.api.v1.router import api_router as nexusmind_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(harmony.router)
api_router.include_router(chat.router)
api_router.include_router(chat_modes.router)
api_router.include_router(memory.router)
api_router.include_router(conversations.router)
api_router.include_router(pack_archives.router)
api_router.include_router(plugins.router)
api_router.include_router(skills.router)
api_router.include_router(llm_config.router)
api_router.include_router(usage.router)
api_router.include_router(tools.router)
api_router.include_router(files.router)
api_router.include_router(nexusmind_router)
