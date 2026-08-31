"""Shared API schema building blocks."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for response models read directly off ORM instances."""

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, obj: object, **overrides: object) -> "ORMModel":
        """Validate an ORM instance and apply field overrides in one call.

        Pydantic v2 removed the ``update=`` kwarg from ``model_validate()``.
        Use this instead of ``model_validate(obj, update={...})``.
        """
        instance = cls.model_validate(obj)
        if overrides:
            return instance.model_copy(update=overrides)
        return instance


class Page(BaseModel, Generic[T]):
    """Offset paginated envelope."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class OkResponse(BaseModel):
    ok: bool = True
    message: str | None = None
