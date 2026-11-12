"""Task 63: modal stepper chuyển Oracle — checklist helpers, checklist trong
start_migration, background runner, guard callback modal.

Tests-first: module app.services.migration_checklist chưa tồn tại, cột
CHECKLIST_JSON chưa có — các test này phải đỏ trước khi code.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import dash
import pytest
from sqlalchemy import create_engine, select

from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_metadata_migration,
    recon_user,
)
from app.services.metadata_migration import (
    get_active_migration,
    get_migration_for_poll,
    get_migration_run_result,
    run_migration_background,
    start_migration,
)
from app.services.migration_checklist import (
    MANUAL_STEP_KEY,
    MIGRATION_STEP_KEYS,
    MIGRATION_STEP_LABELS,
    advance_fake_checklist,
    build_fake_checklist,
    checklist_from_json,
    checklist_to_json,
    count_pending,
    load_checklist,
    mark_item_done,
    mark_step_error,
    new_checklist,
    overall_status,
    save_checklist,
    step_status,
)


@pytest.fixture
def mig63_env(tmp_path: Path, monkeypatch):
    """DB nguồn tạm + engine đích SQLite (theo mẫu test_metadata_migration)."""
    db_file = tmp_path / "recon_source63.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")

    from app.core.config import get_settings

    get_settings.cache_clear()

    src_engine = create_engine(db_url)
    metadata.create_all(src_engine)

    from tests.conftest import seed_perm_basics

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with src_engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                ID=1,
                USERNAME="admin_tester",
                FULL_NAME="Admin Tester",
                PASSWORD_HASH="hash",
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
    seed_perm_basics(src_engine, {1: ["ADMIN"]})

    admin_ctx = Ctx(
        user_id=1,
        username="admin_tester",
        roles=[Role.ADMIN],
        full_name="Admin Tester",
    )

    target_db = tmp_path / "target_recon63.db"
    target_engine = create_engine(f"sqlite:///{target_db.as_posix()}")
    target_file = tmp_path / "target_ds63.db"
    with src_engine.begin() as conn:
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="Target 63",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="SQLITE",
                FILE_PATH=str(target_file),
                HOST="",
                PORT=0,
                SERVICE_NAME="",
                DEFAULT_SCHEMA="",
                USERNAME="",
                PASSWORD_ENC="",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

    return src_engine, target_engine, admin_ctx, int(ds_id)


def _precheck_data() -> dict:
    return {
        "target_ds_id": 7,
        "target_name": "Oracle TEST",
        "target_env": "TEST",
        "mode": "NO_TEMP",
        "can_migrate": True,
        "ready": True,
        "tables": [
            {"table": "RECON_USER", "rows": 5, "bytes_est": 1000},
            {"table": "RECON_MENU", "rows": 12, "bytes_est": 2400},
            {"table": "RECON_RUN", "rows": 3, "bytes_est": 600},
            {"table": "RECON_RESULT_ROW", "rows": 40, "bytes_est": 8000},
        ],
        "total_rows": 60,
        "total_bytes_est": 12000,
    }


# --- Pure helpers -------------------------------------------------------


def test_new_checklist_has_seven_steps_all_pending() -> None:
    state = new_checklist(
        mode="fake",
        target_ds_id=7,
        target_name="Oracle TEST",
        mode_label="NO_TEMP",
        tables=[{"table": "RECON_USER", "rows": 5}, {"table": "RECON_MENU", "rows": 12}],
        top_tables=["RECON_MENU"],
    )
    # Task 65: thêm bước 7 "Các bước làm tay" (chưa có item lúc tạo).
    assert MIGRATION_STEP_KEYS == [
        "precheck",
        "maintenance",
        "create_schema",
        "copy",
        "verify",
        "finish",
        "manual",
    ]
    assert MIGRATION_STEP_LABELS == [
        "Kiểm tra trước",
        "Bật chế độ bảo trì",
        "Tạo schema đích",
        "Sao chép dữ liệu",
        "Đối chiếu toàn vẹn",
        "Hoàn tất",
        "Các bước làm tay",
    ]
    assert [s["key"] for s in state["steps"]] == MIGRATION_STEP_KEYS
    assert [s["label"] for s in state["steps"]] == MIGRATION_STEP_LABELS
    assert all(step_status(s) == "pending" for s in state["steps"])
    assert overall_status(state) == "idle"
    assert len(state["steps"][0]["items"]) == 6
    assert len(state["steps"][1]["items"]) == 3
    assert len(state["steps"][2]["items"]) == 1
    # Bước copy: 1 dòng/bảng + 1 dòng nối liên kết vòng.
    assert len(state["steps"][3]["items"]) == 3
    assert len(state["steps"][4]["items"]) == 1
    assert len(state["steps"][5]["items"]) == 2
    assert len(state["steps"][6]["items"]) == 0


def test_build_fake_checklist_marks_precheck_done() -> None:
    state = build_fake_checklist(_precheck_data())
    assert state["mode"] == "fake"
    assert state["target_name"] == "Oracle TEST"
    assert step_status(state["steps"][0]) == "done"
    assert all(i["status"] == "done" for i in state["steps"][0]["items"])
    assert step_status(state["steps"][1]) == "pending"
    # Bước copy: 4 bảng + backfill; bước verify: top 3 theo số dòng.
    assert [i["id"] for i in state["steps"][3]["items"]] == [
        "RECON_USER",
        "RECON_MENU",
        "RECON_RUN",
        "RECON_RESULT_ROW",
        "__backfill__",
    ]
    assert [i["id"] for i in state["steps"][4]["items"]] == [
        "RECON_RESULT_ROW",
        "RECON_MENU",
        "RECON_USER",
    ]
    assert overall_status(state) == "running"
    assert state["report"]["RECON_RESULT_ROW"] == {
        "source_rows": 40,
        "target_rows": 40,
        "matched": True,
        "checksum_matched": True,
    }
    assert state["report"]["RECON_RUN"]["checksum_matched"] is False
    assert len(state["next_steps"]) == 4


def test_advance_fake_checklist_is_pure_and_completes() -> None:
    state = build_fake_checklist(_precheck_data())
    total = count_pending(state)
    assert total > 0
    snapshot = json.dumps(state, sort_keys=True, ensure_ascii=False)
    advanced = advance_fake_checklist(state, per_tick=4)
    # Không sửa state gốc.
    assert json.dumps(state, sort_keys=True, ensure_ascii=False) == snapshot
    assert count_pending(advanced) == total - 4
    # Tick 1 xong 3 dòng bảo trì + 1 dòng tạo schema.
    assert step_status(advanced["steps"][1]) == "done"
    assert step_status(advanced["steps"][2]) == "done"
    advanced2 = advance_fake_checklist(advanced, per_tick=4)
    assert step_status(advanced2["steps"][3]) == "running"
    done = state
    for _ in range(30):
        done = advance_fake_checklist(done, per_tick=4)
        if overall_status(done) == "done":
            break
    assert overall_status(done) == "done"
    # Task 65: 6 bước tự động xong, 4 việc manual còn chờ tick.
    auto_done = [s for s in done["steps"] if s["key"] != "manual"]
    assert all(step_status(s) == "done" for s in auto_done)
    assert count_pending(done) == 4
    assert len(done["steps"][6]["items"]) == 4
    assert all(i["status"] == "pending" for i in done["steps"][6]["items"])
    # Tick tiếp khi đã xong thì giữ nguyên.
    assert advance_fake_checklist(done, per_tick=4) == done


def test_step_status_derivation() -> None:
    pending_step = {"key": "copy", "label": "Sao chép", "error": None, "items": [{"id": "a", "label": "a", "status": "pending", "detail": None}]}
    assert step_status(pending_step) == "pending"
    running_step = {"key": "copy", "label": "Sao chép", "error": None, "items": [
        {"id": "a", "label": "a", "status": "done", "detail": None},
        {"id": "b", "label": "b", "status": "pending", "detail": None},
    ]}
    assert step_status(running_step) == "running"
    done_step = {"key": "copy", "label": "Sao chép", "error": None, "items": [
        {"id": "a", "label": "a", "status": "done", "detail": None},
    ]}
    assert step_status(done_step) == "done"
    error_step = {"key": "copy", "label": "Sao chép", "error": "Lỗi kết nối", "items": [
        {"id": "a", "label": "a", "status": "done", "detail": None},
    ]}
    assert step_status(error_step) == "error"


def test_mark_item_done_and_mark_step_error() -> None:
    state = new_checklist(
        mode="real",
        target_ds_id=7,
        target_name="Oracle TEST",
        mode_label="NO_TEMP",
        tables=[{"table": "RECON_USER", "rows": 5}],
        top_tables=[],
    )
    mark_item_done(state, "precheck", "admin", detail="OK")
    assert state["steps"][0]["items"][0]["status"] == "done"
    assert state["steps"][0]["items"][0]["detail"] == "OK"
    mark_step_error(state, "copy", "Lỗi kết nối giả lập")
    assert step_status(state["steps"][3]) == "error"
    assert overall_status(state) == "error"
    assert state["error"] == "Lỗi kết nối giả lập"


def test_checklist_json_roundtrip() -> None:
    state = build_fake_checklist(_precheck_data())
    raw = checklist_to_json(state)
    assert isinstance(raw, str)
    assert checklist_from_json(raw) == state
    assert checklist_from_json(None) is None
    assert checklist_from_json("") is None
    assert checklist_from_json("không phải json") is None


# --- DB: lưu/đọc CHECKLIST_JSON ----------------------------------------


def test_save_load_checklist_roundtrip(mig63_env) -> None:
    src_engine, _, _, _ = mig63_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with src_engine.begin() as conn:
        mig_id = conn.execute(
            recon_metadata_migration.insert().values(
                SOURCE_DS_ID=1,
                TARGET_DS_ID=7,
                STATUS="PROCESSING",
                MODE="NO_TEMP",
                STAGE="COPY_RECON_USER",
                PROGRESS_PCT=20,
                CREATED_BY="admin_tester",
                CREATED_AT=now,
            )
        ).inserted_primary_key[0]
    state = build_fake_checklist(_precheck_data())
    save_checklist(src_engine, int(mig_id), state)
    assert load_checklist(src_engine, int(mig_id)) == state
    assert load_checklist(src_engine, 999999) is None


# --- start_migration ghi checklist --------------------------------------


def test_start_migration_writes_checklist(mig63_env) -> None:
    src_engine, target_engine, admin_ctx, ds_id = mig63_env
    res = start_migration(admin_ctx, target_ds_id=ds_id, mode="NO_TEMP", mock_target_engine=target_engine)
    assert res.ok, res.message
    mig_id = int(res.data["migration_id"])
    state = load_checklist(src_engine, mig_id)
    assert state is not None
    assert state["mode"] == "real"
    assert overall_status(state) == "done"
    # Task 65: 6 bước tự động xong, bước 7 manual có 4 việc chờ tick.
    auto_steps = [s for s in state["steps"] if s["key"] != MANUAL_STEP_KEY]
    assert all(step_status(s) == "done" for s in auto_steps)
    manual = state["steps"][6]
    assert manual["key"] == MANUAL_STEP_KEY
    assert len(manual["items"]) == 4
    assert all(i["status"] == "pending" for i in manual["items"])
    copy_items = {i["id"]: i for i in state["steps"][3]["items"]}
    assert "RECON_USER" in copy_items
    assert copy_items["RECON_USER"]["status"] == "done"
    assert copy_items["RECON_USER"]["detail"] is not None
    assert "__backfill__" in copy_items
    assert len(state["steps"][4]["items"]) == 3
    # REPORT_JSON giữ nguyên shape cũ (D1).
    with src_engine.connect() as conn:
        row = conn.execute(
            select(recon_metadata_migration).where(recon_metadata_migration.c.ID == mig_id)
        ).mappings().first()
    assert row is not None
    assert row["STATUS"] == "DONE"
    report = row["REPORT_JSON"]
    assert isinstance(report, dict)
    assert report["RECON_USER"]["source_rows"] == report["RECON_USER"]["target_rows"]
    assert "checklist" not in report


def test_start_migration_failed_step_marked(mig63_env) -> None:
    src_engine, target_engine, admin_ctx, ds_id = mig63_env
    with patch(
        "app.services.metadata_migration._copy_table_data",
        side_effect=RuntimeError("Lỗi kết nối giả lập giữa chừng"),
    ):
        res = start_migration(admin_ctx, target_ds_id=ds_id, mode="NO_TEMP", mock_target_engine=target_engine)
        assert res.ok is False
    with src_engine.connect() as conn:
        row = (
            conn.execute(
                select(recon_metadata_migration).where(recon_metadata_migration.c.TARGET_DS_ID == ds_id)
            )
            .mappings()
            .first()
        )
    assert row is not None
    assert row["STATUS"] == "FAILED"
    state = checklist_from_json(row["CHECKLIST_JSON"])
    assert state is not None
    assert overall_status(state) == "error"
    assert step_status(state["steps"][3]) == "error"
    assert "Lỗi kết nối giả lập" in (state["steps"][3]["error"] or "")


def test_start_migration_precheck_failure_blocks(mig63_env) -> None:
    """D3: precheck lỗi thì start_migration phải dừng, không bật bảo trì,
    không tạo phiên (hành vi cũ: bỏ qua kết quả precheck và chạy tiếp)."""
    src_engine, target_engine, admin_ctx, ds_id = mig63_env
    # Đích không trống: tạo bảng RECON_USER có dữ liệu trên engine đích.
    import sqlalchemy as sa

    from app.db.metadata import recon_app_setting

    with target_engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE RECON_USER (ID INTEGER PRIMARY KEY, USERNAME TEXT)"))
        conn.execute(sa.text("INSERT INTO RECON_USER (ID, USERNAME) VALUES (1, 'x')"))
    res = start_migration(admin_ctx, target_ds_id=ds_id, mode="NO_TEMP", mock_target_engine=target_engine)
    assert res.ok is False
    with src_engine.connect() as conn:
        rows = conn.execute(select(recon_metadata_migration)).fetchall()
        assert rows == []
        maint_row = conn.execute(
            select(recon_app_setting).where(recon_app_setting.c.KEY == "MAINTENANCE")
        ).fetchall()
        assert maint_row == []


def test_get_active_migration_and_for_poll(mig63_env) -> None:
    src_engine, _, admin_ctx, ds_id = mig63_env
    assert get_active_migration(admin_ctx).data is None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with src_engine.begin() as conn:
        conn.execute(
            recon_metadata_migration.insert().values(
                SOURCE_DS_ID=1,
                TARGET_DS_ID=ds_id,
                STATUS="DONE",
                MODE="NO_TEMP",
                STAGE="COMPLETED",
                PROGRESS_PCT=100,
                CREATED_BY="admin_tester",
                CREATED_AT=now,
            )
        )
        proc_id = conn.execute(
            recon_metadata_migration.insert().values(
                SOURCE_DS_ID=1,
                TARGET_DS_ID=ds_id,
                STATUS="PROCESSING",
                MODE="NO_TEMP",
                STAGE="COPY_RECON_USER",
                PROGRESS_PCT=20,
                CREATED_BY="admin_tester",
                CREATED_AT=now,
            )
        ).inserted_primary_key[0]
    active = get_active_migration(admin_ctx)
    assert active.ok
    assert active.data is not None
    assert int(active.data["ID"]) == int(proc_id)
    # Poll: chỉ lấy phiên tạo sau started_at.
    before = get_migration_for_poll(admin_ctx, ds_id, started_at="2000-01-01T00:00:00")
    assert before.ok and before.data is not None
    assert int(before.data["ID"]) == int(proc_id)
    after = get_migration_for_poll(admin_ctx, ds_id, started_at="2999-01-01T00:00:00")
    assert after.ok and after.data is None


def test_run_migration_background_registers_result(mig63_env) -> None:
    src_engine, target_engine, admin_ctx, ds_id = mig63_env
    run_migration_background(admin_ctx, ds_id, "NO_TEMP", "token-63-ok", mock_target_engine=target_engine)
    result = get_migration_run_result("token-63-ok")
    assert result is not None
    assert result["ok"] is True
    assert result["migration_id"] is not None
    with src_engine.connect() as conn:
        row = conn.execute(
            select(recon_metadata_migration).where(
                recon_metadata_migration.c.ID == int(result["migration_id"])
            )
        ).mappings().first()
    assert row is not None
    assert row["STATUS"] == "DONE"
    assert get_migration_run_result("token-khong-ton-tai") is None


# --- Guard callback modal (UI) ------------------------------------------


def test_mig_modal_open_guard_no_clicks(monkeypatch) -> None:
    from app.ui.pages.data_sources import toggle_mig_modal

    out = toggle_mig_modal(None, None, False, None, None)
    assert isinstance(out, tuple)
    assert len(out) == 14
    assert all(v is dash.no_update for v in out)
    out2 = toggle_mig_modal(0, 0, False, None, None)
    assert all(v is dash.no_update for v in out2)


def test_mig_modal_close_returns_closed(monkeypatch) -> None:
    from app.ui.pages.data_sources import toggle_mig_modal

    monkeypatch.setattr(
        "dash.callback_context", SimpleNamespace(triggered_id="ds-mig-modal-close-btn")
    )
    out = toggle_mig_modal(None, 1, True, None, None)
    assert out[0] is False  # modal đóng
    assert out[9] is True  # fake tick tắt
    assert out[10] is True  # real tick tắt


def test_mig_run_guard_no_clicks() -> None:
    from app.ui.pages.data_sources import handle_mig_run

    out = handle_mig_run(None, None, None, False)
    assert isinstance(out, tuple)
    assert len(out) == 9
    assert all(v is dash.no_update for v in out)
    assert all(v is dash.no_update for v in handle_mig_run(0, None, None, False))


def test_mig_fake_tick_guard_no_state() -> None:
    from app.ui.pages.data_sources import handle_mig_fake_tick

    out = handle_mig_fake_tick(1, None, None)
    assert out[2] is True  # tick tắt khi không có state
    assert out[0] is dash.no_update


def test_mig_stepper_renders_six_steps() -> None:
    from app.ui.pages.data_sources import _render_mig_stepper

    state = build_fake_checklist(_precheck_data())
    node = _render_mig_stepper(state)
    # Repr của Dash component chứa đệ quy text các node con.
    blob = str(node)
    for label in MIGRATION_STEP_LABELS:
        assert label in blob
    # Dòng phụ: bước 1 xong, bước 2 đang chạy, bước 3 chờ (task 64).
    assert "✓ 6/6 việc xong" in blob
    assert "Đang: Ghi MAINTENANCE=Y vào RECON_APP_SETTING" in blob
    assert "Chờ • 0/1 việc" in blob
    # Checklist dòng con nằm ở detail (task 64), không gộp trong stepper.
    assert "RECON_RESULT_ROW" not in blob
    assert "Quyền ADMIN" not in blob


def test_mig_run_fake_path_uses_real_precheck(mig63_env, monkeypatch) -> None:
    """Fake: precheck thật qua DS SQLITE, không tạo phiên migration,
    không bật bảo trì (D2)."""
    from app.ui.pages.data_sources import handle_mig_run

    src_engine, _, admin_ctx, ds_id = mig63_env
    monkeypatch.setattr("app.ui.pages.data_sources.get_current_ctx", lambda: admin_ctx)
    out = handle_mig_run(1, str(ds_id), "NO_TEMP", False)
    state, real_store, fake_disabled, real_disabled, stepper, detail, selected, run_disabled, progress = out
    assert state is not None
    assert state["mode"] == "fake"
    assert step_status(state["steps"][0]) == "done"
    assert real_store is None
    assert fake_disabled is False
    assert real_disabled is True
    assert run_disabled is True
    assert selected == 1  # bước đang chạy: bảo trì
    assert "Ghi MAINTENANCE=Y vào RECON_APP_SETTING" in str(detail)
    # Follow-up task 65: progress bar hiện số việc theo precheck thật
    # (DB seed của mig63_env có nhiều bảng hơn fixture _precheck_data
    # nên tổng việc không cố định 20 — tính từ state).
    from app.services.migration_checklist import progress_counts

    done, total = progress_counts(state)
    assert f"{done}/{total} việc" in str(progress)
    assert "Đang chạy bước 2/6" in str(progress)
    with src_engine.connect() as conn:
        assert conn.execute(select(recon_metadata_migration)).fetchall() == []
        from app.db.metadata import recon_app_setting

        assert (
            conn.execute(
                select(recon_app_setting).where(recon_app_setting.c.KEY == "MAINTENANCE")
            ).fetchall()
            == []
        )
