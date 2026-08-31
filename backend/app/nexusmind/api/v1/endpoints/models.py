"""AI 模型管理中心 API。"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.nexusmind.api.deps import DBSession
from app.nexusmind.schemas.common import MessageResponse
from app.nexusmind.schemas.model_config import (
    PROVIDER_CATALOG,
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigUpdate,
    ModelTestRequest,
    ModelTestResult,
    ProviderInfo,
)
from app.nexusmind.services import model_config_service

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/providers", response_model=list[ProviderInfo], summary="服务商目录")
def list_providers() -> list[ProviderInfo]:
    return PROVIDER_CATALOG


@router.get("", response_model=list[ModelConfigOut], summary="模型配置列表")
def list_models(db: DBSession) -> list[ModelConfigOut]:
    return [model_config_service.to_out(i) for i in model_config_service.list_models(db)]


@router.post(
    "",
    response_model=ModelConfigOut,
    status_code=status.HTTP_201_CREATED,
    summary="新增模型配置",
)
def create_model(payload: ModelConfigCreate, db: DBSession) -> ModelConfigOut:
    item = model_config_service.create_model(db, payload)
    return model_config_service.to_out(item)


@router.get("/{model_id}", response_model=ModelConfigOut, summary="模型详情")
def get_model(model_id: str, db: DBSession) -> ModelConfigOut:
    return model_config_service.to_out(model_config_service.get_model(db, model_id))


@router.patch("/{model_id}", response_model=ModelConfigOut, summary="更新模型配置")
def update_model(model_id: str, payload: ModelConfigUpdate, db: DBSession) -> ModelConfigOut:
    item = model_config_service.update_model(db, model_id, payload)
    return model_config_service.to_out(item)


@router.delete("/{model_id}", response_model=MessageResponse, summary="删除模型配置")
def delete_model(model_id: str, db: DBSession) -> MessageResponse:
    model_config_service.delete_model(db, model_id)
    return MessageResponse(message="已删除模型配置")


@router.post("/{model_id}/default", response_model=ModelConfigOut, summary="设为默认模型")
def set_default(model_id: str, db: DBSession) -> ModelConfigOut:
    item = model_config_service.set_default(db, model_id)
    return model_config_service.to_out(item)


@router.post("/test", response_model=ModelTestResult, summary="测试模型连通性")
async def test_model(payload: ModelTestRequest, db: DBSession) -> ModelTestResult:
    return await model_config_service.run_test(db, payload)
