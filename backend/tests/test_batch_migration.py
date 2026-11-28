"""申报批次迁移与调查归档测试：年度区分、缺年不发放、补正、新旧双读、停用新版界面。

场景：藤编门类有两份「秋季申报」存量记录，一条带年度（2023），一条缺年份
（草稿）；专员有一份新版上线前未提交的调查归档（id=4）；档案员在窗口内为
缺年的记录补上带依据的年度。另有一条 2023 年已归档的旧调查（id=5）。
"""
from __future__ import annotations

import copy

import pytest

from app.seed import SEED_ROWS
from app.services import service_for
from app.services.batch_registry import registry
from app.store import store


@pytest.fixture(autouse=True)
def clean_batches():
    """每个用例都从种子数据重新开始，避免补正/归档互相污染。"""
    for module in ("craft_category", "field_survey"):
        store._tables[module] = [copy.deepcopy(row) for row in SEED_ROWS[module]]
    registry._corrections.clear()
    registry.set_new_ui(True)
    yield


@pytest.fixture()
def migrated():
    result = registry.run_migration()
    assert result["ok"] is True
    return result


def _藤编() -> list[dict]:
    return [
        row for row in store.rows("craft_category")
        if row.get("门类名称") == "藤编" and row.get("申报批次") == "秋季申报"
    ]


class TestBatchMigration:
    def test_same_title_different_year_not_merged(self, migrated):
        rows = _藤编()
        assert [row["id"] for row in rows] == [4, 5]
        migrated_rows = [row for row in rows if row.get("迁移状态") == "已迁移"]
        assert [row["年度"] for row in migrated_rows] == ["2023"]
        # 缺年的那条仍是独立审阅对象，没有因为标题相同被并进 2023 批。
        pending = [row for row in rows if row.get("迁移状态") == "待补年度"]
        assert [row["id"] for row in pending] == [5]

    def test_year_missing_batch_gets_no_writable_number(self, migrated):
        pending = store.find("craft_category", 5)
        assert pending["迁移状态"] == "待补年度"
        assert pending["年度"] == ""
        assert pending["申报批次标识"] == ""
        assert pending["调查归档批号"] == ""

    def test_confirmed_year_batch_gets_identifiers(self, migrated):
        row = store.find("craft_category", 4)
        assert row["年度"] == "2023"
        assert row["申报批次标识"] == "2023-秋季申报-01"
        assert row["调查归档批号"] == "DA-2023-001"

    def test_migration_idempotent(self, migrated):
        before = {
            row["id"]: (row["申报批次标识"], row["调查归档批号"])
            for row in store.rows("craft_category")
        }
        registry.run_migration()
        after = {
            row["id"]: (row["申报批次标识"], row["调查归档批号"])
            for row in store.rows("craft_category")
        }
        assert before == after

    def test_lookup_by_year_separates_batches(self, migrated):
        rows = registry.match_batches(category_name="藤编", legacy_batch="秋季申报", year="2023")
        assert [row["id"] for row in rows] == [4]


class TestYearCorrection:
    def test_correction_requires_basis(self, migrated):
        result = registry.correct_year(5, "2024", "")
        assert result["ok"] is False
        assert "依据" in result["message"]

    def test_correction_requires_valid_year(self, migrated):
        result = registry.correct_year(5, "待定", "访谈记录")
        assert result["ok"] is False

    def test_correction_issues_distinct_batch_number(self, migrated):
        result = registry.correct_year(5, "2024", "2023 年访谈与批复件互证，实为 2024 年秋季申报")
        assert result["ok"] is True
        row = store.find("craft_category", 5)
        assert row["迁移状态"] == "已迁移"
        assert row["年度"] == "2024"
        assert row["申报批次标识"] == "2024-秋季申报-01"
        assert row["调查归档批号"] == "DA-2024-001"
        assert row["年份补正依据"]
        # 与 2023 年同名批次编号不同，不能合并。
        assert row["申报批次标识"] != store.find("craft_category", 4)["申报批次标识"]

    def test_correction_idempotent(self, migrated):
        registry.correct_year(5, "2024", "依据一")
        first = (store.find("craft_category", 5)["申报批次标识"],
                 store.find("craft_category", 5)["调查归档批号"])
        result = registry.correct_year(5, "2024", "依据二")
        assert result["ok"] is True
        second = (store.find("craft_category", 5)["申报批次标识"],
                  store.find("craft_category", 5)["调查归档批号"])
        assert first == second

    def test_cannot_overwrite_confirmed_year(self, migrated):
        result = registry.correct_year(4, "2024", "其他依据")
        assert result["ok"] is False


