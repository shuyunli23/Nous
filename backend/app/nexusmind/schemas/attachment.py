"""附件 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_id: str
    filename: str
    extension: str
    mime_type: str
    size_bytes: int
    created_time: datetime
    updated_time: datetime
