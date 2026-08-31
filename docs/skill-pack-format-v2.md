# Nous Skill Pack Format v2 (L2)

> Status: **Implemented (v2.0 runtime)** — see also `docs/examples/nous-image-gen/`.  
> Goal: let users import “strong skills” that ship **instructions + optional scripts/assets**, without breaking today’s L1 JSON playbook import.

## Frozen product decisions (v2.0)

| Topic | Decision | Rationale |
| --- | --- | --- |
| Tool names | **Always** `pack__{sanitized_pack_id}__{tool}` | MCP-style namespacing; no collisions with builtins |
| Runners | **Python only** — `shell` rejected at parse time | Least privilege; shell deferred |
| Invocation | **Auto-run after install grant** + structlog `pack_tool_audit` | Modern skill-install UX; no per-call modal in v2.0 |
| Tool visibility | All **enabled** pack tools for the user are merged into every turn | Reliable capability (not only when playbook retrieves) |
| L1 JSON | Unchanged (`POST /skills/import`) | Backward compatible |

API surface:

- `POST /api/v1/pack-archives/preview`
- `POST /api/v1/pack-archives`
- `GET/PATCH/DELETE /api/v1/pack-archives[/{id}]`

---

## 1. Why L2

| Today (L1) | Problem | L2 |
| --- | --- | --- |
| Skill = text playbook (`instruction` / `workflow` / `tools: string[]`) | External skills that bind scripts lose their executable half | Pack = playbook **+** local tools backed by scripts |
| Import = built-in `pack_id` or inline JSON | No assets, no versioned package, no permissions | Import = `.zip` / `.nouspack` with manifest + files |
| Tools are global builtins only | Can’t teach the agent a new capability without shipping backend code | Pack-local tools register at import time (gated by permissions) |

**Non-goals for v2.0**

- Arbitrary native binaries / unsigned remote code auto-run
- Full npm/pip dependency installation from the pack
- Replacing auto-extracted “memory skills” (those stay text-only)

---

## 2. Package shapes

Nous accepts three equivalent layouts. Importer normalizes all of them into the same internal model.

### 2.1 Multi-skill pack (recommended)

```text
my-pack.zip
├── pack.json                 # required
├── README.md                 # optional (human docs; not injected)
├── skills/
│   └── image-gen/
│       ├── SKILL.md          # required per skill
│       ├── examples.json     # optional
│       ├── assets/           # optional static files (templates, icons, …)
│       │   └── style-ref.png
│       └── tools/
│           ├── generate_image.tool.json
│           └── scripts/
│               └── generate_image.py
└── shared/                   # optional, shared across skills in this pack
    └── lib/
        └── io_utils.py
```

### 2.2 Single-skill zip (Cursor-style)

If the zip root contains `SKILL.md` (and no `pack.json`), importer synthesizes a one-skill pack:

```text
image-gen.zip
├── SKILL.md
├── scripts/                  # optional (see §5.2 shorthand)
│   └── generate_image.py
└── assets/
```

### 2.3 L1 JSON (unchanged)

```http
POST /api/v1/skills/import
{ "pack_id": "nous-pptx" } | { "skills": [ … ] }
```

L1 remains the fast path for text-only playbooks. L2 is additive.

---

## 3. `pack.json` (manifest)

```json
{
  "format": "nous-pack/2",
  "id": "example.image-gen",
  "name": "文生图",
  "version": "1.0.0",
  "description": "Prompt 工程 + 本地 generate_image 工具。",
  "author": "example",
  "license": "MIT",
  "min_nous": "0.2.0",
  "tags": ["image", "creative"],
  "permissions": [
    "script.python",
    "network",
    "fs.write.exports"
  ],
  "skills": [
    "skills/image-gen"
  ],
  "shared": {
    "pythonpath": ["shared/lib"]
  }
}
```

### Field rules

| Field | Required | Rules |
| --- | --- | --- |
| `format` | yes | Must be `"nous-pack/2"` |
| `id` | yes | Reverse-DNS or kebab; `[a-z0-9][a-z0-9._-]*`; unique per user with `version` |
| `name` | yes | Display name ≤ 200 chars |
| `version` | yes | SemVer (`1.0.0`) |
| `skills` | yes | Non-empty list of relative dirs, each containing `SKILL.md` |
| `permissions` | no | Declared capabilities; empty = text-only pack (no local tools run) |
| `min_nous` | no | SemVer floor; reject import if host older |
| `shared.pythonpath` | no | Extra dirs appended for Python runners only |

