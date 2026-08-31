"""API 层公共依赖。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.nexusmind.db.session import get_db

# 数据库会话依赖别名，端点签名里直接写 `db: DBSession`
DBSession = Annotated[Session, Depends(get_db)]


class PaginationParams:
    """列表接口通用分页参数。"""

    def __init__(self, page: int = 1, page_size: int = 20) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def get_pagination(
    page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
) -> PaginationParams:
    """作为 FastAPI Depends 使用，避免类 __init__ 注解在 pydantic 下解析失败。"""
    return PaginationParams(page=page, page_size=page_size)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]
