"""ORM 模型聚合导出。

`init_db()` 依赖本模块把所有模型注册进 `Base.metadata`，
新增模型时必须在这里导入，否则 `create_all` 不会建表。
"""

from app.nexusmind.models.associations import knowledge_keyword
from app.nexusmind.models.attachment import Attachment
from app.nexusmind.models.embedding import KnowledgeEmbedding
from app.nexusmind.models.keyword import Keyword, normalize_keyword
from app.nexusmind.models.knowledge import AnalysisStatus, Knowledge, KnowledgeSource
from app.nexusmind.models.model_config import PROVIDER_DEFAULT_BASE_URL, LLMProvider, ModelConfig

__all__ = [
    "knowledge_keyword",
    "Attachment",
    "KnowledgeEmbedding",
    "Keyword",
    "normalize_keyword",
    "Knowledge",
    "KnowledgeSource",
    "AnalysisStatus",
    "ModelConfig",
    "LLMProvider",
    "PROVIDER_DEFAULT_BASE_URL",
]