### Permissions vocabulary (v2.0)

| Permission | Allows |
| --- | --- |
| `script.python` | Run pack-local Python tools |
| `script.shell` | Run pack-local shell tools (**default off in UI; warn loudly**) |
| `network` | Tool subprocess may open outbound HTTP(S) |
| `fs.read.pack` | Read files under the installed pack dir (always implied for runners) |
| `fs.write.exports` | Write under `./data/exports` (same as `create_presentation`) |
| `fs.write.workdir` | Write under a per-invocation temp dir only |
| `env.*` | Explicit env var names the script may read, e.g. `env.OPENAI_API_KEY` |

Importer **must** surface the permission set in a preview step. Activate only after user confirm (or `activate=false` → draft + tools disabled until approved).

---

## 4. `SKILL.md`

Frontmatter (YAML) + Markdown body. Body → `Skill.instruction`.

```markdown
---
name: 文生图助手
description: 把用户描述转成可下载图片，强调构图与风格约束。
trigger_keywords:
  - 画一张
  - 文生图
  - generate image
  - 出图
trigger_intent: 根据文字描述生成图片文件
tools:
  - builtin: web_search          # optional reference to host tools
  - local: generate_image        # pack-local tool name
workflow:
  - step: 1
    action: 澄清主体、风格、画幅、禁忌内容
  - step: 2
    action: 调用 generate_image
    expect: 返回 download_url
  - step: 3
    action: 把下载链接交给用户，并简述构图选择
confidence: 0.95
---

接到文生图请求时：
1. 先把模糊描述改写成具体英文/中文 prompt（主体、镜头、光线、风格、负面约束）。
2. 必须调用 `generate_image`，不要假装已经生成。
3. 成功后原样给出 `download_url`。
```

### Mapping → existing Skill columns

| Frontmatter / file | DB / runtime |
| --- | --- |
| `name`, `description` | `skills.name/description` |
| Markdown body | `skills.instruction` |
| `trigger_*` | same |
| `workflow` | `skills.workflow` JSON |
| `tools[].builtin` | string names in `skills.tools` (host catalog) |
| `tools[].local` | stored as `pack:<pack_id>:<tool_name>` **and** rows in `skill_pack_tools` |
| `examples.json` | `skills.examples` |
| `confidence` | `skills.confidence` |
| pack id + version | new columns / join table (see §7) |

`examples.json` shape (same as today):

```json
[
  {
    "question": "画一张赛博朋克雨夜街道",
    "solution": "先补全镜头与色调，再调用 generate_image。"
  }
]
```

---

## 5. Local tools

### 5.1 Tool descriptor (`*.tool.json`)

Path: `skills/<skill>/tools/<name>.tool.json`

```json
{
  "name": "generate_image",
  "description": "Generate an image from a text prompt and save it under exports.",
  "parameters": {
    "type": "object",
    "properties": {
      "prompt": { "type": "string", "description": "Full image prompt." },
      "size": {
        "type": "string",
        "enum": ["1024x1024", "1024x1792", "1792x1024"],
        "default": "1024x1024"
      },
      "filename_hint": { "type": "string" }
    },
    "required": ["prompt"]
  },
  "runner": {
    "kind": "python",
    "entry": "scripts/generate_image.py",
    "timeout_sec": 90,
    "memory_mb": 512,
    "network": true,
    "env_allow": ["OPENAI_API_KEY", "IMAGE_API_BASE", "IMAGE_API_KEY"],
    "pythonpath": ["../../shared/lib"]
  }
}
```

Rules:

- `name` must match `[a-z][a-z0-9_]{1,63}` and be unique within the pack.
- `parameters` is OpenAI function-calling JSON Schema (same as builtins).
- `runner.entry` is relative to the **skill directory**, must stay inside the pack (no `..` escape after resolve).
- `runner.kind`: v2.0 supports `python`; `shell` requires `script.shell` permission and is off by default in UI.

### 5.2 Cursor-style shorthand

If `scripts/<name>.py` exists **without** a `.tool.json`, importer may auto-wrap:

```json
{
  "name": "<name>",
  "description": "Pack script <name>.py",
  "parameters": {
    "type": "object",
    "properties": {
      "input": { "type": "string", "description": "Free-form input for the script." }
    },
    "required": ["input"]
  },
  "runner": { "kind": "python", "entry": "scripts/<name>.py", "timeout_sec": 60 }
}
```

