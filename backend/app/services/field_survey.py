"""田野调查领域服务：用调查归档批号完成归档，并保留旧门类/旧批次号原件查阅。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.services.batch_registry import STATUS_MIGRATED, SURVEY_EXTRA_FIELDS, registry


class FieldSurveyService(BaseModuleService):
    MODULE = "field_survey"
    ENTITY = "调查记录"
    OPERATION_TERM = "归档调查"
    LIST_FIELDS = ["调查地点", "调查日期", "访谈对象", "采集素材", "登记编号", "负责人", "生效版本", "备注说明"]
    EXTRA_FIELDS = SURVEY_EXTRA_FIELDS
    REQUIRED_FIELDS = ["调查地点", "调查日期", "访谈对象"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"归档调查": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []

    # ── 归档 ────────────────────────────────────────────────────

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """通用动作入口：归档调查仍必须落到一个已核实的批次上。"""
        if action != "归档调查":
            return super().run_action(entry_id, action)
        survey = self.get_entry(entry_id)
        if survey is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"
        archive_number = str(survey.get("调查归档批号") or "").strip()
        if archive_number:
            return self.archive(entry_id, {"调查归档批号": archive_number})
        category = None
        if survey.get("关联门类ID"):
            category = next(
                (row for row in registry.batches()
                 if row.get("id") == survey.get("关联门类ID")),
                None,
            )
        if category is not None and category.get("调查归档批号"):
            return self.archive(
                entry_id, {"调查归档批号": category["调查归档批号"]})
        legacy_number = (
            survey.get("源门类登记编号")
            or survey.get("归档原编号")
            or _category_original_number(survey.get("关联门类ID"))
        )
        return self.archive(entry_id, {"原编号": legacy_number or ""})

    def archive(self, entry_id: int, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """实际归档：优先按调查归档批号定位门类批次，并抓取原组证据快照。

        没有可用批号（例如年度待补的存量批次）时不发放新号，只能用旧门类
        和旧批次号只读查阅；写入式归档会被拒绝。
        """
        survey = self.get_entry(entry_id)
        if survey is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"
        if survey.get("status") == "已撤回":
            return None, "已撤回的调查记录不能归档"

        archive_number = str(payload.get("调查归档批号") or "").strip()
        legacy_number = str(payload.get("原编号") or "").strip()
        category: dict[str, Any] | None = None

        if archive_number:
            category = registry.find_by_archive_number(archive_number)
            if category is None:
                return None, f"调查归档批号 {archive_number} 未发放或不存在"
        if category is None and legacy_number:
            category = registry.find_by_legacy_number(legacy_number)
            if category is not None and not category.get("调查归档批号"):
                return None, (
                    f"原编号 {legacy_number} 的批次年度无法确认，尚无调查归档批号，"
                    "只能按旧门类与旧批次号查阅，不能写入归档"
                )

        if category is not None:
            if category.get("迁移状态") != STATUS_MIGRATED or not category.get("调查归档批号"):
                return None, "该门类批次尚未完成年度核实，不能用于实际归档"
            if archive_number and category.get("调查归档批号") != archive_number:
                return None, "调查归档批号与门类批次不一致"
            survey["关联门类ID"] = category.get("id")
            survey["门类名称"] = category.get("门类名称", "")
            survey["申报批次"] = category.get("申报批次", "")
            survey["调查归档批号"] = category.get("调查归档批号", "")
            survey["源门类登记编号"] = category.get("登记编号", "")
            survey["归档证据"] = self._collect_evidence(category)
        else:
            # 兼容旧归档流程：没有指向新批次时按记录自身编号归入旧卷。
            if not legacy_number:
                return None, "归档必须提供有效的调查归档批号，或按旧编号补档"
            survey["归档原编号"] = legacy_number
            survey["归档证据"] = self._collect_evidence(None)

        survey["归档方式"] = "调查归档批号" if category is not None else "旧编号补档"
        survey["归档时间"] = _now_text()
        survey["status"] = "已确认"
        survey["pending"] = False
        survey["abnormal"] = False
        return survey, f"{self.ENTITY}已归档，批号 {survey.get('调查归档批号') or legacy_number}"

    def _collect_evidence(self, category: dict[str, Any] | None) -> list[dict[str, Any]]:
        """重取原组证据：同一（年度, 批次）下已归档的调查记录。

        不能只看门类名称和批次标题，否则同名不同年度的批次会被并成一组。
        """
        if category is None:
            return []
        evidence: list[dict[str, Any]] = []
        for row in self.rows():
            if row is None or not row.get("归档时间"):
                continue
            if row.get("关联门类ID") == category.get("id"):
                pass
            elif row.get("关联门类ID"):
                continue
            elif not (
                row.get("门类名称") == category.get("门类名称")
                and row.get("申报批次") == category.get("申报批次")
                and row.get("调查归档批号") in ("", category.get("调查归档批号"))
            ):
                continue
            evidence.append({
                "调查记录ID": row.get("id"),
                "登记编号": row.get("登记编号"),
                "调查地点": row.get("调查地点"),
                "归档时间": row.get("归档时间"),
            })
        return evidence

    def rows(self) -> list[dict[str, Any]]:
        from app.store import store
        return store.rows(self.MODULE)

    # ── 只读查阅 ────────────────────────────────────────────────

    def legacy_lookup(
        self,
        *,
        category_name: str | None = None,
        legacy_batch: str | None = None,
        year: str | None = None,
        original_number: str | None = None,
        archive_number: str | None = None,
    ) -> dict[str, Any]:
        """按旧门类/旧批次号或新归档批号查已归档原件，新旧定位互不覆盖。

        同名门类即使申报批次标题相同，也按（年度, 批次）分别成组返回，
        不会因为标题相同而并成一批。
        """
        batches = registry.match_batches(
            category_name=category_name,
            legacy_batch=legacy_batch,
            year=year,
            original_number=original_number,
            archive_number=archive_number,
        )
        batch_ids = {row.get("id") for row in batches}
        groups: list[dict[str, Any]] = []
        all_archives: list[dict[str, Any]] = []
        for batch in batches:
            archives: list[dict[str, Any]] = []
            for row in self.rows():
                if row.get("status") != "已确认" or not row.get("归档时间"):
                    continue
                matched = row.get("关联门类ID") == batch.get("id")
                if not matched and len(batches) == 1 and not row.get("关联门类ID"):
                    matched = (
                        row.get("门类名称") == batch.get("门类名称")
                        and row.get("申报批次") == batch.get("申报批次")
                    )
                if matched and row not in archives:
                    archives.append(dict(row))
            all_archives.extend(item for item in archives if item not in all_archives)
            groups.append({
                "门类ID": batch.get("id"),
                "门类名称": batch.get("门类名称"),
                "申报批次": batch.get("申报批次"),
                "年度": batch.get("年度"),
                "申报批次标识": batch.get("申报批次标识"),
                "调查归档批号": batch.get("调查归档批号"),
                "原编号": batch.get("登记编号"),
                "迁移状态": batch.get("迁移状态"),
                "archives": archives,
            })
        # 纯旧编号补档、没有关联到新批次的归档也一并返回。
        if original_number and batch_ids:
            legacy = str(original_number).strip()
            for row in self.rows():
                if row.get("归档原编号") != legacy:
                    continue
                if row.get("status") != "已确认" or not row.get("归档时间"):
                    continue
                if dict(row) not in all_archives:
                    all_archives.append(dict(row))
        return {
            "ok": True,
            "batches": groups,
            "archives": all_archives,
            "total": len(all_archives),
        }

    def locators(self, entry_id: int) -> dict[str, Any] | None:
        """列出某条调查可用的批号与原始编号，验证二者能否分别定位。"""
        survey = self.get_entry(entry_id)
        if survey is None:
            return None
        archive_number = survey.get("调查归档批号") or ""
        by_archive = registry.match_batches(archive_number=archive_number) if archive_number else []
        legacy_number = survey.get("归档原编号") or survey.get("源门类登记编号") or survey.get("登记编号")
        by_legacy = registry.match_batches(original_number=legacy_number) if legacy_number else []
        return {
            "entry": survey,
            "调查归档批号": archive_number,
            "原编号": legacy_number,
            "按归档批号定位": by_archive,
            "按原编号定位": by_legacy,
            "分别可定位": (
                bool(archive_number) and bool(by_archive)
                and bool(legacy_number) and bool(by_legacy)
                and by_archive[0].get("id") == by_legacy[0].get("id")
            ),
        }


def _now_text() -> str:
    from datetime import datetime
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _category_original_number(category_id: Any) -> str:
    for row in registry.batches():
        if row.get("id") == category_id:
            return str(row.get("登记编号") or "")
    return ""
