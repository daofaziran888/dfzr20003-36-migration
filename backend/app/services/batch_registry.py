"""门类申报批次的迁移登记册。

旧系统里的「申报批次」是自由录入的名称（例如「秋季申报」），同名门类在不
同年度无法区分。迁移后每个已核实的批次会得到：

* ``申报批次标识``：``年度-批次名称-序号``，例如 ``2023-秋季申报-01``；
* ``调查归档批号``：发给田野调查做实际归档的批号，例如 ``DA-2023-001``。

部署窗口内旧名称 ``申报批次`` 继续保留，旧编号也继续可查。年度无法确认的
存量批次只标记为「待补年度」，不会自动得到可写入的新批次编号；必须由档案员
提交带依据的年份补正后才发放。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.store import store

CATEGORY = "craft_category"
SURVEY = "field_survey"

YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

CATEGORY_EXTRA_FIELDS = [
    "年度",
    "迁移状态",
    "年份补正依据",
    "年份补正时间",
]
CATEGORY_MIGRATION_FIELDS = ["申报批次标识", "调查归档批号"]

SURVEY_EXTRA_FIELDS = [
    "关联门类ID",
    "门类名称",
    "申报批次",
    "调查归档批号",
    "归档原编号",
    "源门类登记编号",
    "归档证据",
    "归档时间",
    "归档方式",
]

STATUS_MIGRATED = "已迁移"
STATUS_NEED_YEAR = "待补年度"
STATUS_PENDING = "待迁移"


def parse_year(value: Any) -> str | None:
    """从「2023」「2023年」「2023-秋季申报」等文本里取出四位年度。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = YEAR_RE.search(text)
    if match is None:
        return None
    year = int(match.group(1))
    if 1900 <= year <= 2100:
        return str(year)
    return None


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


