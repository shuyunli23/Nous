"""通用响应 Schema。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """统一分页信封。前端所有列表接口共用这一种结构。"""

    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class MessageResponse(BaseModel):
    """无数据返回的操作结果（删除、批量更新等）。"""

    success: bool = True
    message: str = "ok"


class ErrorResponse(BaseModel):
    """统一错误结构，前端 axios 拦截器按此解析。"""

    detail: str
    code: str = "error"
