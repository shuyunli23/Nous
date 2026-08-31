"""全局配置。

所有可调参数集中在此处，通过环境变量或 `backend/.env` 覆盖，
避免在业务代码里出现硬编码的路径 / 端口 / 限额。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/nexusmind/config/settings.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """应用配置对象（单例，见 `get_settings`）。"""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="NEXUSMIND_",
        extra="ignore",
    )

    # ---------------------------------------------------------------- 应用
    APP_NAME: str = "Nous Knowledge"
    APP_DESCRIPTION: str = "Nous 个人知识库（由 NexusMind 合并）"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # ---------------------------------------------------------------- 服务
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 允许跨域的前端来源；开发期默认放开 Vite 的两个常用端口
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    # ---------------------------------------------------------------- 存储
    DATA_DIR: Path = BACKEND_ROOT / "data" / "nexusmind"
    DATABASE_URL: str = ""  # 留空则在 validator 中按 DATA_DIR 推导

    # 附件上传限制
    MAX_ATTACHMENT_SIZE_MB: int = 100
    # Markdown 导入文件大小限制
    MAX_MARKDOWN_SIZE_MB: int = 10
    # 允许上传的附件扩展名；空集合表示不限制
    ALLOWED_ATTACHMENT_EXTS: set[str] = Field(
        default_factory=lambda: {
            # 文档
            ".md", ".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv",
            # 图片
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico",
            # 压缩包
            ".zip", ".tar", ".gz", ".rar", ".7z",
            # 代码 / 数据
            ".json", ".yaml", ".yml", ".xml", ".sql", ".log",
        }
    )

    # ---------------------------------------------------------------- AI
    # 单次送入 LLM 的 Markdown 最大字符数，超出则截断（控制 token 成本）
    AI_MAX_INPUT_CHARS: int = 12000
    AI_REQUEST_TIMEOUT: int = 90
    # 本地兜底算法默认提取的关键词数量
    LOCAL_KEYWORD_TOPK: int = 8

    # ---------------------------------------------------------------- Phase 7：向量 / 助手
    # 本地特征哈希维度（越大区分度越高，索引越大）
    EMBEDDING_DIM: int = 384
    # 语义检索最低余弦相似度（0~1）
    VECTOR_MIN_SCORE: float = 0.05
    # 助手默认召回条数
    ASSISTANT_TOP_K: int = 6

    # ---------------------------------------------------------------- 派生属性
    @field_validator("DATA_DIR", mode="before")
    @classmethod
    def _expand_data_dir(cls, v: object) -> Path:
        path = Path(str(v)).expanduser()
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    @property
    def attachments_dir(self) -> Path:
        """附件落盘根目录。"""
        return self.DATA_DIR / "attachments"

    @property
    def database_url(self) -> str:
        """SQLAlchemy 连接串；默认使用 DATA_DIR 下的 SQLite 文件。"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"sqlite:///{(self.DATA_DIR / 'nexusmind.db').as_posix()}"

    @property
    def max_attachment_bytes(self) -> int:
        return self.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024

    @property
    def max_markdown_bytes(self) -> int:
        return self.MAX_MARKDOWN_SIZE_MB * 1024 * 1024

    def ensure_dirs(self) -> None:
        """启动时保证所有数据目录存在。"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """带缓存的配置读取，全进程共享同一个实例。"""
    return Settings()


settings = get_settings()
