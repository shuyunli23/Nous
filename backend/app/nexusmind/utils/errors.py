"""NexusMind 业务异常。

继承 Nous 的 AppError，这样会走统一的 ``{error: {code, message}}`` 响应信封。
同时保留 ``detail`` 属性，兼容原 NexusMind 调用点。
"""

from __future__ import annotations

from fastapi import status

from app.core.exceptions import AppError as NousAppError
from app.core.exceptions import LLMError


class AppError(NousAppError):
    """业务异常基类。Service 层抛出，API 层无需再包一层 try。"""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"

    def __init__(self, detail: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class ExternalServiceError(LLMError):
    """调用第三方（LLM 服务商）失败。"""

    code = "external_service_error"

    def __init__(self, detail: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
