"""POST /api/v1/chat - the main conversation endpoint."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.agent.progress import bind_progress, reset_progress
from app.core.deps import CurrentUser, SessionDep
from app.core.exceptions import AppError, ValidationError
from app.core.logging import get_logger
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

logger = get_logger(__name__)

router = APIRouter(tags=["chat"])


@dataclass(frozen=True)
class _ParsedChat:
    message: str
    conversation_id: str | None
    files: list[tuple[str, bytes, str]]
    mode_id: str | None
    provider_id: str | None


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message (creates conversation if conversation_id is omitted)",
)
async def chat(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> ChatResponse:
    parsed = await _parse_chat_request(request)
    svc = ChatService(session)
    return await svc.chat(
        user_id=user.id,
        message=parsed.message,
        conversation_id=parsed.conversation_id,
        files=parsed.files,
        mode_id=parsed.mode_id,
        provider_id=parsed.provider_id,
    )


@router.post(
    "/chat/stream",
    summary="Send a message and stream execution steps as SSE",
)
async def chat_stream(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> StreamingResponse:
    parsed = await _parse_chat_request(request)
    svc = ChatService(session)

    async def events() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        def sink(event: dict) -> None:
            queue.put_nowait(event)

        async def run() -> None:
            token = bind_progress(sink)
            try:
                result = await svc.chat(
                    user_id=user.id,
                    message=parsed.message,
                    conversation_id=parsed.conversation_id,
                    files=parsed.files,
                    mode_id=parsed.mode_id,
                    provider_id=parsed.provider_id,
                )
                payload = result.model_dump(mode="json")
                payload["type"] = "done"
                await queue.put(payload)
            except AppError as exc:
                details = dict(exc.details or {})
                if svc.active_conversation_id:
                    details.setdefault("conversation_id", svc.active_conversation_id)
                await queue.put(
                    {
                        "type": "error",
                        "code": exc.code,
                        "message": exc.message,
                        "details": details,
                    }
                )
            except Exception as exc:
                logger.exception("chat_stream_failed", error=str(exc))
                details = {}
                if svc.active_conversation_id:
                    details["conversation_id"] = svc.active_conversation_id
                await queue.put(
                    {
                        "type": "error",
                        "code": "internal_error",
                        "message": "Unexpected server error.",
                        "details": details or None,
                    }
                )
            finally:
                reset_progress(token)
                await queue.put(None)

        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _parse_chat_request(request: Request) -> _ParsedChat:
    ctype = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in ctype:
        form = await request.form()
        message = str(form.get("message") or "").strip()
        raw_cid = form.get("conversation_id")
        conversation_id = str(raw_cid).strip() if raw_cid not in (None, "") else None
        raw_mode = form.get("mode_id")
        mode_id = str(raw_mode).strip() if raw_mode not in (None, "") else None
        raw_provider = form.get("provider_id")
        provider_id = (
            str(raw_provider).strip() if raw_provider not in (None, "") else None
        )
        files: list[tuple[str, bytes, str]] = []
        for item in form.getlist("files"):
            if not isinstance(item, StarletteUploadFile):
                continue
            data = await item.read()
            files.append(
                (item.filename or "unnamed", data, item.content_type or "")
            )
        if not message and not files:
            raise ValidationError("Message or files are required.")
        return _ParsedChat(
            message=message,
            conversation_id=conversation_id,
            files=files,
            mode_id=mode_id,
            provider_id=provider_id,
        )

    try:
        body = await request.json()
    except Exception as exc:
        raise ValidationError("Request body must be JSON or multipart form data.") from exc
    payload = ChatRequest.model_validate(body)
    return _ParsedChat(
        message=payload.message,
        conversation_id=payload.conversation_id,
        files=[],
        mode_id=payload.mode_id,
        provider_id=payload.provider_id,
    )
