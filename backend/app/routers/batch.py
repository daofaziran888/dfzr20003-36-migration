"""申报批次迁移与调查归档路由：固定路径先于通用资源路由注册。

覆盖迁移、年度补正、批号发放、新旧双读、归档写入、归档原件查阅，以及
新版界面停用开关。停用新版界面只收起新入口，旧编号查阅始终可用。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import service_for
from app.services.batch_registry import registry

router = APIRouter(prefix="/api", tags=["申报批次与调查归档"])


class CorrectYearPayload(BaseModel):
    年度: str = ""
    依据: str = ""


class ArchivePayload(BaseModel):
    调查归档批号: str = ""
    原编号: str = ""


class BatchUIStatePayload(BaseModel):
    enabled: bool = True


def _survey_service():
    service = service_for("field_survey")
    if service is None:
        raise HTTPException(status_code=500, detail="田野调查服务未注册")
    return service


# ── 批次迁移与补正 ──────────────────────────────────────────────

@router.get("/batch-category/batches")
def batch_summary() -> dict[str, Any]:
    service = service_for("craft_category")
    return service.batch_summary()  # type: ignore[union-attr]


@router.post("/batch-category/migrate")
def migrate_batches() -> dict[str, Any]:
    return registry.run_migration()


@router.get("/batch-category/corrections")
def list_corrections() -> dict[str, Any]:
    return {"items": registry.corrections(), "total": len(registry.corrections())}


@router.post("/batch-category/{category_id}/correct-year")
def correct_year(category_id: int, payload: CorrectYearPayload) -> dict[str, Any]:
    result = registry.correct_year(category_id, payload.年度, payload.依据)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/batch-category/lookup")
def batch_lookup(
    门类名称: str | None = Query(default=None),
    申报批次: str | None = Query(default=None),
    年度: str | None = Query(default=None),
    原编号: str | None = Query(default=None),
    调查归档批号: str | None = Query(default=None),
) -> dict[str, Any]:
    items = registry.match_batches(
        category_name=门类名称,
        legacy_batch=申报批次,
        year=年度,
        original_number=原编号,
        archive_number=调查归档批号,
    )
    return {"items": items, "total": len(items)}


# ── 新版界面开关 ────────────────────────────────────────────────

@router.get("/batch-ui")
def batch_ui_state() -> dict[str, Any]:
    return {"new_ui_enabled": registry.new_ui_enabled}


@router.post("/batch-ui")
def set_batch_ui(payload: BatchUIStatePayload) -> dict[str, Any]:
    return registry.set_new_ui(payload.enabled)


# ── 田野调查归档与查阅 ──────────────────────────────────────────

@router.post("/field_survey/{entry_id}/archive")
def archive_survey(entry_id: int, payload: ArchivePayload) -> dict[str, Any]:
    entry, message = _survey_service().archive(
        entry_id, {"调查归档批号": payload.调查归档批号, "原编号": payload.原编号})
    if entry is None:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "entry": entry}


@router.get("/field_survey/{entry_id}/locators")
def survey_locators(entry_id: int) -> dict[str, Any]:
    result = _survey_service().locators(entry_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"调查记录 {entry_id} 不存在")
    return result


@router.get("/field_survey/archive-lookup")
def archive_lookup(
    门类名称: str | None = Query(default=None),
    申报批次: str | None = Query(default=None),
    年度: str | None = Query(default=None),
    原编号: str | None = Query(default=None),
    调查归档批号: str | None = Query(default=None),
) -> dict[str, Any]:
    return _survey_service().legacy_lookup(
        category_name=门类名称,
        legacy_batch=申报批次,
        year=年度,
        original_number=原编号,
        archive_number=调查归档批号,
    )