Prefer explicit `.tool.json` for production packs.

### 5.3 Script I/O protocol

Runner invokes:

```text
stdin  → JSON object = tool arguments (+ reserved keys)
stdout → JSON object result
stderr → logs (captured, truncated, returned on failure)
```

**Reserved stdin envelope** (host injects; scripts should tolerate unknown keys):

```json
{
  "prompt": "…",
  "_nous": {
    "pack_id": "example.image-gen",
    "pack_version": "1.0.0",
    "skill_id": "<uuid>",
    "tool_name": "generate_image",
    "pack_dir": "/abs/path/to/installed/pack",
    "skill_dir": "/abs/path/to/skill",
    "exports_dir": "/abs/path/to/data/exports",
    "workdir": "/abs/path/to/tmp/invocation",
    "request_id": "…"
  }
}
```

**Stdout success (convention aligned with builtins):**

```json
{
  "ok": true,
  "download_url": "/api/v1/files/exports/rain_street_ab12cd.png",
  "filename": "rain_street_ab12cd.png",
  "message": "Image generated."
}
```

**Stdout failure:**

```json
{ "ok": false, "error": "IMAGE_API_KEY missing" }
```

Non-JSON stdout → host wraps as `{ "ok": false, "error": "invalid tool stdout", "raw": "…" }`.

### 5.4 Execution sandbox (v2.0 minimum)

| Control | Policy |
| --- | --- |
| CWD | `skill_dir` |
| Path escape | Reject resolved paths outside pack / exports / workdir |
| Timeout | `runner.timeout_sec` (cap e.g. 120s) |
| Network | Denied unless pack `permissions` contains `network` **and** `runner.network` |
| Env | Only `env_allow` ∪ safe host defaults (`PATH`, `LANG`, `PYTHONPATH` trimmed) |
| Writes | `exports_dir` and/or `workdir` only |
| Interpreter | Host-managed Python (same major as backend), **not** pack-bundled python |
| Concurrency | Per-user semaphore (e.g. 2) |
| Audit | Log pack_id, tool, duration, exit code, byte sizes |

No `pip install` from pack at runtime in v2.0. If a script needs deps, document them; host may later add an allowlisted `requirements.pack.txt` install step (v2.1).

---

## 6. Import / runtime flow

```text
upload zip
   → unpack to quarantine temp
   → validate pack.json + SKILL.md + path safety + zip-bomb limits
   → build ImportPreview { skills, tools, permissions, warnings }
   → user confirms
   → copy to durable store
   → upsert Skill rows (source=imported)
   → register pack-local tools in skill_pack_tools
   → index embeddings
   → (optional) activate
```

### Chat-time binding

When `retrieve_skills` returns skills that belong to packs:

1. Load their **approved** local tool schemas.
2. Union with (or subset of) global builtins — see L1 follow-up: honor `tools[]`.
3. Pass schemas into `llm_call`.
4. On tool call `pack:<id>:<name>` or namespaced name → `execute_pack_tool`.

Prompt injection should mention **local tool names** (today `tools` is omitted from `to_prompt_dict` — fix as part of L2 or L1).

### Uninstall / upgrade

- Upgrade same `id` with higher SemVer: replace files, bump skill versions, reindex; keep skill UUID if `name` matches (configurable).
- Delete pack: remove files + disable/delete skills + drop tool registrations.

---

## 7. Persistence

### Filesystem

```text
data/skill_packs/
  {user_id}/
    {pack_id}/
      {version}/          # immutable extract
        pack.json
        skills/…
      current -> {version}  # or DB pointer only
```

Zip bomb / size limits (suggested defaults):

- Archive ≤ 20 MiB compressed / ≤ 80 MiB uncompressed
- ≤ 200 files; no symlinks; no absolute paths

### Database (additive)

**`skill_packs`**

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid | |
| user_id | fk | |
| pack_id | str | manifest `id` |
| version | str | |
| name, description | | |
| permissions | JSON | granted set |
| install_path | str | relative under data/ |
| status | enum | `pending_review` / `active` / `disabled` |
| content_hash | str | sha256 of zip |
| created_at / updated_at | | |

**`skill_pack_tools`**

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid | |
| pack_row_id | fk | |
| skill_id | fk | nullable until skill created |
| name | str | local tool name |
| description | text | |
| parameters | JSON | |
| runner | JSON | kind/entry/timeout/… |
| enabled | bool | false until permissions approved |

