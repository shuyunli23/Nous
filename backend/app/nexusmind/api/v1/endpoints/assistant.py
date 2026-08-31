"""AI 知识助手 API。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.nexusmind.api.deps import DBSession
from app.nexusmind.config.features import FEATURES
from app.nexusmind.schemas.assistant import AssistantAskRequest, AssistantAskResponse, CitationOut
from app.nexusmind.services import assistant_service
from app.nexusmind.utils.errors import ValidationError

logger = get_logger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _to_response(reply: assistant_service.AssistantReply) -> AssistantAskResponse:
    return AssistantAskResponse(
        answer=reply.answer,
        citations=[
            CitationOut(
                id=c.id,
                title=c.title,
                summary=c.summary,
                score=c.score,
                match_fields=c.match_fields,
            )
            for c in reply.citations
        ],
        source=reply.source,  # type: ignore[arg-type]
        model=reply.model,
        latency_ms=reply.latency_ms,
        execution_trace=reply.execution_trace,
    )


@router.post("/ask", response_model=AssistantAskResponse, summary="向知识助手提问")
async def ask(payload: AssistantAskRequest, db: DBSession) -> AssistantAskResponse:
    if not FEATURES.get("ai_assistant"):
        raise ValidationError("AI 助手尚未启用")

    history = [{"role": m.role, "content": m.content} for m in payload.history]
    reply = await assistant_service.ask(
        db,
        message=payload.message,
        history=history,
        model_id=payload.model_id,
        top_k=payload.top_k,
    )
    return _to_response(reply)


@router.post("/ask/stream", summary="向知识助手提问并流式返回检索与模型输出")
async def ask_stream(payload: AssistantAskRequest, db: DBSession) -> StreamingResponse:
    if not FEATURES.get("ai_assistant"):
        raise ValidationError("AI 助手尚未启用")

    history = [{"role": m.role, "content": m.content} for m in payload.history]

    async def events() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        def sink(event: dict) -> None:
            queue.put_nowait(event)

        async def run() -> None:
            try:
                reply = await assistant_service.ask(
                    db,
                    message=payload.message,
                    history=history,
                    model_id=payload.model_id,
                    top_k=payload.top_k,
                    emit=sink,
                )
                data = _to_response(reply).model_dump(mode="json")
                data["type"] = "done"
                await queue.put(data)
            except AppError as exc:
                await queue.put(
                    {
                        "type": "error",
                        "code": exc.code,
                        "message": exc.message,
                        "details": getattr(exc, "details", None) or {},
                    }
                )
            except Exception as exc:
                logger.exception("assistant_stream_failed", error=str(exc))
                await queue.put(
                    {
                        "type": "error",
                        "code": "internal_error",
                        "message": "Unexpected server error.",
                    }
                )
            finally:
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
