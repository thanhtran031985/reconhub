"""Tests cho UI wizard chạy bộ + kết quả — Bước 9 task 18 (test viết trước).

Hàm render thuần + bộ lọc lịch sử theo lần chạy bộ. Fixture DB theo mẫu
tests/unit/test_batch_def_service.py.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import dash_mantine_components as dmc
import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def batch_env(tmp_path, monkeypatch):
    db_path = tmp_path / "batch_run_pages.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.batch_def",
        "app.services.batch_run",
        "app.services.run_service",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [(1, "admin"), (2, "owner"), (3, "operator"), (4, "viewer")]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["TEMPLATE_OWNER"], 3: ["OPERATOR"], 4: ["VIEWER"]})
    clear_perm_cache()
    return engine


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


def _texts(comp) -> list[str]:
    out: list[str] = []
    if isinstance(comp, str):
        out.append(comp)
    elif isinstance(comp, (list, tuple)):
        for c in comp:
            out.extend(_texts(c))
    elif hasattr(comp, "children"):
        out.extend(_texts(comp.children))
    return out


def _find_all(comp, typ) -> list:
    found: list = []
    if isinstance(comp, typ):
        found.append(comp)
    children = getattr(comp, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            found.extend(_find_all(c, typ))
    elif children is not None:
        found.extend(_find_all(children, typ))
    return found


def _run(items, files=None, status="DRAFT"):
    return {
        "id": 1,
        "batch_def_id": 1,
        "def_code": "DOANH_THU",
        "def_name": "Doanh thu",
        "name": "Tháng 2/2026",
        "period": "2026-02",
        "period_from": "2026-02-01T00:00:00",
        "period_to": "2026-02-28T23:59:59",
        "status": status,
        "cnt_items": len(items),
        "cnt_done": 0,
        "cnt_failed": 0,
        "cnt_skipped": 0,
        "cnt_not_run": 0,
        "created_by": "admin",
        "created_at": "2026-02-01T10:00:00",
        "items": items,
        "files": files or [],
    }


def _item(**kw):
    d = {
        "id": 1,
        "template_id": 1,
        "template_code": "DTP_TMPL",
        "template_name": "DTP",
        "template_version": 1,
        "profile_code": "BY_DAY_POINT",
        "data_source_id": 1,
        "multi_file": "N",
        "is_required": "Y",
        "status": "PENDING",
        "skip_reason": None,
        "params_run_override": {},
        "params_resolved": {
            "p_from": "2026-02-01T00:00:00",
            "p_to": "2026-02-28T23:59:59",
            "p_ky": "202602",
        },
        "precheck": None,
        "current_run_id": None,
        "attempt_no": 1,
        "files": [],
    }
    d.update(kw)
    return d


def _file(**kw):
    d = {
        "id": 1,
        "batch_run_item_id": 1,
        "file_id": 1,
        "original_name": "dtp_02.xlsx",
        "normalized_name": "DTP02XLSX",
        "match_state": "MATCHED",
        "match_by": "PATTERN",
        "candidate_item_ids": [],
    }
    d.update(kw)
    return d


class TestItemMatchText:
    def test_required_missing_file(self):
        from app.ui.pages.batch_run_wizard import item_match_text

        assert item_match_text(_item()) == "Thiếu file bắt buộc"

    def test_optional_missing_file(self):
        from app.ui.pages.batch_run_wizard import item_match_text

        assert item_match_text(_item(is_required="N")) == "Tùy chọn sẽ bỏ qua"

    def test_matched_single(self):
        from app.ui.pages.batch_run_wizard import item_match_text

        assert item_match_text(_item(files=[_file()])) == "Đã ghép"

    def test_matched_multi_merged(self):
        from app.ui.pages.batch_run_wizard import item_match_text

        assert (
            item_match_text(_item(multi_file="Y", files=[_file(id=1), _file(id=2, original_name="b.xlsx")]))
            == "Gộp 2 file"
        )

    def test_matched_multi_not_allowed(self):
        from app.ui.pages.batch_run_wizard import item_match_text

        assert item_match_text(_item(files=[_file(id=1), _file(id=2, original_name="b.xlsx")])) == "Chỉ nhận 1 file"

    def test_skipped_reasons(self):
        from app.ui.pages.batch_run_wizard import item_match_text

        assert (
            item_match_text(_item(status="SKIPPED", skip_reason="TEMPLATE_ARCHIVED")) == "Bỏ qua: template đã lưu trữ"
        )
        assert item_match_text(_item(status="SKIPPED", skip_reason="USER_SKIP")) == "Bỏ qua tháng này"
        assert item_match_text(_item(status="SKIPPED", skip_reason="NO_FILE")) == "Bỏ qua: không có file"


class TestWizardBlockers:
    def test_unresolved_file_blocks(self):
        from app.ui.pages.batch_run_wizard import wizard_blockers

        run = _run([_item()], files=[_file(id=9, match_state="UNMATCHED", batch_run_item_id=None)])
        blockers = wizard_blockers(run)
        assert any("không khớp mục nào" in b for b in blockers)

    def test_ambiguous_file_blocks(self):
        from app.ui.pages.batch_run_wizard import wizard_blockers

        run = _run(
            [_item()],
            files=[_file(id=9, match_state="AMBIGUOUS", batch_run_item_id=None, candidate_item_ids=[1, 2])],
        )
        assert any("khớp nhiều mục" in b for b in wizard_blockers(run))

    def test_clean_run_no_blockers(self):
        from app.ui.pages.batch_run_wizard import wizard_blockers

        run = _run([_item(files=[_file()])], files=[_file()])
        assert wizard_blockers(run) == []


class TestDecodeUploads:
    def test_valid_contents(self):
        from app.ui.pages.batch_run_wizard import decode_uploads

        payload = base64.b64encode(b"hello").decode()
        files, errors = decode_uploads([f"data:application/octet-stream;base64,{payload}"], ["a.xlsx"])
        assert errors == []
        assert files == [{"filename": "a.xlsx", "content": b"hello"}]

    def test_invalid_contents_reported(self):
        from app.ui.pages.batch_run_wizard import decode_uploads

        files, errors = decode_uploads(["not-a-data-url"], ["a.xlsx"])
        assert files == []
        assert len(errors) == 1


class TestRenderSteps:
    def test_step2_shows_match_table(self):
        from app.ui.pages.batch_run_wizard import render_step_content

        node = render_step_content(2, _run([_item(files=[_file()])], files=[_file()]))
        texts = _texts(node)
        assert "Đã ghép" in texts
        assert "DTP_TMPL" in texts

    def test_step2_shows_unmatched_block(self):
        from app.ui.pages.batch_run_wizard import render_step_content

        node = render_step_content(
            2, _run([_item()], files=[_file(id=9, match_state="UNMATCHED", batch_run_item_id=None)])
        )
        texts = _texts(node)
        assert "File chưa ghép được" in texts
        assert "Không khớp" in texts

    def test_step3_shows_params_and_override_badge(self):
        from app.ui.pages.batch_run_wizard import render_step_content

        item = _item(files=[_file()], params_run_override={"p_ky": "202603"})
        node = render_step_content(3, _run([item], files=[_file()]))
        inputs = _find_all(node, dmc.TextInput)
        values = [i.value for i in inputs]
        assert "202603" in values
        assert "2026-02-01T00:00:00" in values
        assert "Đã sửa" in _texts(node)

    def test_step3_empty_when_no_files(self):
        from app.ui.pages.batch_run_wizard import render_step_content

        node = render_step_content(3, _run([_item()]))
        assert "Chưa có mục nào có file" in _texts(node)

    def test_step4_shows_precheck_kpis_and_checks(self):
        from app.ui.pages.batch_run_wizard import render_step_content

        item = _item(
            status="WARN",
            files=[_file()],
            precheck={
                "checks": [
                    {"key": "control_total", "level": "warn", "message": "Control total lệch ở file: a.xlsx."},
                    {"key": "files", "level": "ok", "message": "Đọc được 1 file, 200 dòng hợp lệ."},
                ]
            },
        )
        node = render_step_content(4, _run([item], files=[_file()]))
        texts = _texts(node)
        assert "Cảnh báo" in texts
        assert "Control total lệch ở file: a.xlsx." in texts
        assert "Chạy 1 template" in texts

    def test_step5_shows_progress_and_run_link(self):
        from app.ui.pages.batch_run_wizard import render_step_content

        item = _item(status="DONE", files=[_file()], current_run_id=42)
        node = render_step_content(5, _run([item], files=[_file()], status="DONE"))
        texts = _texts(node)
        assert "Run #42" in texts
        assert "Xem kết quả" in texts

    def test_header_shows_archived_warning(self):
        from app.ui.pages.batch_run_wizard import render_wizard_header

        item = _item(status="SKIPPED", skip_reason="TEMPLATE_ARCHIVED")
        node = render_wizard_header(_run([item]))
        # alert_box hiển thị tiêu đề qua prop title, nội dung qua children.
        assert "Các mục sau sẽ bị bỏ qua khi chạy: DTP_TMPL." in _texts(node)


class TestResultRender:
    def _matrix(self, **row_kw):
        row = {
            "item_id": 1,
            "template_id": 1,
            "template_code": "DTP_TMPL",
            "template_name": "DTP",
            "file_count": 1,
            "status": "DONE",
            "skip_reason": None,
            "current_run_id": 42,
            "attempt_no": 1,
            "main_measure": "THANH_TIEN",
            "excel_total": 1000.0,
            "db_total": 900.0,
            "diff_total": 100.0,
            "cnt_matched": 9,
            "cnt_mismatch": 1,
            "cnt_missing_in_db": 0,
            "cnt_missing_in_excel": 0,
            "match_rate": 0.9,
            "prev_match_rate": 0.8,
            "match_rate_delta": 0.1,
            "checked_by": None,
        }
        row.update(row_kw)
        return {
            "run": {"id": 1, "period": "2026-02", "name": "Tháng 2/2026", "created_by": "admin"},
            "def_code": "DOANH_THU",
            "def_name": "Doanh thu",
            "total_items": 1,
            "kpis": {
                "items_with_results": 1,
                "all_matched_items": 0,
                "mismatch_items": 1,
                "mismatch_total_diff": 100.0,
                "error_items": 0,
                "skipped_items": 0,
            },
            "rows": [row],
        }

    def test_matrix_table_shows_totals_and_delta(self):
        from app.ui.pages.batch_run_result import render_matrix_table

        node = render_matrix_table(self._matrix())
        texts = _texts(node)
        assert "1.000" in texts
        assert "900" in texts
        assert "90.0%" in texts
        assert "+10.0 điểm %" in texts
        assert "Mở run" in texts

    def test_matrix_table_failed_row_has_rerun(self):
        from app.ui.pages.batch_run_result import render_matrix_table

        node = render_matrix_table(self._matrix(status="FAILED"))
        assert "Chạy lại" in _texts(node)

    def test_result_header_and_kpis(self):
        from app.ui.pages.batch_run_result import render_result_header, render_result_kpis

        data = self._matrix()
        # _texts trả danh sách chuỗi theo từng phần tử; nối lại để so khớp chuỗi con.
        assert "1/1 mục có kết quả" in " ".join(_texts(render_result_header(data)))
        assert "100" in " ".join(_texts(render_result_kpis(data["kpis"])))


class TestHistoryBatchChip:
    def _history_item(self, **kw):
        d = {
            "id": 7,
            "template_id": 1,
            "template_code": "DTP_TMPL",
            "template_name": "DTP",
            "template_version": 1,
            "profile_code": "BY_DAY_POINT",
            "status": "DONE",
            "progress_pct": 100,
            "created_by": "admin",
            "created_at": "2026-02-10T09:00:00",
            "checked_at": None,
            "checked_by": None,
            "temp_purged_at": None,
            "p_from": "2026-02-01T00:00:00",
            "p_to": "2026-02-28T23:59:59",
            "file_id": 5,
            "filename": "dtp.xlsx",
            "file_size": 12345,
            "cnt_matched": 10,
            "cnt_mismatch": 0,
            "cnt_missing_in_db": 0,
            "cnt_missing_in_excel": 0,
            "match_pct": 100.0,
            "batch_run_id": None,
            "batch_def_code": None,
        }
        d.update(kw)
        return d

    def test_batch_run_shows_def_chip(self):
        from app.ui.pages.history import render_runs_table

        node = render_runs_table(
            [self._history_item(batch_run_id=3, batch_def_code="DOANH_THU")],
            is_admin=False,
            selected_ids=set(),
            total=1,
            current_page=1,
            page_size=20,
            total_pages=1,
        )
        assert "Bộ DOANH_THU" in _texts(node)

    def test_single_run_has_no_chip(self):
        from app.ui.pages.history import render_runs_table

        node = render_runs_table(
            [self._history_item()],
            is_admin=False,
            selected_ids=set(),
            total=1,
            current_page=1,
            page_size=20,
            total_pages=1,
        )
        assert "Bộ DOANH_THU" not in _texts(node)


class TestListRunsBatchFilter:
    def _setup(self, engine, admin_ctx):
        from app.services.batch_def import (
            activate_batch_def,
            add_batch_def_items,
            create_batch_def,
        )
        from app.services.batch_run import create_batch_run

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with engine.begin() as conn:
            ds_id = conn.execute(
                text(
                    "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, HOST, "
                    "PORT, SERVICE_NAME, CALL_TIMEOUT_S, MAX_ROWS, IS_ACTIVE, "
                    "IS_CURRENT_METADATA, CREATED_BY, CREATED_AT, UPDATED_AT) VALUES "
                    "('ORACLE_TEST', 'DEV', 'SOURCE', 'ORACLE', 'localhost', 1521, 'XE', "
                    "600, 1000000, 'Y', 'N', 'admin', :now, :now)"
                ),
                {"now": now},
            ).lastrowid
            cfg = json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
            cfg["db_source"]["params"] = [
                {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
                {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
                {"name": "p_ky", "type": "text", "source": "user", "label": "Kỳ", "required": True},
                {"name": "p_so", "type": "number", "source": "user", "label": "Số", "required": False},
            ]
            tmpl_id = conn.execute(
                text(
                    "INSERT INTO RECON_TEMPLATE (CODE, NAME, OWNER, STATUS, CURRENT_VERSION, "
                    "CREATED_AT, UPDATED_AT, ROW_VERSION) VALUES ('DTP_TMPL', 'DTP_TMPL', "
                    "'admin', 'ACTIVE', 1, :now, :now, 1)"
                ),
                {"now": now},
            ).lastrowid
            conn.execute(
                text(
                    "INSERT INTO RECON_TEMPLATE_VERSION (TEMPLATE_ID, VERSION, STATUS, "
                    "CONFIG_JSON, DATA_SOURCE_ID, CREATED_BY, CREATED_AT) VALUES (:t, 1, "
                    "'ACTIVE', :cfg, :ds, 'admin', :now)"
                ),
                {"t": tmpl_id, "cfg": json.dumps(cfg, ensure_ascii=False), "ds": ds_id, "now": now},
            )
        created = create_batch_def(admin_ctx, {"code": "DOANH_THU", "name": "Doanh thu", "max_parallel_per_ds": 2})
        assert created.ok is True
        added = add_batch_def_items(
            admin_ctx,
            created.data["id"],
            [
                {
                    "template_id": int(tmpl_id),
                    "file_pattern": "*DTP*",
                    "multi_file": False,
                    "is_required": True,
                    "priority": 10,
                    "params_override": {"p_ky": "{ky.thang}"},
                }
            ],
        )
        assert added.ok is True
        activated = activate_batch_def(admin_ctx, created.data["id"])
        assert activated.ok is True
        run = create_batch_run(admin_ctx, created.data["id"], "2026-02")
        assert run.ok is True
        batch_run_id = int(run.data["id"])
        with engine.begin() as conn:
            for batch_id in (batch_run_id, None):
                conn.execute(
                    text(
                        "INSERT INTO RECON_RUN (TEMPLATE_ID, TEMPLATE_VERSION, PROFILE_CODE, "
                        "DATA_SOURCE_ID, P_FROM, P_TO, APPLY_RANGE_EXCEL, PROGRESS_PCT, STATUS, CREATED_BY, CREATED_AT, "
                        "BATCH_RUN_ID) VALUES (:t, 1, 'BY_DAY_POINT', :ds, :pf, :pt, "
                        "'Y', 0, 'DONE', 'admin', :now, :b)"
                    ),
                    {
                        "t": tmpl_id,
                        "ds": ds_id,
                        "pf": datetime(2026, 2, 1),
                        "pt": datetime(2026, 2, 28, 23, 59, 59),
                        "now": now,
                        "b": batch_id,
                    },
                )
        return batch_run_id

    def test_batch_only_true(self, batch_env, admin_ctx):
        from app.schemas.run import RunListFilter
        from app.services.run_service import list_runs

        self._setup(batch_env, admin_ctx)
        res = list_runs(admin_ctx, RunListFilter(batch_only=True))
        assert res.ok is True
        assert res.data["total"] == 1
        assert res.data["items"][0]["batch_def_code"] == "DOANH_THU"
        assert res.data["items"][0]["batch_run_id"] is not None

    def test_batch_only_false(self, batch_env, admin_ctx):
        from app.schemas.run import RunListFilter
        from app.services.run_service import list_runs

        self._setup(batch_env, admin_ctx)
        res = list_runs(admin_ctx, RunListFilter(batch_only=False))
        assert res.ok is True
        assert res.data["total"] == 1
        assert res.data["items"][0]["batch_def_code"] is None

    def test_batch_only_none_returns_both(self, batch_env, admin_ctx):
        from app.schemas.run import RunListFilter
        from app.services.run_service import list_runs

        self._setup(batch_env, admin_ctx)
        res = list_runs(admin_ctx, RunListFilter())
        assert res.ok is True
        assert res.data["total"] == 2
