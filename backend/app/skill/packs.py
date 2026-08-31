"""Built-in skill packs + import helpers (Claude / WorkBuddy style playbooks)."""

from __future__ import annotations

from typing import Any

# Packs mimic popular agent skill libraries: research, ops, writing, presentation.
BUILTIN_PACKS: list[dict[str, Any]] = [
    {
        "id": "nous-research",
        "name": "深度调研",
        "description": "网页检索 → 精读来源 → 结构化结论，适合竞品/技术/市场调研。",
        "tags": ["research", "web", "analysis"],
        "skills": [
            {
                "name": "网页调研工作流",
                "description": "用搜索与抓取完成有引用的调研报告。",
                "instruction": (
                    "接到调研任务时：1) 用 web_search 找 5+ 候选来源；"
                    "若结果为空或明显不相关，立刻换英文关键词 / 加 github / 加官方产品名再搜；"
                    "2) 对最相关 2–3 个 URL 用 fetch_url 精读；"
                    "3) 交叉验证后输出：结论 / 证据 / 不确定性 / 来源链接。"
                    "禁止编造未检索到的事实；禁止在搜索失败时假装项目不存在。"
                ),
                "trigger_keywords": ["调研", "搜索", "查一下", "research", "竞品", "最新"],
                "trigger_intent": "需要联网调研并给出有来源的结论",
                "workflow": [
                    {"step": 1, "action": "澄清调研问题与范围"},
                    {"step": 2, "action": "web_search 收集候选来源"},
                    {"step": 3, "action": "fetch_url 精读关键页面"},
                    {"step": 4, "action": "汇总结论并附上来源"},
                ],
                "tools": ["web_search", "fetch_url"],
                "examples": [
                    {
                        "question": "帮我调研一下 LangGraph 最近有什么重要更新",
                        "solution": "先搜索官方 changelog 与 release notes，再抓取页面提炼要点。",
                    }
                ],
            }
        ],
    },
    {
        "id": "nous-weather-travel",
        "name": "出行天气",
        "description": "查询天气并给出穿衣/出行建议。",
        "tags": ["weather", "daily"],
        "skills": [
            {
                "name": "出行天气顾问",
                "description": "查询指定城市天气并给出实用建议。",
                "instruction": (
                    "用户问天气时必须调用 get_weather。"
                    "回答包含：当前气温、体感、天气概况、未来 1–3 天要点，以及穿衣/是否带伞建议。"
                ),
                "trigger_keywords": ["天气", "气温", "下雨", "weather", "穿什么"],
                "trigger_intent": "查询天气并获得出行建议",
                "workflow": [
                    {"step": 1, "action": "确认城市/地点"},
                    {"step": 2, "action": "调用 get_weather"},
                    {"step": 3, "action": "给出穿衣与出行建议"},
                ],
                "tools": ["get_weather"],
            }
        ],
    },
    {
        "id": "nous-pptx",
        "name": "演示文稿",
        "description": "把主题快速做成可下载的 PPTX。",
        "tags": ["ppt", "presentation", "office"],
        "skills": [
            {
                "name": "一键生成 PPT",
                "description": "根据主题大纲调用 create_presentation 产出 .pptx。",
                "instruction": (
                    "仅在用户明确要 PPT/幻灯片时使用。"
                    "若用户要网页、demo、H5、在线演示、给领导看的汇报页，改用 create_webpage。"
                    "做 PPT 时按「设计稿」而不是纯大纲："
                    "1) 先确认主题、受众、页数；"
                    "2) 规划版式节奏：封面 title → 分节 section → "
                    "正文混用 bullets / two_column / cards（KPI）/ quote → 结尾 closing；"
                    "3) 默认 theme=nous（也可 slate/ink/dawn）；"
                    "4) 每页最多 3–5 条短句；代码页必须用 layout=code + multiline code 保留缩进；"
                    "5) 调用时必须同时传 title 与 slides，禁止只传 title；"
                    "6) 用 markdown 相对链接返回 download_url，禁止 http://127.0.0.1:5173。"
                    "不要只做全是 bullets 的白底幻灯片。"
                ),
                "trigger_keywords": ["PPT", "ppt", "幻灯片", "演示文稿", "pptx", "做个片子"],
                "trigger_intent": "生成演示文稿文件",
                "workflow": [
                    {"step": 1, "action": "明确主题、受众、语气与页数"},
                    {"step": 2, "action": "设计版式节奏（封面/分节/双栏/KPI/结尾）"},
                    {"step": 3, "action": "create_presentation（选 theme + layout）"},
                    {"step": 4, "action": "返回下载链接并简述设计选择"},
                ],
                "tools": ["create_presentation", "web_search"],
            }
        ],
    },
    {
        "id": "nous-pdf",
        "name": "PDF 讲义",
        "description": "把主题做成可下载的 PDF 教程/讲义（不是 PPT）。",
        "tags": ["pdf", "tutorial", "document"],
        "skills": [
            {
                "name": "一键生成 PDF",
                "description": "根据主题大纲调用 create_pdf 产出 .pdf。",
                "instruction": (
                    "用户要 PDF、讲义、学习资料、教程文档时必须调用 create_pdf，"
                    "禁止改用 create_presentation。"
                    "1) 确认主题与读者；"
                    "2) 按章节组织 sections：heading + body/bullets，代码用 code+language；"
                    "3) 一次同时传 title 与 sections；"
                    "4) 用 markdown 相对链接返回 download_url。"
                ),
                "trigger_keywords": [
                    "PDF",
                    "pdf",
                    "讲义",
                    "学习资料",
                    "教程文档",
                    "生成pdf",
                ],
                "trigger_intent": "生成 PDF 学习文档",
                "workflow": [
                    {"step": 1, "action": "明确主题、受众与章节"},
                    {"step": 2, "action": "组织 sections（含代码示例）"},
                    {"step": 3, "action": "create_pdf（title + sections）"},
                    {"step": 4, "action": "返回下载链接"},
                ],
                "tools": ["create_pdf"],
            }
        ],
    },
    {
        "id": "nous-webpage",
        "name": "网页汇报 Demo",
        "description": "把工作材料做成可投屏的 HTML 汇报页（不是 PPT）。",
        "tags": ["webpage", "demo", "briefing", "html"],
        "skills": [
            {
                "name": "一键生成汇报网页",
                "description": "根据主题或附件调用 create_webpage 产出可全屏翻页的 HTML。",
                "instruction": (
                    "用户要网页、demo、H5、在线演示、汇报页、给领导看，且没点名 PPT 时，"
                    "必须调用 create_webpage，禁止改用 create_presentation。"
                    "1) 从用户附件/描述提炼事实，结论先行，不编造数据；"
                    "2) 按投屏节奏组织 7–10 屏：hero → kpis → 重点页"
                    "（narrative/split/timeline/cards/architecture/figure）→ closing；"
                    "若附件含论文图（PAPER FIGURES），至少做 1–3 页 layout=figure，"
                    "image 必须用抽出的 /api/v1/files/uploads/... 地址，禁止 generate_image 造图；"
                    "3) closing 必须给 talking_points（汇报时口头强调的 3 句）；"
                    "4) 一次同时传 title 与 sections；"
                    "5) 回复用 [打开汇报网页](download_url)，并提醒方向键翻页、F 全屏。"
                ),
                "trigger_keywords": [
                    "网页",
                    "demo",
                    "Demo",
                    "H5",
                    "汇报",
                    "领导",
                    "在线演示",
                    "汇报页",
                    "briefing",
                    "landing",
                ],
                "trigger_intent": "生成给领导看的网页 Demo",
                "workflow": [
                    {"step": 1, "action": "从附件/需求提炼结论、指标、架构与下一步"},
                    {"step": 2, "action": "设计投屏节奏（封面/KPI/重点/收束）"},
                    {"step": 3, "action": "create_webpage（title + sections）"},
                    {"step": 4, "action": "返回打开链接并说明翻页/全屏操作"},
                ],
                "tools": ["create_webpage"],
            }
        ],
    },
    {
        "id": "nous-ops",
        "name": "工程排障",
        "description": "系统化排查开发/运维问题（可与自沉淀 Skill 叠加）。",
        "tags": ["devops", "debug", "engineering"],
        "skills": [
            {
                "name": "结构化排障",
                "description": "复现 → 假设 → 验证 → 修复 → 沉淀。",
                "instruction": (
                    "排障时按：现象 / 环境 / 最近变更 / 假设列表 / 验证步骤 / 修复方案。"
                    "涉及外部文档时用 web_search；涉及计算用 calculator。"
                    "问题解决后提醒用户关闭会话以沉淀为 Skill。"
                ),
                "trigger_keywords": ["报错", "失败", "超时", "排障", "debug", "不工作", "500"],
                "trigger_intent": "排查并修复技术问题",
                "workflow": [
                    {"step": 1, "action": "复述问题与复现条件"},
                    {"step": 2, "action": "列出假设并按代价排序验证"},
                    {"step": 3, "action": "给出修复命令/补丁"},
                    {"step": 4, "action": "建议沉淀为 Skill"},
                ],
                "tools": ["web_search", "fetch_url", "calculator"],
            }
        ],
    },
    {
        "id": "nous-writing",
        "name": "写作润色",
        "description": "邮件、方案、周报等结构化写作。",
        "tags": ["writing", "productivity"],
        "skills": [
            {
                "name": "商务写作助手",
                "description": "按受众与目的产出清晰文稿。",
                "instruction": (
                    "写作前确认：体裁、受众、语气、长度。"
                    "输出先给大纲再给正文；提供 2 个标题备选。"
                    "需要事实时先搜索再写，避免臆造数据。"
                ),
                "trigger_keywords": ["写一封", "润色", "周报", "方案", "邮件", "文案"],
                "trigger_intent": "撰写或润色文稿",
                "workflow": [
                    {"step": 1, "action": "确认体裁与约束"},
                    {"step": 2, "action": "给出大纲"},
                    {"step": 3, "action": "输出正文与标题备选"},
                ],
                "tools": ["web_search"],
            }
        ],
    },
]


def list_builtin_packs() -> list[dict[str, Any]]:
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "tags": p.get("tags") or [],
            "skill_count": len(p.get("skills") or []),
        }
        for p in BUILTIN_PACKS
    ]


def get_builtin_pack(pack_id: str) -> dict[str, Any] | None:
    for pack in BUILTIN_PACKS:
        if pack["id"] == pack_id:
            return pack
    return None
