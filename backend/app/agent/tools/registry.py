"""Tool registry: OpenAI schemas + async handlers."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import builtins
from app.core.logging import get_logger

logger = get_logger(__name__)

ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


_TOOLS: dict[str, dict[str, Any]] = {
    "web_search": {
        "description": (
            "Search the public web for up-to-date information "
            "(projects, docs, news, GitHub repos). "
            "Use for anything that may have changed or is not in your training data. "
            "If the first query returns weak/empty hits, retry with a more specific "
            "query (add 'github', official English name, etc.), then fetch_url."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query in the user's language or English.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results (1-10).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        "handler": builtins.web_search,
    },
    "fetch_url": {
        "description": (
            "Fetch a URL and return readable text content (HTML stripped). "
            "Use after web_search when you need the page body."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Absolute http(s) URL to fetch.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters to return (default 6000).",
                    "default": 6000,
                },
            },
            "required": ["url"],
        },
        "handler": builtins.fetch_url,
    },
    "get_weather": {
        "description": (
            "Get current weather and a short forecast for a city or location."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, e.g. 'Beijing', 'Shanghai', 'Tokyo'.",
                },
            },
            "required": ["location"],
        },
        "handler": builtins.get_weather,
    },
    "create_presentation": {
        "description": (
            "Create a designed PowerPoint (.pptx) ONLY when the user explicitly asks for PPT/slides. "
            "If they asked for a webpage / demo / H5 / 汇报页 / 给领导看的在线演示, use create_webpage. "
            "If they asked for a PDF / 讲义 / 教程文档, use create_pdf instead. "
            "ALWAYS pass title AND slides together in a single call (never title-only). "
            "For programming tutorials use layout=code with a multiline `code` "
            "string (spaces/indentation preserved) plus optional explain bullets. "
            "Mix layouts: title/section/bullets/two_column/cards/code/quote/closing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Deck title (also used for cover if no title slide).",
                },
                "subtitle": {
                    "type": "string",
                    "description": "Optional cover subtitle / audience line.",
                },
                "theme": {
                    "type": "string",
                    "description": "Visual theme: nous (default teal), slate, ink, dawn.",
                    "enum": ["nous", "slate", "ink", "dawn"],
                    "default": "nous",
                },
                "slides": {
                    "type": "array",
                    "description": (
                        "Ordered slides (required). For indented source use "
                        "layout=code with multiline `code` + optional `explain`."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "layout": {
                                "type": "string",
                                "description": (
                                    "title|section|bullets|two_column|cards|code|quote|closing"
                                ),
                            },
                            "heading": {"type": "string"},
                            "subtitle": {"type": "string"},
                            "bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "3–5 short lines for bullets layout.",
                            },
                            "code": {
                                "type": "string",
                                "description": (
                                    "Multiline source for layout=code. Keep indentation "
                                    "with spaces; use \\n for newlines."
                                ),
                            },
                            "language": {
                                "type": "string",
                                "description": "Code language label, e.g. java.",
                            },
                            "explain": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Right-side explanations for code layout.",
                            },
                            "left_heading": {"type": "string"},
                            "left_bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "right_heading": {"type": "string"},
                            "right_bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "cards": {
                                "type": "array",
                                "description": "KPI cards: [{label, value, hint}]",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "value": {"type": "string"},
                                        "hint": {"type": "string"},
                                    },
                                },
                            },
                            "quote": {"type": "string"},
                            "attribution": {"type": "string"},
                            "notes": {"type": "string"},
                        },
                        "required": ["heading"],
                    },
                },
            },
            "required": ["title", "slides"],
        },
        "handler": builtins.create_presentation,
    },
    "create_pdf": {
        "description": (
            "Create a downloadable A4 PDF handout/tutorial (NOT PowerPoint). "
            "Use this whenever the user asks for PDF / 讲义 / 教程文档 / 学习资料. "
            "ALWAYS pass title AND sections together. "
            "Each section may include heading, body, bullets, and/or code+language. "
            "Do not substitute create_presentation when a PDF was requested."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Document title (cover page).",
                },
                "subtitle": {
                    "type": "string",
                    "description": "Optional cover subtitle / audience line.",
                },
                "sections": {
                    "type": "array",
                    "description": "Ordered document sections (required).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "level": {
                                "type": "integer",
                                "description": "1 = chapter, 2 = subsection.",
                                "default": 1,
                            },
                            "body": {
                                "type": "string",
                                "description": "Paragraphs. Separate with blank lines.",
                            },
                            "bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "code": {
                                "type": "string",
                                "description": "Source snippet; keep indentation.",
                            },
                            "language": {
                                "type": "string",
                                "description": "Code language label, e.g. java.",
                            },
                        },
                        "required": ["heading"],
                    },
                },
            },
            "required": ["title", "sections"],
        },
        "handler": builtins.create_pdf,
    },
    "create_webpage": {
        "description": (
            "Create a self-contained HTML briefing page for leadership demos / 网页汇报. "
            "Use this when the user wants 网页, 页面, demo, H5, 在线演示, 汇报页, "
            "or '给领导看' WITHOUT explicitly asking for PPT. "
            "The page is full-viewport, keyboard-paged, fullscreen-ready. "
            "ALWAYS pass title AND sections together. Mix layouts: "
            "hero / kpis / narrative / split / timeline / cards / architecture / "
            "figure / code / quote / closing. "
            "If the user uploaded a paper/PDF, you MUST include layout=figure pages "
            "using the extracted PAPER FIGURES src URLs (do not generate fake figures). "
            "If they asked to add a 证件照 / 一寸照 / 求职者头像 from a resume, pass that "
            "portrait URL as hero.image — the cover renders it. Never generate_image a fake face. "
            "If they asked for 伪代码 / algorithm / code, use layout=code with a multiline "
            "`code` string (indentation preserved). A heading without `code` is empty. "
            "Do NOT substitute create_presentation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Briefing title (cover headline).",
                },
                "subtitle": {
                    "type": "string",
                    "description": "One-line value proposition under the title.",
                },
                "presenter": {
                    "type": "string",
                    "description": "Who is presenting, e.g. 李同学.",
                },
                "audience": {
                    "type": "string",
                    "description": "Who is watching, e.g. 技术负责人 / 管理层.",
                },
                "date": {
                    "type": "string",
                    "description": "Date label, e.g. 2026.08.15.",
                },
                "theme": {
                    "type": "string",
                    "enum": ["nous", "slate", "ink", "dawn"],
                    "default": "nous",
                    "description": "Visual theme.",
                },
                "sections": {
                    "type": "array",
                    "description": (
                        "Ordered full-screen sections (required). "
                        "Start with hero, include kpis + architecture + closing talking_points."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "layout": {
                                "type": "string",
                                "description": (
                                    "hero|kpis|narrative|split|timeline|cards|"
                                    "architecture|figure|code|quote|closing"
                                ),
                            },
                            "nav": {
                                "type": "string",
                                "description": "Short nav label (2–6 chars).",
                            },
                            "kicker": {"type": "string"},
                            "heading": {"type": "string"},
                            "subtitle": {"type": "string"},
                            "body": {
                                "type": "string",
                                "description": "1–3 short paragraphs. Conclusion first.",
                            },
                            "code": {
                                "type": "string",
                                "description": (
                                    "Multiline source/pseudocode for layout=code. "
                                    "Keep indentation; do not put the algorithm only in heading."
                                ),
                            },
                            "language": {
                                "type": "string",
                                "description": "Optional language label for layout=code.",
                            },
                            "explain": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Short notes beside the code block.",
                            },
                            "bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "metrics": {
                                "type": "array",
                                "description": "KPI cards: [{label, value, hint}]",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "value": {"type": "string"},
                                        "hint": {"type": "string"},
                                    },
                                },
                            },
                            "cards": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "tag": {"type": "string"},
                                        "title": {"type": "string"},
                                        "body": {"type": "string"},
                                    },
                                },
                            },
                            "steps": {
                                "type": "array",
                                "description": "Timeline: [{when, title, body}]",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "when": {"type": "string"},
                                        "title": {"type": "string"},
                                        "body": {"type": "string"},
                                    },
                                },
                            },
                            "layers": {
                                "type": "array",
                                "description": (
                                    "Architecture tiers: [{name, items:['React','FastAPI']}]"
                                ),
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "items": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                            },
                            "left_heading": {"type": "string"},
                            "left_bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "right_heading": {"type": "string"},
                            "right_bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "quote": {"type": "string"},
                            "attribution": {"type": "string"},
                            "image": {
                                "type": "string",
                                "description": (
                                    "Image URL from PAPER FIGURES / uploads / crop_image. "
                                    "On layout=hero this is the cover portrait (证件照). "
                                    "On layout=figure this is the main figure."
                                ),
                            },
                            "caption": {
                                "type": "string",
                                "description": "Caption under the main image.",
                            },
                            "images": {
                                "type": "array",
                                "description": "Extra figures: [{src, caption}]",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "src": {"type": "string"},
                                        "caption": {"type": "string"},
                                    },
                                },
                            },
                            "talking_points": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "What to say out loud on the closing page.",
                            },
                        },
                        "required": ["heading"],
                    },
                },
            },
            "required": ["title", "sections"],
        },
        "handler": builtins.create_webpage,
    },
    "crop_image": {
        "description": (
            "Crop a region from an uploaded/exported image and save a PNG. "
            "Use this for 一寸照 / 证件照 / 从简历截头像. "
            "Pass a PAPER FIGURES URL as src. preset=portrait crops a typical "
            "top-right resume ID photo (or keeps an already-portrait embed). "
            "Then pass the returned download_url as create_webpage hero.image. "
            "Never use generate_image to invent a person's face."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "src": {
                    "type": "string",
                    "description": (
                        "Existing image URL, e.g. /api/v1/files/uploads/xxx_p1.png "
                        "or a portrait embed from PAPER FIGURES."
                    ),
                },
                "preset": {
                    "type": "string",
                    "enum": ["portrait", "id_photo", "headshot"],
                    "description": "Default portrait: keep a headshot or crop top-right of a page.",
                },
                "left": {"type": "number", "description": "Crop left (ratio 0-1 or pixels)."},
                "top": {"type": "number", "description": "Crop top."},
                "width": {"type": "number", "description": "Crop width."},
                "height": {"type": "number", "description": "Crop height."},
                "unit": {
                    "type": "string",
                    "enum": ["ratio", "pixel"],
                    "description": "How to interpret left/top/width/height. Default ratio.",
                },
                "filename_hint": {"type": "string"},
            },
            "required": ["src"],
        },
        "handler": builtins.crop_image,
    },
    "generate_image": {
        "description": (
            "Generate an image from a text prompt (illustration / diagram / 文生图). "
            "Do NOT use this for a real person's 证件照 / 一寸照 / resume photo — "
            "those already exist in PAPER FIGURES; use crop_image + hero.image instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "Detailed image prompt (subject, camera, lighting, style, "
                        "negative constraints)."
                    ),
                },
                "size": {
                    "type": "string",
                    "description": "1024x1024 | 1024x1792 | 1792x1024",
                    "default": "1024x1024",
                },
                "filename_hint": {
                    "type": "string",
                    "description": "Optional short filename stem.",
                },
            },
            "required": ["prompt"],
        },
        "handler": builtins.generate_image,
    },
    "calculator": {
        "description": (
            "Evaluate a mathematical expression safely "
            "(arithmetic, powers, parentheses)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression, e.g. '(12.5 + 3) * 0.08'.",
                },
            },
            "required": ["expression"],
        },
        "handler": builtins.calculator,
    },
    "current_datetime": {
        "description": "Return the current date and time (UTC and local).",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone, e.g. 'Asia/Shanghai'. Optional.",
                },
            },
        },
        "handler": builtins.current_datetime,
    },
    "run_command": {
        "description": (
            "Execute a shell command on the host inside a confined sandbox "
            "workspace, and return its stdout/stderr and exit code. "
            "Use for real tasks: inspect files, run scripts, git, build/test, "
            "data wrangling. STATELESS — no shell state persists between calls, "
            "so pass `workdir` instead of using `cd`. "
            "ALWAYS check the `[exit code: N]` marker on every result and "
            "investigate a nonzero exit before moving on. "
            "The command runs in `read-only` or `workspace-write` mode; if a "
            "call is blocked because it needs to write, retry ONCE with "
            "`sandbox_permissions='workspace-write'` and a one-sentence "
            "`justification`. Do not attempt destructive, system-wide, or "
            "network-exfiltration commands."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command line to run (via the platform shell).",
                },
                "description": {
                    "type": "string",
                    "description": "One-line, active-voice summary (5-10 words), for display only.",
                },
                "workdir": {
                    "type": "string",
                    "description": (
                        "Working directory for this call, relative to (or inside) "
                        "the sandbox workspace root. Defaults to the workspace root."
                    ),
                },
                "timeout_ms": {
                    "type": "integer",
                    "description": "Timeout override in milliseconds (capped by the executor).",
                },
                "sandbox_permissions": {
                    "type": "string",
                    "enum": ["workspace-write", "danger-full-access"],
                    "description": (
                        "Request a WIDER mode than the standing default when a "
                        "command was denied. Requires `justification`."
                    ),
                },
                "justification": {
                    "type": "string",
                    "description": (
                        "One sentence explaining why this exact command needs the "
                        "wider access. Required with `sandbox_permissions`."
                    ),
                },
            },
            "required": ["command"],
        },
        "handler": builtins.run_command,
    },
}

def _shell_gate() -> bool:
    from app.agent.tools.shell_config import resolve_shell

    return resolve_shell().enabled


# Tools that are only advertised / executable when a config flag enables them.
_GATED_TOOLS: dict[str, Callable[[], bool]] = {
    "run_command": _shell_gate,
}


def _tool_available(name: str) -> bool:
    gate = _GATED_TOOLS.get(name)
    return gate() if gate is not None else True


async def openai_tool_schemas(
    *,
    session: AsyncSession | None = None,
    user_id: str | None = None,
    allowed: set[str] | frozenset[str] | None = None,
    include_packs: bool = True,
) -> list[dict[str, Any]]:
    """Schemas passed to chat_complete(tools=...).

    Always includes builtins. When session+user_id are provided, also merges
    enabled nous-pack/2 tools (namespaced ``pack__…``).
    """
    schemas = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": meta["description"],
                "parameters": meta["parameters"],
            },
        }
        for name, meta in _TOOLS.items()
        if (allowed is None or name in allowed) and _tool_available(name)
    ]
    if include_packs and session is not None and user_id and allowed is None:
        from app.services.pack_service import PackService

        pack_schemas = await PackService(session).list_enabled_tool_schemas(
            user_id=user_id
        )
        # Pack tools never shadow builtins (different namespace).
        schemas.extend(pack_schemas)
    return schemas


def list_tool_catalog() -> list[dict[str, Any]]:
    """Human-readable catalog for the UI / API (builtins only)."""
    return [
        {
            "name": name,
            "description": meta["description"],
            "parameters": meta["parameters"],
        }
        for name, meta in _TOOLS.items()
        if _tool_available(name)
    ]


async def execute_tool(
    name: str,
    arguments: dict[str, Any] | str | None,
    *,
    session: AsyncSession | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Run a tool by name. Always returns a JSON-serialisable dict."""
    from app.skill.pack_names import is_pack_tool_name

    if is_pack_tool_name(name):
        if session is None or not user_id:
            return {"ok": False, "error": "Pack tools require an authenticated session."}
        from app.services.pack_service import PackService
        from app.skill.pack_runner import execute_pack_tool

        svc = PackService(session)
        resolved = await svc.resolve_tool(user_id=user_id, exposed_name=name)
        if resolved is None:
            return {"ok": False, "error": f"Unknown pack tool '{name}'."}
        pack, tool = resolved
        args: dict[str, Any]
        if arguments is None:
            args = {}
        elif isinstance(arguments, str):
            try:
                args = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as exc:
                return {"ok": False, "error": f"Invalid JSON arguments: {exc}"}
        else:
            args = arguments
        return await execute_pack_tool(pack=pack, tool=tool, arguments=args)

    meta = _TOOLS.get(name)
    if meta is None:
        return {"ok": False, "error": f"Unknown tool '{name}'."}

    args: dict[str, Any]
    if arguments is None:
        args = {}
    elif isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Invalid JSON arguments: {exc}"}
    else:
        args = arguments

    handler: ToolHandler = meta["handler"]
    try:
        result = await handler(**args)
        if not isinstance(result, dict):
            return {"ok": True, "result": result}
        if "ok" not in result:
            result = {"ok": True, **result}
        return result
    except TypeError as exc:
        logger.warning("tool_bad_args", tool=name, error=str(exc))
        return {"ok": False, "error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 - surface to model
        logger.exception("tool_failed", tool=name)
        return {"ok": False, "error": str(exc)}