**`skills` additive columns**

- `pack_row_id` nullable FK  
- `pack_skill_key` optional stable key inside pack (`image-gen`) for upgrades  

`skills.source` stays `imported`.

---

## 8. API (proposed)

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/pack-archives/preview` | multipart zip → validation + preview JSON (no persist) |
| `POST` | `/api/v1/pack-archives` | multipart zip + `grant_permissions` + `activate` |
| `GET` | `/api/v1/pack-archives` | list installed L2 packs |
| `GET` | `/api/v1/pack-archives/{id}` | detail + tools |
| `DELETE` | `/api/v1/pack-archives/{id}` | uninstall |
| `PATCH` | `/api/v1/pack-archives/{id}` | enable/disable |

Keep existing:

- `GET /skills/packs`, `POST /skills/import` → L1

### Preview response (sketch)

```json
{
  "format": "nous-pack/2",
  "pack_id": "example.image-gen",
  "version": "1.0.0",
  "name": "文生图",
  "permissions_requested": ["script.python", "network", "fs.write.exports"],
  "skills": [
    {
      "key": "image-gen",
      "name": "文生图助手",
      "tools_local": ["generate_image"],
      "tools_builtin": ["web_search"]
    }
  ],
  "warnings": [
    "script.shell not requested",
    "Tool generate_image requires network"
  ],
  "errors": []
}
```

If `errors` non-empty → import rejected.

---

## 9. Compatibility & migration

| Source | Behavior |
| --- | --- |
| Built-in L1 packs in `packs.py` | Unchanged; optional later ship as zip under `backend/skill_packs/` |
| Inline JSON import | Unchanged |
| Cursor single-skill folder zipped | Accepted via §2.2 |
| Pack with only `SKILL.md` (no tools) | Valid L2 text pack; permissions may be empty |
| Name collision with existing skill | Same as L1: `skip_duplicates` or rename policy |

---

## 10. Security checklist (must ship with importer)

1. Zip slip: normalize paths; reject `..` / absolute / symlink entries.  
2. Size & file-count caps.  
3. Permission preview + explicit grant (no silent network).  
4. Script path confinement + timeout + output size cap (e.g. 1 MiB stdout).  
5. Tool names cannot shadow builtins unless pack opts in with `override_builtin: true` (default false → rename or error).  
6. Disable pack tools instantly on pack `disabled`.  
7. Never execute tools for `draft` / `pending_review` packs.  
8. Redact secrets in tool logs.

---

## 11. Example: minimal text-to-image pack

```text
nous-image-gen.zip
├── pack.json
└── skills/
    └── image-gen/
        ├── SKILL.md
        └── tools/
            ├── generate_image.tool.json
            └── scripts/
                └── generate_image.py
```

`pack.json`:

```json
{
  "format": "nous-pack/2",
  "id": "nous.image-gen",
  "name": "文生图",
  "version": "0.1.0",
  "description": "文生图 playbook + generate_image 工具",
  "permissions": ["script.python", "network", "fs.write.exports", "env.OPENAI_API_KEY"],
  "skills": ["skills/image-gen"]
}
```

This pack is the first reference implementation once coding starts.

---

## 12. Implementation phases

| Phase | Deliverable |
| --- | --- |
| **P0 — Spec freeze** | This document + sample zip in `docs/examples/nous-image-gen/` (no runner yet) |
| **P1 — Import plumbing** | Preview/import APIs, filesystem layout, DB tables, SKILL.md parser; tools stored but **not executed** |
| **P2 — Runner** | Python stdin/stdout executor + sandbox + chat-time schema merge |
| **P3 — UI** | Skills page: upload zip, permission checklist, installed packs manager |
| **P4 — Reference pack** | Real `nous.image-gen` calling an images API; frontend image preview for export URLs |

Suggested order after design sign-off: **P1 → P2 → P4 (image) → P3 polish**.

---

## 13. Decisions (frozen for v2.0)

1. **Tool naming**: always `pack__{sanitized_pack_id}__{tool_name}` (no bare names).  
2. **Shell**: not supported in v2.0; parse rejects `runner.kind=shell`.  
3. **Invocation**: install-time permission grant → auto-run + `pack_tool_audit` logs.  
4. **Visibility**: all enabled pack tools for the user are merged into every chat turn.