class BatchRegistry:
    """批次迁移、补正、批号发放与旧号检索的唯一入口。"""

    def __init__(self) -> None:
        self._new_ui_enabled = True
        self._corrections: list[dict[str, Any]] = []
        self.ensure_fields()

    # ── 基础字段 ────────────────────────────────────────────────

    def ensure_fields(self) -> None:
        """给存量记录补齐迁移字段，不改动已有值。"""
        for row in store.rows(CATEGORY):
            row.setdefault("年度", "")
            row.setdefault("申报批次标识", "")
            row.setdefault("迁移状态", STATUS_PENDING)
            row.setdefault("调查归档批号", "")
            row.setdefault("年份补正依据", "")
            row.setdefault("年份补正时间", "")
        for row in store.rows(SURVEY):
            row.setdefault("关联门类ID", None)
            row.setdefault("门类名称", "")
            row.setdefault("申报批次", "")
            row.setdefault("调查归档批号", "")
            row.setdefault("归档原编号", "")
            row.setdefault("源门类登记编号", "")
            row.setdefault("归档证据", [])
            row.setdefault("归档时间", "")
            row.setdefault("归档方式", "")

    # ── 编号生成 ────────────────────────────────────────────────

    def _batch_label(self, row: dict[str, Any]) -> str:
        return str(row.get("申报批次") or "未命名批次").strip()

    def _next_identifier(self, year: str, label: str, exclude_id: int | None = None) -> str:
        ordinal = 1
        used = {
            str(row.get("申报批次标识") or "")
            for row in store.rows(CATEGORY)
            if row.get("id") != exclude_id
        }
        while f"{year}-{label}-{ordinal:02d}" in used:
            ordinal += 1
        return f"{year}-{label}-{ordinal:02d}"

    def _next_archive_number(self, year: str) -> str:
        used = {
            str(row.get("调查归档批号") or "")
            for row in store.rows(CATEGORY)
        }
        prefix = f"DA-{year}-"
        ordinal = 1
        while f"{prefix}{ordinal:03d}" in used:
            ordinal += 1
        return f"{prefix}{ordinal:03d}"

    # ── 迁移 ────────────────────────────────────────────────────

    def run_migration(self) -> dict[str, Any]:
        """把存量门类迁移到「年度 + 批次」标识；重复执行结果不变。"""
        self.ensure_fields()
        migrated = 0
        need_year = 0
        for row in store.rows(CATEGORY):
            explicit_year = parse_year(row.get("年度"))
            inferred_year = explicit_year or parse_year(row.get("申报批次"))
            if inferred_year:
                row["年度"] = inferred_year
                if not row.get("申报批次标识"):
                    row["申报批次标识"] = self._next_identifier(
                        inferred_year, self._batch_label(row), row.get("id"))
                if not row.get("调查归档批号"):
                    row["调查归档批号"] = self._next_archive_number(inferred_year)
                row["迁移状态"] = STATUS_MIGRATED
                migrated += 1
            else:
                # 年度无法确认：保留旧名称供查阅，但不发放可写入的新编号。
                row["年度"] = ""
                row["申报批次标识"] = ""
                row["调查归档批号"] = ""
                row["迁移状态"] = STATUS_NEED_YEAR
                need_year += 1
        return {
            "ok": True,
            "total": len(store.rows(CATEGORY)),
            "migrated": migrated,
            "need_year": need_year,
            "message": f"申报批次迁移完成：已迁移 {migrated} 条，待补年度 {need_year} 条",
        }

    def correct_year(self, category_id: int, year: Any, basis: Any) -> dict[str, Any]:
        """档案员为缺年度的存量批次补上带依据的年份。"""
        row = store.find(CATEGORY, category_id)
        if row is None:
            return {"ok": False, "message": f"技艺门类 {category_id} 不存在"}
        normalized = parse_year(year)
        if normalized is None:
            return {"ok": False, "message": "年份补正必须填写四位年度"}
        basis_text = str(basis or "").strip()
        if not basis_text:
            return {"ok": False, "message": "年份补正必须附上可核查的依据"}

        current = parse_year(row.get("年度"))
        if current and current != normalized:
            return {
                "ok": False,
                "message": f"该批次年度已确认为 {current}，不能覆盖为 {normalized}",
            }
        if current == normalized and row.get("迁移状态") == STATUS_MIGRATED:
            return {
                "ok": True,
                "message": f"该批次年度已是 {normalized}，无需重复补正",
                "entry": row,
                "idempotent": True,
            }

        row["年度"] = normalized
        row["年份补正依据"] = basis_text
        row["年份补正时间"] = _now()
        row["迁移状态"] = STATUS_PENDING
        row["申报批次标识"] = ""
        row["调查归档批号"] = ""
        self.run_migration()
        self._corrections.append({
            "门类ID": category_id,
            "年度": normalized,
            "依据": basis_text,
            "补正时间": row["年份补正时间"],
            "申报批次标识": row.get("申报批次标识", ""),
            "调查归档批号": row.get("调查归档批号", ""),
        })
        return {
            "ok": True,
            "message": (
                f"年份补正已登记，批次标识 {row.get('申报批次标识')}，"
                f"调查归档批号 {row.get('调查归档批号')}"
            ),
            "entry": row,
            "idempotent": False,
        }

    # ── 查询 ────────────────────────────────────────────────────

    def batches(self) -> list[dict[str, Any]]:
        self.ensure_fields()
        return [dict(row) for row in store.rows(CATEGORY)]

    def find_by_archive_number(self, archive_number: Any) -> dict[str, Any] | None:
        text = str(archive_number or "").strip()
        if not text:
            return None
        for row in store.rows(CATEGORY):
            if str(row.get("调查归档批号") or "").strip() == text:
                return row
        return None

    def find_by_legacy_number(self, original_number: Any) -> dict[str, Any] | None:
        text = str(original_number or "").strip()
        if not text:
            return None
        for row in store.rows(CATEGORY):
            if str(row.get("登记编号") or "").strip() == text:
                return row
        return None

    def match_batches(
        self,
        *,
        category_name: str | None = None,
        legacy_batch: str | None = None,
        year: str | None = None,
        original_number: str | None = None,
        archive_number: str | None = None,
    ) -> list[dict[str, Any]]:
        """按新旧标识查找门类批次，同名不同年度分别返回，不做合并。"""
        name = str(category_name or "").strip()
        batch = str(legacy_batch or "").strip()
        year_text = parse_year(year)
        rows = list(store.rows(CATEGORY))

        if archive_number:
            number = str(archive_number).strip()
            rows = [r for r in rows if str(r.get("调查归档批号") or "") == number]
        if original_number:
            legacy = str(original_number).strip()
            rows = [r for r in rows if str(r.get("登记编号") or "") == legacy]
        if name:
            rows = [r for r in rows if str(r.get("门类名称") or "") == name]
        if batch:
            rows = [r for r in rows if self._batch_label(r) == batch]
        if year_text:
            rows = [r for r in rows if parse_year(r.get("年度")) == year_text]
        return rows

    # ── 新版界面开关 ────────────────────────────────────────────

    @property
    def new_ui_enabled(self) -> bool:
        return self._new_ui_enabled

    def set_new_ui(self, enabled: bool) -> dict[str, Any]:
        self._new_ui_enabled = bool(enabled)
        return {
            "ok": True,
            "new_ui_enabled": self._new_ui_enabled,
            "message": "新版批次界面已启用" if self._new_ui_enabled else "新版批次界面已停用，旧编号查阅保持可用",
        }

    def corrections(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._corrections]


registry = BatchRegistry()
