"""Tool contracts for the plan / author / review / repair material workflow."""

from __future__ import annotations

from typing import Any
import hashlib
import json
from pathlib import Path

from app.agent.tools import material_workflow as workflow

_TEXT = {"type": "string"}
_STRINGS = {"type": "array", "items": _TEXT}
_REFERENCES = {"type": "array", "items": {"type": "object", "properties": {"title": _TEXT, "url": _TEXT}, "required": ["title", "url"]}}
_TABLE_ROWS = {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": "Complete rows, each with the same number of cells as columns. Do not silently omit rows."}


async def _review(*, files: list[str], expected_slide_count: int | None = None,
                  required_sections: list[str] | None = None, visual: bool = True,
                  plan_id: str | None = None) -> dict[str, Any]:
    from app.agent.tools.material_review import review_materials

    plan = workflow.load_material_plan(plan_id) if plan_id else {}
    planned = next((item.get("total_slides") for item in plan.get("deliverables", []) if item.get("kind") == "pptx"), None)
    if expected_slide_count is not None and planned is not None and expected_slide_count != planned:
        raise ValueError("Review slide count conflicts with the saved material plan.")
    planned_sections = list(dict.fromkeys(str(item["heading"]) for item in plan.get("outline", []) if item.get("heading")))
    required = list(dict.fromkeys(required_sections or []))
    result = await review_materials(files=files, expected_slide_count=planned or expected_slide_count,
                                    required_sections=required or None, visual=visual)
    result["plan_id"] = plan_id
    if plan:
        result["plan_sha256"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        result["planned_sections"] = planned_sections
        result["plan_acceptance_criteria"] = plan.get("acceptance_criteria") or []
        if result.get("path") and result.get("ok"):
            Path(result["path"]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def install_material_tools(tools: dict[str, dict[str, Any]]) -> None:
    """Extend old authoring tools so existing conversations remain compatible."""
    ppt = tools["create_presentation"]
    ppt["description"] += (
        " For rich training/briefing materials call plan_materials first. "
        "Supports editable table and embedded figure layouts, cover images, and real speaker notes. "
        "Pass expected_slide_count for an exact total including cover/closing. "
        "Call review_materials after exporting and repair any reported errors."
    )
    ppt_props = ppt["parameters"]["properties"]
    ppt_props.update({
        "draft_id": {**_TEXT, "description": "Export a saved pptx draft from write_material_draft instead of resending slides."},
        "expected_slide_count": {"type": "integer", "minimum": 1, "maximum": 60, "description": "Exact total, including cover and closing. Provide exactly this many slides; no automatic insertions."},
        "plan_id": {**_TEXT, "description": "ID returned by plan_materials. Enforces its slide count."},
        "cover_image": {**_TEXT, "description": "Existing local /api/v1/files/exports or uploads image URL, e.g. the result of generate_image. No remote URL."},
    })
    ppt["parameters"]["required"] = ["title"]
    ppt["description"] += " For long materials write small batches with write_material_draft, then export with title + draft_id (omit slides)."
    ppt["description"] = ppt["description"].replace("ALWAYS pass title AND slides together in a single call (never title-only).", "Pass title with either slides or an existing draft_id.")
    slide = ppt_props["slides"]["items"]["properties"]
    slide["layout"]["description"] = "title|section|bullets|two_column|cards|code|table|figure|quote|closing"
    slide.update({
        "columns": _STRINGS, "rows": _TABLE_ROWS,
        "image": {**_TEXT, "description": "Local generated/uploaded image URL for title or figure. Must actually exist."},
        "caption": _TEXT,
        "speaker_notes": {**_TEXT, "description": "Presenter narration, discussion prompts, timing, and technical caveats. Stored in real PowerPoint notes."},
        "references": _REFERENCES,
    })
    slide["cards"]["maxItems"] = 4
    for field in ("bullets", "explain", "left_bullets", "right_bullets"):
        slide[field]["maxItems"] = 10

    pdf = tools["create_pdf"]
    pdf["description"] += (
        " For self-study materials use purposeful sections and rich blocks rather than copying slide bullets. "
        "Include complete runnable code, expected observations, worked reasoning, exercises with answers and references. "
        "Long code may span pages. Call review_materials on the final file."
    )
    pdf_props = pdf["parameters"]["properties"]
    pdf_props.update({"plan_id": _TEXT, "audience": _TEXT, "objectives": _STRINGS,
                      "references": _REFERENCES, "cover_image": _TEXT,
                      "draft_id": {**_TEXT, "description": "Export a saved pdf draft instead of resending sections."}})
    pdf["parameters"]["required"] = ["title"]
    pdf["description"] += " For long handouts write chapters in small batches with write_material_draft, then export using title + draft_id (omit sections)."
    pdf["description"] = pdf["description"].replace("ALWAYS pass title AND sections together.", "Pass title with either sections or an existing draft_id.")
    section = pdf_props["sections"]["items"]["properties"]
    section.update({
        "page_break_before": {"type": "boolean", "description": "Start this chapter on a fresh page when useful; do not pad the document with empty pages."},
        "blocks": {"type": "array", "description": "Ordered rich content blocks, rendered in exactly this order.", "items": {
            "type": "object", "properties": {
                "type": {"type": "string", "enum": ["paragraph", "code", "table", "image", "callout", "exercise"]},
                "text": _TEXT, "title": _TEXT, "code": _TEXT, "language": _TEXT,
                "caption": _TEXT, "columns": _STRINGS, "rows": _TABLE_ROWS,
                "image": _TEXT, "question": _TEXT, "answer": _TEXT,
            }, "required": ["type"],
        }},
    })
    tools.update({
        "read_material_draft": {
            "description": "Recover a bounded range of saved draft items after an interruption or when revising materials. Uses the draft_id/kind restored from this conversation. Returns real saved content, without executing it or resending the whole document.",
            "parameters": {"type": "object", "properties": {
                "draft_id": _TEXT, "kind": {"type": "string", "enum": ["pptx", "pdf", "sources"]},
                "start": {"type": "integer", "minimum": 0}, "count": {"type": "integer", "minimum": 1, "maximum": 8},
            }, "required": ["draft_id", "kind"]}, "handler": workflow.read_material_draft,
        },
        "write_material_draft": {
            "description": "Write a small batch of material content to a durable draft, then append more batches with the returned draft_id. Prefer 2-4 slides, 1-3 detailed PDF chapters, or 1-2 source files per call to avoid oversized responses/timeouts. pptx items use the create_presentation slide fields; pdf items use create_pdf section fields; sources items use filename/content. After all batches export via create_presentation/create_pdf/create_code_files with draft_id. Do not resend all previous content.",
            "parameters": {"type": "object", "properties": {
                "plan_id": _TEXT, "kind": {"type": "string", "enum": ["pptx", "pdf", "sources"]},
                "draft_id": _TEXT, "items": {"type": "array", "minItems": 1, "maxItems": 8,
                    "items": {"type": "object", "properties": {**slide, **section, "filename": _TEXT, "content": _TEXT}}},
            }, "required": ["plan_id", "kind", "items"]}, "handler": workflow.write_material_draft,
        },
        "plan_materials": {
            "description": "Plan rich PPT/PDF materials BEFORE authoring. Record the audience, learning goals, each deliverable's purpose and a specific outline. For a requested N-slide deck supply exactly N pptx outline entries including cover/closing. This saves a reusable plan, not the deliverable.",
            "parameters": {"type": "object", "properties": {
                "title": _TEXT, "audience": _TEXT, "objectives": _STRINGS,
                "deliverables": {"type": "array", "items": {"type": "object", "properties": {
                    "kind": {"type": "string", "enum": ["pptx", "pdf"]}, "purpose": _TEXT,
                    "total_slides": {"type": "integer", "minimum": 1, "maximum": 60},
                }, "required": ["kind", "purpose"]}},
                "outline": {"type": "array", "items": {"type": "object", "properties": {
                    "kind": {"type": "string", "enum": ["pptx", "pdf"]}, "heading": _TEXT, "purpose": _TEXT,
                }, "required": ["kind", "heading", "purpose"]}},
                "acceptance_criteria": _STRINGS, "references": _REFERENCES,
            }, "required": ["title", "audience", "objectives", "deliverables", "outline"]},
            "handler": workflow.plan_materials,
        },
        "review_materials": {
            "description": "Read and render the ACTUAL final PPTX/PDF files, inspect every page, and ask the configured materials review model for visual/content feedback. Use after all exports and again after repairs. Returns file hashes, preview URLs, issues and honest check scope. Missing LibreOffice/vision capability means partial, never visually passed. Include BOTH files for a multi-format request.",
            "parameters": {"type": "object", "properties": {
                "files": {**_STRINGS, "description": "1-4 final local export/upload URLs. Review the newest versions, never intermediate files."},
                "expected_slide_count": {"type": "integer", "minimum": 1, "maximum": 60},
                "required_sections": {**_STRINGS, "description": "Optional literal short text snippets to verify, e.g. UnsafeCounter, 练习, 答案. Do not use descriptive outline titles, decorative labels like 封面, or combine alternatives in one string. Plan headings may be reworded."}, "visual": {"type": "boolean", "default": True}, "plan_id": _TEXT,
            }, "required": ["files"]}, "handler": _review,
        },
        "create_code_files": {
            "description": "Deliver complete source files and README with original compilable filenames in a ZIP. Returns an isolated workspace for verify_code_examples. Does NOT execute code. Use for programming materials so readers can reproduce all examples without copying slide snippets.",
            "parameters": {"type": "object", "properties": {"title": _TEXT, "draft_id": _TEXT, "plan_id": _TEXT, "files": {"type": "array", "items": {
                "type": "object", "properties": {"filename": _TEXT, "content": _TEXT}, "required": ["filename", "content"],
            }}}, "required": ["title"]}, "handler": workflow.create_code_files,
        },
        "verify_code_examples": {
            "description": "Actually compile/run examples from create_code_files using the existing command-execution sandbox. Only available when the operator enables command execution. Stops at the first failure and returns actual outputs and a downloadable verification log. Use separate compile and run commands, not claims of execution.",
            "parameters": {"type": "object", "properties": {"workspace": _TEXT, "commands": _STRINGS}, "required": ["workspace", "commands"]},
            "handler": workflow.verify_code_examples,
        },
        "package_materials": {
            "description": "Package explicit final PPT/PDF/source ZIP/log files into one downloadable training kit. Include a useful README with reading order and running instructions. Does not replace content, code or visual review.",
            "parameters": {"type": "object", "properties": {"title": _TEXT, "files": _STRINGS, "readme": _TEXT}, "required": ["title", "files"]},
            "handler": workflow.package_materials,
        },
    })
