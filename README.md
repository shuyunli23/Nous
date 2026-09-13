# Nous

> 个人智能工作台：能调用工具办实事，也能沉淀 / 导入 Skill，越用越强。

普通聊天机器人每次对话都从零开始：同一个 GitLab SSH 超时问题，你问三次，它推理三次。
Nous 会在会话结束后判断这段对话是否包含可复用的经验，如果有，就把它提炼成一条
结构化的 **Skill**（触发关键词 + 解决步骤 + 给 Agent 的指令）存进长期记忆。下次你再提到
类似问题，相关 Skill 会被检索出来注入系统提示，Agent 直接给出沉淀过的解法。

用得越久，回答越准 —— 而且这些经验是你自己的：可查看、可编辑、每次修改都留有版本快照。

---

## 目录

- [核心特性](#核心特性)
- [技术栈](#技术栈)
- [环境要求](#环境要求)
- [版本管理](#版本管理)
- [快速开始（本地开发）](#快速开始本地开发)
- [配置模型供应商](#配置模型供应商)
- [Docker 部署](#docker-部署)
- [配置项说明](#配置项说明)
- [使用流程](#使用流程)
- [工作原理](#工作原理)
- [数据模型](#数据模型)
- [API 接口](#api-接口)
- [测试](#测试)
- [目录结构](#目录结构)
- [常见问题](#常见问题)
- [安全说明](#安全说明)

---

## 核心特性

| 特性 | 说明 |
| --- | --- |
| **Nous Agent** | LangGraph：记忆 → 检索 Skill → 组装提示 → 调用模型（可循环工具）→ 持久化；长会话有重复调用提醒、超长工具结果落盘、历史压缩 |
| **内置工具** | 网页搜索、抓取页面、查天气、生成 PPT / 网页 Demo、计算器、当前时间、命令执行（沙箱，需显式开启）、`todo_write` 任务清单 |
| **会话预览** | 工具产出的 HTML 网页和 SVG 图在对话里直接预览，可切换源码 |
| **Skill 包导入** | 一键导入内置能力包，或粘贴 JSON（Claude / WorkBuddy 风格 playbook） |
| **插件** | 稳定 `nous-plugin/1`；zip / GitHub 导入；兼容 nous-pack/2 与 DeepSeek Harness（`dsh`）仓库 |
| **Skill 自动沉淀** | 会话关闭时判断可复用性并提炼 Skill，带去重与合并；大段 SVG / HTML 会压缩后再抽取 |
| **混合检索** | 向量 + 关键词融合打分，短查询也能命中 |
| **反馈闭环** | 使用次数与成功率进入排序；失败达阈值可自动禁用 |
| **知识库** | NexusMind：笔记、检索、图谱、知识助手 |
| **Harmony** | 本机音乐播放器（开发时经 `/harmony` 代理；Docker 镜像不含） |
| **UI 配置模型** | 「设置」页切换供应商，无需改 `.env` 或重启 |
| **多源接入** | OpenAI 兼容接口 + AWS Bedrock |

---

## 技术栈

- **后端** — Python 3.11 · FastAPI · SQLAlchemy 2.0（async）· Alembic · LangGraph · ChromaDB · structlog
- **前端** — React 18.3 · TypeScript 5.7 · Vite 6 · React Router 6（无 UI 框架，手写 CSS）
- **存储** — SQLite（本地开发）/ PostgreSQL 16（Docker）· ChromaDB 向量索引
- **部署** — Docker Compose · Nginx（前端静态托管 + API 反向代理）

---

## 环境要求

### 本地开发

| 工具 | 版本 | 说明 |
| --- | --- | --- |
| Python | **3.11+** | 代码用到 `StrEnum`，3.10 及以下无法运行 |
| Node.js | **20+**（推荐 22） | Vite 6 的要求 |
| 数据库 | 不需要 | 默认用 SQLite 文件 |

### Docker 部署

只需要 Docker Engine 20.10+ 和 Docker Compose v2（`docker compose`，注意不是老的 `docker-compose`）。

---

## 版本管理

源码用 Git 跟踪，方便改坏之后找回。仓库目前是**本机仓库**，没有配置远程。

密钥和运行时数据**不会**进版本库（见 `.gitignore`）：

- `.env`、`backend/data/`（SQLite、Chroma、上传 / 导出、供应商密钥、Skill 包）
- `harmony/Music/`、`harmony/tmp_lyrics/`、`harmony/tmp_imgs/`
- `node_modules/`、`.venv/`

常用命令：

```bash
git status
git add -A
git commit -m "说明这次改了什么"
git log --oneline
git checkout -- path/to/file   # 丢弃某个文件的未提交改动
```

需要备份到 GitHub 时，建好远程后执行 `git remote add origin <url>` 再 `git push -u origin main`。

---

## 快速开始（本地开发）

### 1. 准备配置文件

```bash
cp .env.example .env
```

`.env` 里所有值都有可用默认值。**不填任何密钥也能启动**，只是对话功能会返回明确的提示。
想立刻跑通对话的话，填一个 `LLM_API_KEY` 即可（也可以启动后在 UI 里配，见[下一节](#配置模型供应商)）。

建议先把嵌入方式改成免密钥的哈希模式，这样 Skill 检索开箱可用：

```ini
EMBEDDING_PROVIDER=hash
```

### 2. 启动后端

```bash
cd backend

# 创建虚拟环境（首次）
python -m venv .venv

# 激活：Windows PowerShell
.\.venv\Scripts\Activate.ps1
# 激活：macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

python run_dev.py
```

`run_dev.py` 会排除 `data/`。不要用裸的 `uvicorn --reload`：它仍会监视当前目录，Agent 一写 `data/shell_workspace/*.py` 就会把正在跑的对话重启掉。

启动成功后：

- API 根路径 <http://127.0.0.1:8000/api/v1>
- 交互式文档 <http://127.0.0.1:8000/docs>
- 健康检查 <http://127.0.0.1:8000/api/v1/health>

本地默认 `DB_AUTO_CREATE=true`，首次启动会自动建表，**不需要**手动跑迁移。

### 3. 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>。Vite 已配置把 `/api` 代理到 `http://localhost:8000`，
所以前端不需要配置后端地址。要指向别的后端，设 `VITE_API_TARGET` 环境变量。

### 4. 验证

```bash
curl http://127.0.0.1:8000/api/v1/health
```

```json
{
  "status": "ok",
  "environment": "development",
  "database": true,
  "llm_configured": false,
  "embedding_provider": "hash",
  "vector_backend": "chroma",
  "llm_source": "env",
  "llm_provider": ".env defaults",
  "llm_model": "deepseek-chat"
}
```

`llm_configured: false` 只表示还没配模型密钥，其他功能（会话管理、Skill 增删改查、检索）
此时已经可用。`llm_source` 指明当前配置来自哪里：`env` 是 `.env` 兜底，
`runtime` 是 UI 里启用的供应商。

---

## 配置模型供应商

有两种方式，**UI 优先于 `.env`**：启用了任何运行时供应商就用它，没有则回落到 `.env`。

### 方式一：UI 配置（推荐）

进入侧边栏 **模型设置**（`/settings`）→ 新增供应商：

1. 点厂商预设（DeepSeek / 阿里云百炼 / OpenAI / Moonshot / 智谱 / SiliconFlow / Ollama / AWS Bedrock）
   一键预填地址和模型名
2. 填上你自己的密钥
3. 点 **测试连接** —— 保存前就能确认通不通，失败会返回可操作的诊断
4. 保存即生效，**不需要重启后端**

配置持久化在 `backend/data/llm_providers.json`（已在 `.gitignore` 中），重启后仍然有效。

两种接入类型的必填项不同：

| 类型 | 必填 | 可选 |
| --- | --- | --- |
| OpenAI 兼容 | Base URL（填到 `/v1` 为止）、模型名 | API Key（本地 Ollama / vLLM 可留空） |
| AWS Bedrock | AWS 区域、模型 ID | Access Key + Secret / Profile 名 / 都留空走默认凭证链 |

AWS Bedrock 需要额外安装 SDK（因为它用 SigV4 签名而非 Bearer Token，报文格式也不同）：

```bash
cd backend
pip install -r requirements-aws.txt
```

装完在设置页点「检查 Bedrock SDK」确认。不装也不影响其他供应商。

### 方式二：`.env` 配置

适合服务器部署或不想暴露配置接口的场景：

```ini
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=你的密钥
LLM_MODEL=deepseek-chat
```

改完需要重启后端。若要**完全禁用** UI 配置（写接口全部拒绝，只认 `.env`）：

```ini
RUNTIME_LLM_CONFIG_ENABLED=false
```

### 常见供应商参数

| 供应商 | Base URL | 模型示例 |
| --- | --- | --- |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| 阿里云百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-plus` |
| SiliconFlow | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` |
| Ollama（本地） | `http://localhost:11434/v1` | `qwen2.5:7b` |
| AWS Bedrock | —（填区域） | `anthropic.claude-3-5-sonnet-20241022-v2:0` |

---

## Docker 部署

Compose 编排三个服务：**PostgreSQL 16** + **后端 API** + **Nginx 托管的前端**。
Harmony 音乐库是本机开发功能，当前 Compose **不包含** Harmony。

```bash
# 1. 准备配置（必需；至少填 LLM_API_KEY，或部署后在 UI 里配）
cp .env.example .env

# 2. 构建并启动
docker compose up -d --build

# 3. 查看状态与日志
docker compose ps
docker compose logs -f backend
```

访问 <http://localhost:3000>。

### 编排细节

| 服务 | 容器名 | 端口 | 说明 |
| --- | --- | --- | --- |
| `postgres` | `nous-db` | 不对外暴露 | 数据存 `postgres-data` 卷；首次初始化时执行 `scripts/init-db.sql` 装 `unaccent`/`pg_trgm`/`pgcrypto` 扩展 |
| `backend` | `nous-api` | 不对外暴露 | 以非 root 用户运行；Chroma 索引存 `chroma-data` 卷，UI 保存的供应商存 `config-data` 卷，导出/上传存 `exports-data` / `uploads-data`，导入的 Skill 包存 `skill-packs-data` |
| `frontend` | `nous-web` | `3000:80` | Nginx 托管构建产物，并把 `/api/` 反代到 `backend:8000` |

> **`.env` 是必需的**：`backend` 服务通过 `env_file` 读取它，这样[配置项说明](#配置项说明)里
> 列出的每个变量在容器里都生效。文件不存在时 `docker compose up` 会直接报错。

几个值得注意的设计：

- **只有前端暴露端口。** 浏览器看到单一源，API 经 Nginx 反代，因此不存在跨域问题。
  需要直接调 API 调试时，在 `docker-compose.yml` 里取消 `backend` 的 `ports` 注释。
- **Alembic 独占 schema 管理。** 容器里 `DB_AUTO_CREATE=false`，入口脚本先等数据库就绪、
  再执行 `alembic upgrade head`，迁移失败会直接终止启动而不是带着未知 schema 提供服务。
- **依赖健康检查串联。** `backend` 等 `postgres` healthy，`frontend` 等 `backend` healthy。
- **向量索引挂卷持久化。** Postgres 始终是唯一事实来源，索引任何时候都能用
  `POST /api/v1/skills/reindex` 从数据库重建。
- **UI 保存的供应商也挂卷持久化。** 存在 `config-data` 卷（容器内
  `/app/data/config/llm_providers.json`），`--build` 重建镜像不会丢。
- **导出文件与聊天上传挂卷持久化。** `exports-data` / `uploads-data` 对应容器内
  `/app/data/exports` 与 `/app/data/uploads`。HTML 汇报页、SVG 图、PPT、附件都在这里，
  重建镜像后对话里的预览链接仍然有效。
- **导入的 Skill 包挂卷持久化。** `skill-packs-data` 对应 `/app/data/skill_packs`。
- **LLM 超时放宽到 300s。** Nginx 侧已配好，长推理不会被网关掐断。

### 常用运维命令

```bash
docker compose restart backend          # 重启后端
docker compose down                     # 停止（保留数据卷）
docker compose down -v                  # 停止并删除数据（不可恢复）
docker compose exec backend alembic current   # 查看当前迁移版本
docker compose exec postgres psql -U skill -d skillagent   # 连数据库
```

### 覆盖端口 / 凭证

```ini
WEB_PORT=8080
POSTGRES_USER=skill
POSTGRES_PASSWORD=改成强密码
POSTGRES_DB=skillagent
# 用域名或局域网 IP 访问时，把实际来源写进 CORS（逗号分隔）
CORS_ORIGINS=http://localhost:3000
```

---

## 配置项说明

所有配置通过环境变量或 `.env` 提供，优先级：**真实环境变量 > 项目根 `.env` > `backend/.env` > 代码默认值**。

### 应用

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `nous` | 日志中的应用名 |
| `ENVIRONMENT` | `development` | `development` / `test` / `production` |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_JSON` | `false` | 生产环境建议 `true`，输出结构化 JSON 日志 |
| `API_PREFIX` | `/api/v1` | API 路由前缀 |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | 逗号分隔 |

### 数据库

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/skillagent.db` | Postgres 用 `postgresql+asyncpg://user:pass@host:5432/db` |
| `DB_ECHO` | `false` | 打印 SQL，调试用 |
| `DB_AUTO_CREATE` | `true` | 启动时 `create_all` 建表。**用 Alembic 管理时必须设为 `false`** |

### 大模型

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | 兜底配置，UI 未启用供应商时使用 |
| `LLM_API_KEY` | 空 | 兜底密钥 |
| `LLM_MODEL` | `deepseek-chat` | 兜底模型 |
| `LLM_TEMPERATURE` | `0.3` | |
| `LLM_MAX_TOKENS` | `8192` | 单次补全上限；设置里可调到当前模型支持的最大值。旧的 `2048` 视为「没选过」，按模型上限处理，避免网页/PPT JSON 被截断 |
| `LLM_TIMEOUT_SECONDS` | `120` | |
| `LLM_MAX_RETRIES` | `2` | 仅对 429/5xx 重试，指数退避 |
| `RUNTIME_LLM_CONFIG_ENABLED` | `true` | 设为 `false` 则关闭 UI 配置，只认 `.env` |
| `LLM_PROVIDER_STORE` | `./data/llm_providers.json` | 运行时供应商存储路径 |

### 嵌入模型

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `EMBEDDING_PROVIDER` | `remote` | `remote`（OpenAI 兼容 `/embeddings`）/ `local`（进程内）/ `hash`（确定性哈希，免密钥） |
| `EMBEDDING_BASE_URL` | `https://api.openai.com/v1` | |
| `EMBEDDING_API_KEY` | 空 | 留空时回退到 `LLM_API_KEY` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | |
| `EMBEDDING_LOCAL_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | 需装 `requirements-local.txt`（约 1GB） |
| `EMBEDDING_DIM` | `1536` | 远程模型维度；`hash` 固定 512 |
| `EMBEDDING_FALLBACK_TO_HASH` | `true` | 远程失败时自动降级，保证检索不中断 |

> 切换嵌入方式会改变向量维度，之后需要执行一次 `POST /api/v1/skills/reindex?force=true` 重建索引。

### 向量库

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VECTOR_BACKEND` | `chroma` | `chroma`（持久化）/ `memory`（进程内，测试用） |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | |
| `CHROMA_COLLECTION` | `skills` | |

### Agent 与记忆

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MEMORY_MAX_TURNS` | `12` | 带入上下文的最大轮数 |
| `MEMORY_MAX_CHARS` | `8000` | 上下文字符上限 |
| `AGENT_MAX_TOOL_LOOPS` | `4` | 工具调用循环上限，防止死循环 |
| `GUARD_REPEAT_ENABLED` | `true` | 连续相同工具调用达到阈值时注入提醒（不拦截） |
| `GUARD_REPEAT_THRESHOLDS` | `3,5,8` | 第 3 次短提醒，之后点名工具和参数 |
| `SPILL_MAX_INLINE_BYTES` | `8192` | 工具 JSON 超过此字节则落盘，模型只看预览；`0` 关闭 |
| `COMPACT_CHECKPOINT_ENABLED` | `true` | 历史超出预算时，被丢掉的前缀压成 `<compacted-summary>` |

### 命令执行工具（沙箱）

思路移植自 DeepSeek Harness 的 `shell/` + `sandbox/`：给 Agent 一个 `run_command` 工具，在**受限工作区**里执行真实命令（看文件、跑脚本、git、构建测试），并返回 stdout/stderr 与退出码。**默认关闭**——这是很大的安全面，需在信任的机器上显式打开。

> **开关放在 UI 里**：进「设置 → 通用 → 命令执行」可直接切换启用/关闭、选择默认沙箱模式，即时生效、无需改 `.env` 或重启。运行时覆盖存在 `data/shell_config.json`（已 gitignore）。**唯独提权上限 `SHELL_MAX_MODE` 只认 `.env`**——前端永远无法调高这个安全上限，因此 UI 不可能自行放开 `danger-full-access`。下面的表是 `.env` 兜底默认值。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SHELL_TOOL_ENABLED` | `false` | 总开关。为 `false` 时该工具既不进 schema 也不可执行 |
| `SHELL_WORKSPACE_DIR` | `./data/shell_workspace` | 工作区根目录；每次调用的 cwd 都被限制在其内部 |
| `SHELL_DEFAULT_MODE` | `workspace-write` | 未申请提权时的默认模式 |
| `SHELL_MAX_MODE` | `workspace-write` | 允许提权到的**上限**。Nous 无交互式审批，所以这个上限就是同意闸门 |
| `SHELL_OS_SANDBOX` | `auto` | `auto` 时在 Linux/macOS 用 bubblewrap / sandbox-exec 做内核级隔离；`off` 强制降级 |
| `SHELL_NETWORK_ENABLED` | `false` | 是否放行网络（仅在有内核后端时才真正强制） |
| `SHELL_TIMEOUT_SECONDS` / `SHELL_TIMEOUT_CAP_SECONDS` | `60` / `300` | 单次默认超时与硬上限 |
| `SHELL_STDOUT_CAP_BYTES` | `262144` | 输出上限，超出保留尾部并标记截断 |

隔离是**纵深防御**，并对平台差异保持诚实：

1. **总开关**——默认不暴露该工具。
2. **工作区限制**——cwd 与 `workdir` 解析后必须落在工作区根内，越界直接拒绝（不 spawn）。命令**无状态**：进程间不保留 shell 状态，用 `workdir` 而不是 `cd`。
3. **命令策略**——始终生效的「灾难性命令」黑名单（`rm -rf /`、fork bomb、磁盘擦写、关机等，任何模式都拦）；当 `read-only` 只能「建议式」强制时，额外拦截写重定向与会改文件的命令。
4. **内核沙箱（尽力而为）**——Linux 上 `bwrap`、macOS 上 `sandbox-exec` 存在时做真正的文件系统限制；无后端的平台（如 Windows）退化为 cwd + 黑名单，结果里以 `enforcement=advisory` 如实标注。
5. **环境擦洗 + 超时 + 输出上限**——子进程只继承最小白名单环境（不泄露任何凭证）。

模式（安全序）：`read-only` < `workspace-write` < `danger-full-access`。模型被拦时可**一次性**带 `sandbox_permissions` + `justification` 申请更宽模式，但不能超过 `SHELL_MAX_MODE`；要放开 `danger-full-access` 必须由运维把上限调高。

### Skill 检索

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SKILL_TOP_K` | `3` | 最多注入几条 Skill |
| `SKILL_MIN_SIMILARITY` | `0.28` | 融合得分阈值，低于此值不注入 |
| `SKILL_KEYWORD_BOOST` | `0.15` | 关键词命中的加权系数 |
| `SKILL_CANDIDATE_POOL` | `12` | 向量召回候选池大小 |

### Skill 提取

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `EXTRACTION_ENABLED` | `true` | 关闭后不再自动沉淀 |
| `EXTRACTION_MIN_MESSAGES` | `4` | user + assistant 消息少于此数的会话直接跳过 |
| `EXTRACTION_MIN_CONFIDENCE` | `0.6` | 可复用性置信度阈值 |
| `EXTRACTION_DEDUPE_THRESHOLD` | `0.9` | 相似度超过则合并进已有 Skill 而非新建 |
| `EXTRACTION_AUTO_ACTIVATE` | `false` | 默认存为草稿，需人工确认后启用 |
| `SKILL_AUTO_DISABLE_FAILURES` | `3` | **累计**失败次数达到此值时自动禁用（失败计数不会因成功而重置） |

### 其他

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEFAULT_USER_EXTERNAL_ID` | `local-dev` | 请求未带 `X-User-Id` 时使用的默认用户 |

---

## 使用流程

1. **对话** —— 在工作台提问。命中 Skill 时，回答下方会列出用到了哪些经验，以及本次的 token 用量。工具生成的 **HTML 网页**和 **SVG 图**会嵌在消息里预览，可切换「源码」。
2. **反馈** —— 对注入的 Skill 点赞/点踩，成绩会计入该 Skill 的成功率并影响后续排序。
3. **关闭会话** —— 在「会话」里关闭一个已解决的会话，系统自动判断可复用性并提炼 Skill。含大图 / 完整 SVG 的对话会先压缩再抽取，避免模型返回空 JSON。
4. **审核 Skill** —— 自动生成的 Skill 默认是**草稿**，需要在「Skill 管理」里确认并启用后才参与检索。
5. **调阈值** —— 「Skill 管理」页顶部的检索测试框可以输入任意问题，查看命中情况和
   「向量得分 + 关键词得分」拆解，方便调 `SKILL_MIN_SIMILARITY`。
6. **安装插件** —— 同一页可贴 GitHub 地址（`owner/repo`）或上传 zip。稳定格式是根目录 `plugin.json`（`nous-plugin/1`）。DeepSeek Harness 插件仓库（`package.json` 里有 `dsh` 字段）会导入为 Skill；**不会**执行 Cordis 的 TypeScript `apply()`。带 Python 脚本的包仍走沙箱，需勾选 `script.python`。示例：`docs/examples/hello-plugin`。

---

## 工作原理

### Agent 流程

```
load_memory → retrieve_skills → compose_prompt → llm_call
                                                     ↓
                                           should_call_tools?
                                          /                \
                                      tools              persist
                                        ↑                   ↓
                                   tool_executor           END
```

各节点职责：

| 节点 | 做什么 |
| --- | --- |
| `load_memory` | 按轮数和字符预算截取历史消息 |
| `retrieve_skills` | 混合检索相关 Skill，并写入使用台账 |
| `compose_prompt` | 把 Skill 的步骤和指令编排进系统提示 |
| `llm_call` | 调用模型；请求工具调用时走条件边循环 |
| `tool_executor` | 执行内置工具（搜索、天气、PPT、网页 Demo、计算器、命令执行、`todo_write` 等） |
| `persist` | 落库消息、token 用量、以及本次用到的 Skill ID（审计轨迹） |

**`todo_write`（规划清单）** 移植自 DeepSeek Harness：整表替换本会话任务清单（`pending` / `in_progress` / `completed`）。每次必须提交完整列表，同时只能有一项进行中。清单挂在会话上、跨轮次保留，执行过程里会画出勾选条。简单问答不要用。

### Skill 提取链

会话关闭时触发（也可手动调 `POST /api/v1/skills/generate`）：

```
读取消息 → 压缩大段 SVG / HTML → 判断可复用性（结构化 LLM 调用）
              ↓ 可复用且置信度 ≥ 阈值
         起草 Skill（结构化 LLM 调用）
              ↓
         与已有 Skill 去重
              ↓
    新建（草稿）或合并进已有 Skill（版本 +1）
```

消息数不足、判定不可复用、或置信度不够时状态记为 `skipped`；LLM 报错记为 `failed`，
两种情况都不影响主流程。含完整图纸源码的长会话若抽取失败，可在「会话」里再点一次抽取。

### 混合检索打分

纯向量检索在短查询上不可靠 ——「gitlab ssh 又超时了」这种恰恰是复发问题最常见的说法。
因此最终得分是两条腿融合：

```
score = 向量相似度 + 关键词得分 × SKILL_KEYWORD_BOOST
```

关键词得分（0~1）由三部分构成：触发关键词命中比例（支持子串与词元乱序两种匹配）、
Skill 名称词元重叠 × 0.5、触发意图词元重叠 × 0.3。

超过阈值的结果按 **融合得分 → 成功率 → 使用次数** 排序，所以在相关度接近时，
已被验证有效的 Skill 会胜出。未评分的 Skill 成功率按 0.5 计，不会被过度惩罚或奖励。

---

## 数据模型

6 张业务表，均以 `user_id` 隔离数据：

| 表 | 说明 |
| --- | --- |
| `users` | 用户。当前无鉴权，由 `X-User-Id` 头选择或自动创建 |
| `conversations` | 会话，含状态与提取状态 |
| `messages` | 消息，带 `seq` 顺序号、token 用量、`used_skill_ids` |
| `skills` | Skill 主体：触发条件、解决步骤、示例、统计数据 |
| `skill_versions` | Skill 每个版本的快照，含变更原因；创建时即写入 v1，之后每次更新版本 +1 |
| `skill_usages` | 使用台账：哪条 Skill 在哪条消息被用到、反馈如何 |

枚举全部以 VARCHAR 存储而非数据库原生枚举，这样新增取值只是代码改动，不需要迁移，
也保证 SQLite 与 Postgres 行为一致。

### 迁移

```bash
cd backend
alembic upgrade head          # 应用到最新
alembic current               # 查看当前版本
alembic downgrade -1          # 回滚一步
alembic revision --autogenerate -m "描述"   # 生成新迁移
```

本地用 `DB_AUTO_CREATE=true` 时不需要跑迁移；Docker 里由入口脚本自动执行。

---

## API 接口

完整交互式文档见 <http://127.0.0.1:8000/docs>。所有接口都在 `/api/v1` 下，
可选 `X-User-Id` 请求头用于区分用户。

### 对话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat` | 发消息，省略 `conversation_id` 则自动新建会话 |

### 会话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/conversations` | 创建空会话 |
| `GET` | `/conversations` | 列表（分页） |
| `GET` | `/conversations/{id}` | 完整上下文（含消息） |
| `PATCH` | `/conversations/{id}` | 改标题或状态 |
| `DELETE` | `/conversations/{id}` | 删除会话及其消息 |
| `POST` | `/conversations/{id}/close` | 关闭并触发 Skill 提取 |

### Skill

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/skills` | 手动创建 |
| `GET` | `/skills` | 列表（可按状态/关键词筛选） |
| `GET` | `/skills/{id}` | 详情 |
| `PUT` | `/skills/{id}` | 更新（版本 +1） |
| `PATCH` | `/skills/{id}/status` | 启用 / 禁用 / 废弃 |
| `DELETE` | `/skills/{id}` | 删除并从索引移除 |
| `POST` | `/skills/generate` | 手动触发从会话提取 |
| `POST` | `/skills/search` | 检索测试，返回得分拆解 |
| `POST` | `/skills/reindex` | 从数据库重建向量索引 |
| `POST` | `/skills/{id}/feedback` | 记录使用反馈 |

### 插件

稳定清单是 `plugin.json`（`nous-plugin/1`）。也接受 `pack.json`（nous-pack/2）和 DeepSeek Harness 的 `package.json`（`dsh` 字段）。GitHub 只允许 github.com / gitlab.com。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/plugins/preview` | 校验 zip（不安装） |
| `POST` | `/plugins/preview-url` | 拉取 GitHub 仓库并校验 |
| `POST` | `/plugins` | 安装 zip |
| `POST` | `/plugins/from-url` | 从 GitHub URL 安装 |
| `GET` | `/pack-archives` | 已安装插件列表 |
| `PATCH` | `/pack-archives/{id}` | 启用 / 停用 |
| `DELETE` | `/pack-archives/{id}` | 卸载 |

### 模型配置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/llm/config` | 当前生效配置、已保存供应商、厂商预设 |
| `POST` | `/llm/providers` | 新增供应商 |
| `PUT` | `/llm/providers/{id}` | 更新（未提交的字段保持原值，传空字符串表示清除） |
| `DELETE` | `/llm/providers/{id}` | 删除 |
| `POST` | `/llm/providers/{id}/activate` | 切换生效供应商 |
| `POST` | `/llm/deactivate` | 放弃运行时配置，回落到 `.env` |
| `POST` | `/llm/test` | 连通性探测（可传 `provider_id`、`draft`，或都不传测当前配置） |
| `POST` | `/llm/bedrock/check` | 检查 boto3 是否已安装 |

### 健康检查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 数据库连通性、生效的模型来源与型号、嵌入与向量后端 |

### 错误格式

所有错误统一信封，便于前端处理：

```json
{
  "error": {
    "code": "llm_error",
    "message": "LLM API key not configured. Add a provider on the settings page, ...",
    "details": { "hint": "打开「模型设置」页面添加供应商，…" },
    "request_id": "a53ab407a2f6"
  }
}
```

`request_id` 同时出现在响应头 `X-Request-Id` 和后端日志里，便于串联排查。

---

## 测试

后端测试是可直接运行的脚本（不是 pytest 套件）。**必须从 `backend/` 目录以模块方式运行**，
否则 `app` 包不在搜索路径上会报 `ModuleNotFoundError`：

```bash
cd backend

python -m tests.smoke_phase1      # 会话 CRUD
python -m tests.smoke_phase2      # 对话 / Agent（mock 掉 LLM）
python -m tests.smoke_phase3      # Skill 提取与管理（mock 掉 LLM）
python -m tests.smoke_phase4      # 嵌入、向量库、混合检索
python -m tests.smoke_llm_config  # 运行时模型配置（含 Bedrock 报文转换）
python -m tests.test_shell_tool   # 命令执行工具：隔离策略 + 本机真实执行
python -m tests.test_todo         # todo_write 校验与提示注入
python -m tests.test_context_governance  # 重复调用提醒 / 工具结果落盘 / 历史压缩
python -m tests.check_migration   # 校验 Alembic 迁移与 ORM 模型一致
```

全部不需要网络、不需要 API 密钥，也不会污染你的真实配置
（`smoke_llm_config` 使用临时目录里的独立存储文件）。

前端检查：

```bash
cd frontend
npm run typecheck    # tsc --noEmit
npm run build        # 类型检查 + 生产构建
```

---

## 目录结构

```
nous/
├── docker-compose.yml
├── .env.example                 # 配置模板（唯一需要复制的文件）
├── scripts/init-db.sql          # Postgres 扩展初始化
├── backend/
│   ├── Dockerfile
│   ├── docker-entrypoint.sh     # 等数据库 → 跑迁移 → 启动
│   ├── requirements.txt         # 核心依赖
│   ├── requirements-dev.txt     # pytest
│   ├── requirements-aws.txt     # 可选：Bedrock（boto3）
│   ├── requirements-local.txt   # 可选：本地嵌入（sentence-transformers）
│   ├── alembic/                 # 迁移
│   ├── tests/                   # 冒烟测试脚本
│   └── app/
│       ├── main.py              # FastAPI 入口
│       ├── agent/               # LangGraph 状态图与节点
│       ├── api/                 # 路由（v1）
│       ├── core/                # 配置、依赖、异常、日志
│       ├── database/            # 引擎、会话、ORM 模型
│       ├── llm/                 # 模型客户端、供应商、嵌入、提示词
│       ├── memory/              # 会话记忆、Skill 记忆、向量库
│       ├── nexusmind/           # 知识库
│       ├── repositories/        # 数据访问
│       ├── schemas/             # Pydantic 请求/响应模型
│       ├── services/            # 业务编排
│       ├── skill/               # 提取器、检索器、pack 格式
│       └── plugin/              # 插件导入（nous-plugin/1、GitHub、dsh）
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
│       ├── api/                 # 接口封装与类型
│       ├── appearance/          # 图谱 / 侧栏动态背景
│       ├── components/          # 布局、消息、编辑器
│       ├── pages/               # 工作台、会话、Skill、知识库、设置
│       └── styles/index.css
└── harmony/                     # 本机音乐播放器（开发用，不进 Docker）
```

---

## 常见问题

**对话报 502 `llm_error`，提示未配置密钥**
还没配模型。去「模型设置」加一个供应商（可先点「测试连接」验证），或在 `.env` 里填 `LLM_API_KEY`。

**`ModuleNotFoundError: No module named 'app'`**
测试脚本用了 `python tests/smoke_phase1.py` 这种直接执行的方式。改成从 `backend/` 目录跑
`python -m tests.smoke_phase1`。

**改了 UI 里的模型配置，但好像没生效**
配置是每次调用时解析的，不需要重启。如果仍不对，检查设置页顶部「当前生效」卡片显示的是
哪个来源；也确认服务端没有设 `RUNTIME_LLM_CONFIG_ENABLED=false`。

**Skill 检索一条都命中不了**
三种常见原因：Skill 还是**草稿**状态（需在「Skill 管理」里启用）；`SKILL_MIN_SIMILARITY`
偏高；换过嵌入方式但没重建索引。用「Skill 管理」页的检索测试框看得分拆解最快定位。

**Skill 抽取报 `invalid JSON for structured output`**
常见于含大段 SVG / HTML 的长会话：模型起草 Skill 时返回空内容。抽取已会压缩图纸源码。
在「会话」里对失败条目再点一次「抽取 Skill」。

**换了 `EMBEDDING_PROVIDER` 之后检索变得很奇怪**
向量维度变了，旧索引失效。执行 `POST /api/v1/skills/reindex?force=true` 重建。

**AWS Bedrock 报 boto3 未安装**
`cd backend && pip install -r requirements-aws.txt`。

**Bedrock 报 AccessDenied**
检查 IAM 权限是否包含 `bedrock:InvokeModel`，以及该模型是否已在 Bedrock 控制台申请开通。
错误响应的 `details.hint` 里会带上针对性建议。

**Docker 里前端起来了但接口 502**
后端还没通过健康检查。`docker compose logs backend` 看迁移是否失败。

**端口 8000 已被占用**
换端口 `uvicorn app.main:app --port 8001`，同时给前端设 `VITE_API_TARGET=http://localhost:8001`。

---

## 安全说明

这个项目定位是**单人本地工具**，默认没有鉴权 —— `X-User-Id` 请求头即身份。
要对外提供服务的话，请注意以下几点：

1. **加鉴权。** 所有查询已经按 `user_id` 隔离，替换 `app/core/deps.py` 里的
   `get_current_user` 一个依赖即可覆盖全部接口。
2. **关闭运行时模型配置。** 设 `RUNTIME_LLM_CONFIG_ENABLED=false`。该功能的写接口会
   接收明文密钥，且配置以明文存放在 `backend/data/llm_providers.json`。
   （读接口返回的凭证一律掩码为 `****1234`，密钥不会回传给浏览器，也不会写进日志。）
3. **改掉数据库默认口令。** `docker-compose.yml` 里 `skill/skill` 仅供本地使用。
4. **启用 JSON 日志。** `LOG_JSON=true`，便于接入日志系统。
5. **收紧 CORS。** `CORS_ORIGINS` 明确列出实际域名。
6. **`.env` 与 `backend/data/` 已被 gitignore**，注意不要绕过它们提交密钥。
