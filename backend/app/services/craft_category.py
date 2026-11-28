"""技艺分类领域服务：门类申报批次迁移到含年度与批次的标识，并发放调查归档批号。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.services.batch_registry import CATEGORY_EXTRA_FIELDS, STATUS_MIGRATED, registry


class CraftCategoryService(BaseModuleService):
    MODULE = "craft_category"
    ENTITY = "技艺门类"
    OPERATION_TERM = "核定门类"
    LIST_FIELDS = ["门类名称", "所属级别", "申报批次", "保护单位", "登记编号", "负责人", "生效版本", "备注说明"]
    EXTRA_FIELDS = CATEGORY_EXTRA_FIELDS
    REQUIRED_FIELDS = ["门类名称", "所属级别", "申报批次"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"核定门类": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        entry, missing = super().create_entry(values)
        if entry is not None:
            # 新登记的门类同样进入迁移流程：有年度才发新标识和归档批号。
            entry["年度"] = values.get("年度") or ""
            entry["申报批次标识"] = ""
            entry["调查归档批号"] = ""
            entry["迁移状态"] = "待迁移"
            registry.run_migration()
        return entry, missing

    def list_entries(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        # 读取列表前先保证存量记录已补齐迁移字段，部署窗口内旧名称照常展示。
        registry.ensure_fields()
        return super().list_entries(**kwargs)

    def batch_summary(self) -> dict[str, Any]:
        rows = registry.batches()
        return {
            "total": len(rows),
            "migrated": sum(1 for row in rows if row.get("迁移状态") == STATUS_MIGRATED),
            "need_year": sum(1 for row in rows if row.get("迁移状态") == "待补年度"),
            "items": rows,
        }
