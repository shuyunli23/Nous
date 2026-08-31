"""Conversation titles that name the topic, not the first user line."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Iterable

from app.agent.goal import ATTACH_START
from app.agent.skill_gate import is_retry_or_continue
from app.core.logging import get_logger
from app.memory.conversation_memory import compact_history_text

logger = get_logger(__name__)

TITLE_MAX_LENGTH = 240
_CLIP_SUFFIX = re.compile(r"(?:\u2026|\.{2,})$")
PLACEHOLDER_TITLES = frozenset(
    {"", "新会话", "新對話", "new chat", "new conversation", "untitled"}
)
GENERIC_TITLES = frozenset(
    {
        "日常陪伴",
        "日常闲聊",
        "日常對話",
        "学习交流",
        "学习答疑",
        "工作交流",
        "工作台对话",
        "casual chat",
        "study session",
        "workbench",
        "conversation",
    }
)

_PUNCT = re.compile(r"[\s?？!！。.~…,，、'\"“”‘’]+")
_LEAD_GREETING = re.compile(
    r"^(?:你好呀|你好啊|您好呀|您好|你好|嗨嗨|嗨|哈喽|在吗|在嘛|早上好|晚上好|"
    r"hi+|hello|hey|yo)[\s,，.。!！~～]*",
    re.I,
)
_TRAIL_PUNCT = re.compile(r"[\s?？!！。.~…,，、:：;；'\"“”]+$")
_QUOTES = re.compile(r"^[\s'\"“”‘’「」『』]+|[\s'\"“”‘’「」『』]+$")
_LABEL_PREFIX = re.compile(r"^(?:标题|題目|title)\s*[:：]\s*", re.I)
_IDENTITY = re.compile(
    r"(你是谁|你是什么|你是\s*[?？]|能做什么|你会什么|who are you|what can you do)",
    re.I,
)
_IMAGE_REQ = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?(?:生成|画|绘制)(?:一[张幅个]|张|幅|个)?(.+?)"
    r"(?:的)?(?:图像|图片|插画|照片)$"
)
_FILLER = frozenset(
    {
        "你好",
        "您好",
        "你好呀",
        "你好啊",
        "嗨",
        "哈喽",
        "早",
        "早上好",
        "晚上好",
        "在吗",
        "在嘛",
        "在不在",
        "hi",
        "hii",
        "hiii",
        "hello",
        "hey",
        "yo",
        "谢谢",
        "感谢",
        "thanks",
        "thank you",
        "好的",
        "嗯",
        "嗯嗯",
        "ok",
        "okay",
        "哈哈",
        "试试",
        "再试",
        "继续",
    }
)

_LLM_REFRESH_AT = frozenset({1, 2, 4, 8})
_LLM_TIMEOUT_SECONDS = 30.0
_in_flight: set[str] = set()
_attempted: set[str] = set()
_title_lock = asyncio.Lock()


def _normalize(text: str) -> str:
    return _PUNCT.sub("", (text or "").strip()).lower()


def _is_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text or "")


def compact_user_text(text: str) -> str:
    cleaned = compact_history_text("user", text or "")
    if ATTACH_START in cleaned:
        cleaned = cleaned.split(ATTACH_START, 1)[0]
    return " ".join(cleaned.strip().split())


def is_filler_text(text: str) -> bool:
    compact = compact_user_text(text)
    if not compact:
        return True
    if is_retry_or_continue(compact):
        return True
    return _normalize(compact) in _FILLER


def clip_title(text: str) -> str:
    cleaned = _QUOTES.sub("", (text or "").strip())
    cleaned = _LABEL_PREFIX.sub("", cleaned)
    cleaned = _TRAIL_PUNCT.sub("", cleaned)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return ""
    if len(cleaned) <= TITLE_MAX_LENGTH:
        return cleaned
    return cleaned[:TITLE_MAX_LENGTH].rstrip()


def is_clipped_title(title: str) -> bool:
    return bool(_CLIP_SUFFIX.search((title or "").rstrip()))


def clipped_stem(title: str) -> str:
    return _CLIP_SUFFIX.sub("", (title or "").strip()).rstrip()


def _restores_clip(stem: str, candidate: str) -> bool:
    if not stem or not candidate:
        return False
    if candidate.startswith(stem):
        return len(candidate) > len(stem)
    return candidate[: len(stem)] == stem


def expand_clipped_title(title: str, user_texts: list[str]) -> str:
    """Restore a stored 'prefix…' title from the user turn it was cut from."""
    current = (title or "").strip()
    if not is_clipped_title(current):
        return current
    stem = clipped_stem(current)
    if len(stem) < 4:
        return current
    for raw in user_texts:
        if is_filler_text(raw):
            continue
        compact = compact_user_text(raw)
        stripped = _strip_lead_greeting(compact)
        for candidate in (compact, stripped):
            if _restores_clip(stem, candidate):
                restored = clip_title(candidate)
                if restored:
                    return restored
    rebuilt = title_from_user_texts(user_texts)
    if rebuilt and not is_clipped_title(rebuilt):
        return rebuilt
    return current


def is_placeholder_title(title: str) -> bool:
    return (title or "").strip().lower() in PLACEHOLDER_TITLES


def is_generic_title(title: str) -> bool:
    return (title or "").strip().lower() in GENERIC_TITLES


def _same_topic_text(left: str, right: str) -> bool:
    a = (left or "").strip().rstrip("…").rstrip(".")
    b = (right or "").strip().rstrip("…").rstrip(".")
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= 6 and longer.startswith(shorter)


def looks_like_opener(title: str, user_texts: Iterable[str]) -> bool:
    """True when the title is still just the first real user sentence."""
    current = (title or "").strip().rstrip("…")
    if not current:
        return False
    for raw in user_texts:
        if is_filler_text(raw):
            continue
        compact = compact_user_text(raw)
        shaped = _shape_substantive(compact, cjk=_is_cjk(compact) or True)
        candidates = (
            compact,
            clip_title(compact),
            clip_title(_strip_lead_greeting(compact)),
            shaped,
        )
        if any(_same_topic_text(current, item) for item in candidates if item):
            return True
        break
    return False


def is_weak_title(title: str, user_texts: list[str] | None = None) -> bool:
    text = (title or "").strip()
    if is_placeholder_title(text) or is_generic_title(text):
        return True
    if is_filler_text(text):
        return True
    if user_texts and looks_like_opener(text, user_texts):
        return True
    return False


def _strip_lead_greeting(text: str) -> str:
    previous = ""
    current = text.strip()
    while current and current != previous:
        previous = current
        current = _LEAD_GREETING.sub("", current, count=1).strip()
    return current


def _mode_fallback(mode_key: str | None, mode_name: str | None, *, cjk: bool) -> str:
    if mode_key == "companion":
        return "日常陪伴" if cjk else "Casual chat"
    if mode_key == "tutor":
        return "学习交流" if cjk else "Study session"
    if mode_key == "workbench":
        return "工作交流" if cjk else "Workbench"
    name = (mode_name or "").strip()
    if name:
        return clip_title(name)
    return "新会话" if cjk else "New chat"


def _shape_substantive(text: str, *, cjk: bool) -> str:
    stripped = _strip_lead_greeting(compact_user_text(text))
    if not stripped or is_filler_text(stripped):
        return ""
    if _IDENTITY.search(stripped) and len(_normalize(stripped)) <= 16:
        return "了解助手能力" if cjk or _is_cjk(stripped) else "What the assistant can do"
    image = _IMAGE_REQ.match(stripped)
    if image:
        subject = image.group(1).strip(" 的")
        if subject:
            return clip_title(f"{subject}图像" if _is_cjk(subject) else f"{subject} image")
    return clip_title(stripped)


def title_from_user_texts(
    user_texts: list[str],
    *,
    mode_key: str | None = None,
    mode_name: str | None = None,
) -> str:
    """Best-effort topic title without calling the LLM."""
    compact = [compact_user_text(item) for item in user_texts if compact_user_text(item)]
    has_cjk = any(_is_cjk(item) for item in compact)
    has_english_topic = any(
        item.isascii() and not is_filler_text(item) for item in compact
    )
    cjk = has_cjk or not has_english_topic
    for item in compact:
        shaped = _shape_substantive(item, cjk=cjk)
        if shaped and not is_filler_text(shaped):
            return shaped
    if compact:
        return _mode_fallback(mode_key, mode_name, cjk=cjk)
    return "新会话"


def user_texts_from_messages(messages: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for item in messages:
        if isinstance(item, dict):
            role = str(item.get("role") or "")
            content = str(item.get("content") or "")
        else:
            role = str(getattr(item, "role", "") or "")
            content = str(getattr(item, "content", "") or "")
        if role != "user":
            continue
        cleaned = compact_user_text(content)
        if cleaned:
            out.append(cleaned)
    return out


def title_from_messages(
    messages: Iterable[Any],
    *,
    mode_key: str | None = None,
    mode_name: str | None = None,
) -> str:
    return title_from_user_texts(
        user_texts_from_messages(messages),
        mode_key=mode_key,
        mode_name=mode_name,
    )


def should_llm_refresh(title: str, user_texts: list[str]) -> bool:
    user_n = len(user_texts)
    if user_n < 1:
        return False
    substantive = [item for item in user_texts if not is_filler_text(item)]
    if not substantive and user_n < 3:
        return False
    if is_weak_title(title, user_texts):
        return True
    return user_n in _LLM_REFRESH_AT


def _transcript(messages: Iterable[Any], *, limit: int = 12) -> str:
    lines: list[str] = []
    for item in messages:
        if isinstance(item, dict):
            role = str(item.get("role") or "")
            content = str(item.get("content") or "")
        else:
            role = str(getattr(item, "role", "") or "")
            content = str(getattr(item, "content", "") or "")
        if role not in {"user", "assistant"}:
            continue
        text = compact_history_text(role, content)
        if not text:
            continue
        if role == "assistant":
            text = text[:160].rstrip()
        else:
            text = text[:240].rstrip()
        label = "用户" if role == "user" else "助手"
        lines.append(f"{label}：{text}")
    return "\n".join(lines[-limit:])


async def llm_topic_title(
    messages: Iterable[Any],
    *,
    mode_name: str | None = None,
) -> str | None:
    """Ask the chat model for a short topic title. Returns None on failure."""
    transcript = _transcript(messages)
    if not transcript.strip():
        return None
    user_texts = user_texts_from_messages(messages)
    has_cjk = any(_is_cjk(item) for item in user_texts)
    has_english_topic = any(
        item.isascii() and not is_filler_text(item) for item in user_texts
    )
    cjk = has_cjk or not has_english_topic
    mode_line = f"对话模式：{mode_name}\n" if mode_name else ""
    lang = "中文" if cjk else "the same language as the user"
    prompt = (
        "根据对话内容写一个会话标题。\n"
        "规则：\n"
        f"- 用{lang}，8 到 40 个字，名词短语，概括整段对话的主题，不要复述第一句话。\n"
        "- 不要引号、不要句号、不要「标题：」前缀。\n"
        "- 寒暄、hi、你好不能当标题。\n"
        "- 只输出标题本身。\n\n"
        f"{mode_line}{transcript}"
    )
    from app.llm.client import chat_complete
    from app.llm.usage import PURPOSE_OTHER, usage_scope

    with usage_scope(purpose=PURPOSE_OTHER):
        result = await chat_complete(
            [
                {
                    "role": "system",
                    "content": "You write concise conversation titles. Reply with the title only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=48,
        )
    title = clip_title(str(result.content or ""))
    if not title or is_filler_text(title) or is_placeholder_title(title):
        return None
    return title


async def llm_topic_title_timed(
    messages: Iterable[Any],
    *,
    mode_name: str | None = None,
    timeout: float = _LLM_TIMEOUT_SECONDS,
) -> str | None:
    try:
        return await asyncio.wait_for(
            llm_topic_title(messages, mode_name=mode_name),
            timeout=timeout,
        )
    except Exception as exc:
        logger.info(
            "conversation_title_llm_skipped",
            error=repr(exc),
            exc_type=type(exc).__name__,
        )
        return None


def schedule_title_job(conversation_id: str, factory, *, force: bool = False) -> None:
    """Fire-and-forget LLM retitle; no-ops if a job is already running."""
    cid = (conversation_id or "").strip()
    if not cid or cid in _in_flight:
        return
    if not force and cid in _attempted:
        return
    _in_flight.add(cid)
    _attempted.add(cid)

    async def _run() -> None:
        try:
            async with _title_lock:
                await factory(cid)
        except Exception as exc:
            logger.info(
                "conversation_title_job_failed",
                conversation_id=cid,
                error=repr(exc),
            )
        finally:
            _in_flight.discard(cid)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _in_flight.discard(cid)
        return
    loop.create_task(_run())
