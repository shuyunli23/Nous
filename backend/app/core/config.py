"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Typed application configuration.

    Values come from (in order of precedence): real environment variables,
    ``backend/.env``, then the defaults declared here.
    """

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "nous"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = False
    api_prefix: str = "/api/v1"

    # Stored as a raw string, not list[str]: pydantic-settings tries to JSON
    # decode complex types from .env before any validator runs, which rejects
    # plain comma-separated values like "http://a,http://b".
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./data/skillagent.db"
    db_echo: bool = False
    db_auto_create: bool = True

    # --- LLM ---
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2

    # Runtime provider overrides configured from the UI. Values above act as the
    # fallback whenever no runtime provider is active. Disable in shared or
    # public deployments: the endpoints accept credentials over plain HTTP.
    runtime_llm_config_enabled: bool = True
    llm_provider_store: str = "./data/llm_providers.json"

    # --- Embeddings ---
    embedding_provider: Literal["remote", "local", "hash"] = "remote"
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_local_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedding_dim: int = 1536
    embedding_fallback_to_hash: bool = True

    # --- Vector store ---
    vector_backend: Literal["chroma", "memory"] = "chroma"
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection: str = "skills"

    # --- Agent / memory ---
    memory_max_turns: int = 32
    memory_max_chars: int = 48000
    agent_max_tool_loops: int = 12
    agent_max_verify_retries: int = 2

    # --- Skill packs (nous-pack/2) ---
    skill_packs_dir: str = "./data/skill_packs"
    skill_pack_max_zip_bytes: int = 20 * 1024 * 1024
    skill_pack_max_uncompressed_bytes: int = 80 * 1024 * 1024
    skill_pack_max_files: int = 200
    skill_pack_tool_timeout_cap_sec: int = 120
    skill_pack_tool_stdout_cap_bytes: int = 1 * 1024 * 1024
    skill_pack_max_tools_in_prompt: int = 32

    # --- Shell tool (command execution, ported from Harness shell/ + sandbox/) ---
    # OFF by default: this is a large security surface. Enable explicitly to let
    # the agent run OS commands inside a confined workspace.
    shell_tool_enabled: bool = False
    # Durable workspace root; every command runs with cwd confined under it.
    shell_workspace_dir: str = "./data/shell_workspace"
    # Sandbox mode vocabulary (fail-safe order): read-only < workspace-write <
    # danger-full-access. `default` is used when the model does not escalate;
    # `max` is the operator-controlled ceiling a call may escalate up to. There
    # is no interactive approval in Nous, so `max` IS the consent gate —
    # danger-full-access is only reachable when an operator raises it here.
    shell_default_mode: Literal[
        "read-only", "workspace-write", "danger-full-access"
    ] = "workspace-write"
    shell_max_mode: Literal[
        "read-only", "workspace-write", "danger-full-access"
    ] = "workspace-write"
    # Use a kernel-level sandbox backend when present (bubblewrap on Linux,
    # sandbox-exec on macOS). "off" forces the advisory (cwd + denylist) path.
    shell_os_sandbox: Literal["auto", "off"] = "auto"
    # Best-effort network flag (advisory unless an OS backend enforces it).
    shell_network_enabled: bool = False
    shell_timeout_seconds: int = 60
    shell_timeout_cap_seconds: int = 300
    shell_stdout_cap_bytes: int = 256 * 1024
    # Runtime overlay written by the Settings UI (enable toggle + standing mode).
    shell_config_store: str = "./data/shell_config.json"

    # --- Image generation ---
    # auto | openai | huggingface | bedrock
    image_provider: str = "auto"
    image_api_base_url: str = ""
    image_api_key: str = ""
    image_model: str = "dall-e-3"
    # Hugging Face Inference Providers (e.g. fal-ai, replicate, hf-inference)
    image_hf_provider: str = "fal-ai"
    hf_token: str = ""
    image_bedrock_model: str = "amazon.nova-canvas-v1:0"
    image_timeout_seconds: float = 180.0

    # --- Web search ---
    # Primary free path: DuckDuckGo HTML scrape, then ddgs (bing/duckduckgo/brave).
    # Optional API keys (Brave / Tavily / Serper) upgrade quality when set.
    # Runtime overrides live in web_search_store (Settings UI).
    # brave | tavily | serper | deepseek | ddgs | ddg_html | auto
    web_search_provider: str = "auto"
    brave_search_api_key: str = ""
    tavily_api_key: str = ""
    serper_api_key: str = ""
    web_search_timeout_seconds: float = 15.0
    # Comma-separated ddgs engines tried in order (not "auto" — that is too slow).
    web_search_ddgs_backends: str = "bing,duckduckgo,brave"
    web_search_store: str = "./data/web_search.json"
    # DeepSeek official server-side search (Harness web_search_20250305).
    # Separate from chat: only the API key is reused when the chat endpoint is DeepSeek.
    deepseek_search_api_key: str = ""
    deepseek_search_base_url: str = "https://api.deepseek.com/anthropic/v1"
    deepseek_search_model: str = "deepseek-v4-flash"
    deepseek_search_max_tokens: int = 4096
    deepseek_search_max_uses: int = 2
    deepseek_search_timeout_seconds: float = 90.0

    # --- Skill retrieval ---
    skill_top_k: int = 3
    skill_min_similarity: float = 0.28
    skill_keyword_boost: float = 0.15
    skill_candidate_pool: int = 12

    # --- Skill extraction ---
    extraction_enabled: bool = True
    extraction_min_messages: int = 4
    extraction_min_confidence: float = 0.6
    extraction_dedupe_threshold: float = 0.9
    extraction_auto_activate: bool = False
    skill_auto_disable_failures: int = 3

    # --- Owner unlock (LAN) ---
    # Empty password falls back to Harmony ADMIN_PASSWORD (default admin123).
    # Loopback clients skip this; Harmony guest accounts still cannot enter Nous.
    nous_owner_password: str = ""
    nous_session_secret: str = ""
    nous_session_days: int = 30

    # --- Dev convenience ---
    default_user_external_id: str = "local-dev"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parsed CORS origins. Accepts a comma-separated string or JSON array."""
        raw = self.cors_origins.strip()
        if raw.startswith("["):
            import json

            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except ValueError:
                pass
        return [item.strip() for item in raw.split(",") if item.strip()]

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def resolve_path(self, raw: str) -> Path:
        """Resolve a possibly relative config path against the backend root."""
        path = Path(raw)
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    @property
    def chroma_path(self) -> Path:
        return self.resolve_path(self.chroma_persist_dir)

    @property
    def llm_provider_store_path(self) -> Path:
        return self.resolve_path(self.llm_provider_store)

    @property
    def skill_packs_path(self) -> Path:
        return self.resolve_path(self.skill_packs_dir)

    @property
    def shell_workspace_path(self) -> Path:
        return self.resolve_path(self.shell_workspace_dir)

    @property
    def shell_config_store_path(self) -> Path:
        return self.resolve_path(self.shell_config_store)

    @property
    def web_search_store_path(self) -> Path:
        return self.resolve_path(self.web_search_store)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so the env is parsed once per process."""
    return Settings()


settings = get_settings()
