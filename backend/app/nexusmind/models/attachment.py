"""附件模型 —— 与知识条目绑定的本地文件资源。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.nexusmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.nexusmind.models.knowledge import Knowledge


class Attachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """附件元数据。

    文件本体落在 `settings.attachments_dir/<knowledge_id>/<stored_name>`，
    数据库只保存相对路径，方便整体迁移数据目录。
    """

    __tablename__ = "attachment"

    knowledge_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 用户上传时的原始文件名，下载时回填给浏览器
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # 落盘文件名（UUID + 扩展名），避免重名覆盖与路径穿越
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 相对 settings.attachments_dir 的 POSIX 路径
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)

    extension: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    knowledge: Mapped["Knowledge"] = relationship(back_populates="attachments")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Attachment {self.filename} ({self.size_bytes}B)>"