class TestSurveyArchive:
    def test_archive_pending_year_survey_rejected(self, migrated):
        service = service_for("field_survey")
        entry, message = service.archive(6, {"调查归档批号": "", "原编号": "CRAF-0005"})
        assert entry is None
        assert "年度" in message
        assert store.find("field_survey", 6)["status"] == "草稿"

    def test_archive_with_batch_number(self, migrated):
        service = service_for("field_survey")
        entry, message = service.archive(4, {"调查归档批号": "DA-2023-001"})
        assert entry is not None
        assert entry["status"] == "已确认"
        assert entry["调查归档批号"] == "DA-2023-001"
        assert entry["关联门类ID"] == 4

    def test_archive_after_correction_uses_new_number(self, migrated):
        service = service_for("field_survey")
        registry.correct_year(5, "2024", "访谈记录")
        entry, message = service.archive(6, {"调查归档批号": "DA-2024-001"})
        assert entry is not None
        assert entry["调查归档批号"] == "DA-2024-001"
        assert entry["关联门类ID"] == 5

    def test_archive_with_unknown_batch_number_rejected(self, migrated):
        service = service_for("field_survey")
        entry, message = service.archive(4, {"调查归档批号": "DA-9999-001"})
        assert entry is None

    def test_archived_original_retrievable_by_old_number(self, migrated):
        service = service_for("field_survey")
        result = service.legacy_lookup(original_number="CRAF-0004")
        assert result["total"] >= 1
        assert any(row["id"] == 5 for row in result["archives"])
        assert [group["年度"] for group in result["batches"]] == ["2023"]

    def test_archived_evidence_does_not_cross_years(self, migrated):
        service = service_for("field_survey")
        registry.correct_year(5, "2024", "访谈记录")
        entry, _ = service.archive(6, {"调查归档批号": "DA-2024-001"})
        assert entry is not None
        ids = {item["调查记录ID"] for item in entry["归档证据"]}
        assert 5 not in ids, "2023 年批次的归档材料不应进入 2024 年批次的证据组"

    def test_locators_resolve_both_ways(self, migrated):
        service = service_for("field_survey")
        entry, _ = service.archive(4, {"调查归档批号": "DA-2023-001"})
        assert entry is not None
        locators = service.locators(4)
        assert locators is not None
        assert locators["调查归档批号"] == "DA-2023-001"
        assert locators["原编号"] == "CRAF-0004"
        assert locators["分别可定位"] is True

    def test_new_and_old_numbers_locate_separately(self, migrated):
        service = service_for("field_survey")
        by_new = service.legacy_lookup(archive_number="DA-2023-001")
        by_old = service.legacy_lookup(original_number="CRAF-0004")
        assert [group["门类ID"] for group in by_new["batches"]] == [4]
        assert [group["门类ID"] for group in by_old["batches"]] == [4]


class TestBatchUIFlag:
    def test_disable_new_ui_keeps_legacy_lookup(self, migrated):
        service = service_for("field_survey")
        registry.set_new_ui(False)
        try:
            assert registry.new_ui_enabled is False
            result = service.legacy_lookup(original_number="CRAF-0004")
            assert result["total"] >= 1
        finally:
            registry.set_new_ui(True)

    def test_disable_new_ui_does_not_block_archived_retrieval(self, migrated):
        service = service_for("field_survey")
        service.archive(4, {"调查归档批号": "DA-2023-001"})
        registry.set_new_ui(False)
        try:
            result = service.legacy_lookup(original_number="CRAF-0004")
            assert {row["id"] for row in result["archives"]} >= {4, 5}
        finally:
            registry.set_new_ui(True)


class TestGenericAction:
    """表格里的「归档调查」按钮也要走同一套批次规则。"""

    def test_generic_archive_uses_resolved_batch(self, migrated):
        service = service_for("field_survey")
        entry, message = service.run_action(4, "归档调查")
        assert entry is not None
        assert entry["调查归档批号"] == "DA-2023-001"

    def test_generic_archive_rejected_for_pending_year(self, migrated):
        service = service_for("field_survey")
        entry, message = service.run_action(6, "归档调查")
        assert entry is None
        assert "年度" in message
        assert store.find("field_survey", 6)["status"] == "草稿"
