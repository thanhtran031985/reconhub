"""Task 65: sửa modal migration (idle, bước 7 manual) + layout tab Lưu trữ.

Tests-first: helper bước 7 + callback tick + render idle + cấu trúc
2 card / nút Xem trước chưa tồn tại — các test này phải đỏ trước khi code.
"""

from __future__ import annotations

from types import SimpleNamespace

import dash

from app.services.migration_checklist import (
    build_fake_checklist,
    new_checklist,
    overall_status,
    step_status,
)
from tests.unit.test_migration_stepper63 import _precheck_data, mig63_env

# Re-export fixture dùng chung với test_migration_stepper63 (pattern của
# test_export_concurrency57): __all__ đánh dấu import đã dùng cho ruff.
__all__ = ["mig63_env"]


def _done_fake_state() -> dict:
    """State fake chạy hết 6 bước tự động (chưa tick manual)."""
    from app.services.migration_checklist import advance_fake_checklist

    state = build_fake_checklist(_precheck_data())
    for _ in range(30):
        state = advance_fake_checklist(state, per_tick=4)
        if overall_status(state) == "done":
            break
    return state


def _tree_nodes(node: object) -> list:
    """Đi đệ quy cây component Dash, trả mọi node (kể cả gốc)."""
    out = [node]
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            out.extend(_tree_nodes(child))
    elif children is not None:
        out.extend(_tree_nodes(children))
    return out


def _has_id(node: object, wanted: str) -> bool:
    return any(getattr(n, "id", None) == wanted for n in _tree_nodes(node))


def _has_text(node: object, text: str) -> bool:
    return text in str(node)


# --- Bước 1: lỗi idle -----------------------------------------------------


def test_stepper_idle_shows_all_waiting() -> None:
    """Modal mới mở (state idle, 6 bước 0 item): không bước nào tô xanh
    hay ghi "Đang chạy…" — tất cả hiện "Chờ"."""
    from app.ui.pages.data_sources import _empty_mig_state, _render_mig_stepper

    blob = str(_render_mig_stepper(_empty_mig_state(), 0))
    assert "Đang chạy…" not in blob
    assert "Đang:" not in blob
    assert blob.count("Chờ") >= 7
    for label in (
        "Kiểm tra trước",
        "Bật chế độ bảo trì",
        "Tạo schema đích",
        "Sao chép dữ liệu",
        "Đối chiếu toàn vẹn",
        "Hoàn tất",
        "Các bước làm tay",
    ):
        assert label in blob


def test_detail_idle_still_hints_to_start() -> None:
    from app.ui.pages.data_sources import _empty_mig_state, _render_mig_detail

    blob = str(_render_mig_detail(_empty_mig_state(), 0))
    assert "Chưa có dữ liệu" in blob
    assert "Đang chạy" not in blob


# --- Bước 2: bước 7 manual — helper thuần ---------------------------------


def test_new_checklist_has_seven_steps_manual_last_empty() -> None:
    state = new_checklist(
        mode="fake",
        target_ds_id=7,
        target_name="Oracle TEST",
        mode_label="NO_TEMP",
        tables=[{"table": "RECON_USER", "rows": 5}],
        top_tables=[],
    )
    assert len(state["steps"]) == 7
    manual = state["steps"][6]
    assert manual["key"] == "manual"
    assert manual["label"] == "Các bước làm tay"
    assert manual["items"] == []
    assert step_status(manual) == "pending"
    assert overall_status(state) == "idle"


def test_manual_items_from_next_steps() -> None:
    """Item bước 7 lấy từ next_steps, bỏ số thứ tự đầu dòng."""
    from app.services.migration_checklist import manual_items

    items = manual_items(
        [
            "1. Dừng ứng dụng web ReconHub và background worker.",
            "2. Cập nhật biến môi trường RECON_DB_URL trong file .env: oracle+oracledb://u:***@h:1521/?service_name=X",
            "3. Chạy lệnh kiểm tra schema: uv run poe db-migrate",
            "4. Khởi động lại dịch vụ web và worker để chạy hoàn toàn trên Oracle.",
        ]
    )
    assert [i["id"] for i in items] == ["manual-1", "manual-2", "manual-3", "manual-4"]
    assert items[0]["label"] == "Dừng ứng dụng web ReconHub và background worker."
    assert items[1]["label"].startswith("Cập nhật biến môi trường RECON_DB_URL")
    assert items[2]["label"] == "Chạy lệnh kiểm tra schema: uv run poe db-migrate"
    assert all(i["status"] == "pending" for i in items)


def test_populate_manual_items_only_once() -> None:
    """Nạp item bước 7 từ next_steps; nạp lại không reset tick đã có."""
    from app.services.migration_checklist import populate_manual_items, set_item_status

    state = _done_fake_state()
    assert state["steps"][6]["items"] != []
    assert all(i["status"] == "pending" for i in state["steps"][6]["items"])
    assert set_item_status(state, "manual", "manual-1", "done") is True
    assert set_item_status(state, "manual", "manual-99", "done") is False
    assert populate_manual_items(state) is False  # đã có item -> không nạp lại
    assert state["steps"][6]["items"][0]["status"] == "done"
    assert state["steps"][6]["items"][1]["status"] == "pending"


def test_set_item_status_and_step_done() -> None:
    """Tick đủ 4 item -> bước 7 hiện done; bỏ tick 1 item -> running."""
    from app.services.migration_checklist import set_item_status

    state = _done_fake_state()
    manual = state["steps"][6]
    for item in manual["items"]:
        assert set_item_status(state, "manual", item["id"], "done") is True
    assert step_status(manual) == "done"
    assert set_item_status(state, "manual", "manual-2", "pending") is True
    assert step_status(manual) == "running"


def test_overall_status_excludes_manual() -> None:
    """6 bước tự động xong là overall done, dù bước 7 còn chờ tick."""
    state = _done_fake_state()
    assert overall_status(state) == "done"
    assert step_status(state["steps"][6]) == "pending"


def test_advance_fake_skips_manual_items() -> None:
    """Tick fake không tự đánh dấu các bước làm tay (chỉ user tick)."""
    from app.services.migration_checklist import advance_fake_checklist

    state = _done_fake_state()
    assert overall_status(state) == "done"
    assert all(i["status"] == "pending" for i in state["steps"][6]["items"])
    again = advance_fake_checklist(state, per_tick=4)
    assert all(i["status"] == "pending" for i in again["steps"][6]["items"])
    assert overall_status(again) == "done"


def test_ensure_manual_step_on_old_checklist() -> None:
    """Checklist cũ (6 bước, không có manual) được chuẩn hóa lên 7 bước;
    phiên DONE có next_steps thì nạp luôn item manual (chưa tick)."""
    from app.services.migration_checklist import ensure_manual_step

    old = build_fake_checklist(_precheck_data())
    old["steps"] = old["steps"][:6]
    assert ensure_manual_step(old) is True
    assert len(old["steps"]) == 7
    assert old["steps"][6]["key"] == "manual"
    assert old["steps"][6]["items"] == []
    # Phiên DONE: nạp item từ next_steps.
    done = _done_fake_state()
    done["steps"] = done["steps"][:6]
    assert ensure_manual_step(done) is True
    assert len(done["steps"][6]["items"]) == 4
    assert all(i["status"] == "pending" for i in done["steps"][6]["items"])
    # Đã có manual thì không động vào.
    assert ensure_manual_step(done) is False


# --- Bước 2: detail bước 7 + callback tick --------------------------------


def test_detail_manual_step_shows_checkboxes_and_note() -> None:
    """Detail bước 7: 4 checkbox (id mig-manual-check), chưa chạy xong
    6 bước thì chỉ hiện ghi chú, không có checkbox."""
    from app.ui.pages.data_sources import _render_mig_detail

    state = _done_fake_state()
    blob = str(_render_mig_detail(state, selected_idx=6))
    assert "Các bước làm tay" in blob
    assert blob.count("mig-manual-check") == 4
    assert "Dừng ứng dụng web ReconHub" in blob
    # Bước 7 chưa mở (0 item): ghi chú, không checkbox.
    locked = build_fake_checklist(_precheck_data())
    blob_locked = str(_render_mig_detail(locked, selected_idx=6))
    assert "mig-manual-check" not in blob_locked
    assert "Chạy xong 6 bước" in blob_locked


def test_detail_finish_step_still_shows_report() -> None:
    """Báo cáo đối chiếu vẫn ở detail bước 6 (finish), không dời sang
    bước 7."""
    from app.ui.pages.data_sources import _render_mig_detail

    state = _done_fake_state()
    assert "Chuyển dữ liệu thành công (mô phỏng)!" in str(_render_mig_detail(state, selected_idx=5))
    assert "Chuyển dữ liệu thành công (mô phỏng)!" not in str(_render_mig_detail(state, selected_idx=6))


def test_manual_tick_callback_fake_updates_state(monkeypatch) -> None:
    """Bấm checkbox bước tay (fake): state đổi, tick còn sau khi vẽ lại."""
    from app.ui.pages.data_sources import handle_mig_manual_tick

    state = _done_fake_state()
    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(
            triggered_id={"type": "mig-manual-check", "item": "manual-2"},
            triggered=[{"prop_id": '{"item":"manual-2","type":"mig-manual-check"}.checked', "value": True}],
        ),
    )
    new_state, stepper, detail = handle_mig_manual_tick([False, True, False, False], state, 6)
    assert new_state["steps"][6]["items"][1]["status"] == "done"
    assert new_state["steps"][6]["items"][0]["status"] == "pending"
    assert "Các bước làm tay" in str(stepper)
    assert "Cần làm tay" in str(detail)
    # Vẽ lại từ state đã tick: checkbox vẫn checked.
    from app.ui.pages.data_sources import _render_mig_detail

    assert "mig-manual-check" in str(_render_mig_detail(new_state, selected_idx=6))


def test_manual_tick_callback_real_saves_to_db(mig63_env, monkeypatch) -> None:
    """Bấm checkbox bước tay (thật): CHECKLIST_JSON trong DB có tick."""
    from app.services.metadata_migration import start_migration
    from app.services.migration_checklist import load_checklist
    from app.ui.pages.data_sources import handle_mig_manual_tick

    src_engine, target_engine, admin_ctx, ds_id = mig63_env
    res = start_migration(admin_ctx, target_ds_id=ds_id, mode="NO_TEMP", mock_target_engine=target_engine)
    assert res.ok, res.message
    mig_id = int(res.data["migration_id"])
    state = load_checklist(src_engine, mig_id)
    assert state is not None
    assert len(state["steps"][6]["items"]) == 4
    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(
            triggered_id={"type": "mig-manual-check", "item": "manual-1"},
            triggered=[{"prop_id": '{"item":"manual-1","type":"mig-manual-check"}.checked', "value": True}],
        ),
    )
    monkeypatch.setattr("app.ui.pages.data_sources.get_current_ctx", lambda: admin_ctx)
    new_state, _, _ = handle_mig_manual_tick([True, False, False, False], state, 6)
    assert new_state["steps"][6]["items"][0]["status"] == "done"
    saved = load_checklist(src_engine, mig_id)
    assert saved is not None
    assert saved["steps"][6]["items"][0]["status"] == "done"
    assert saved["steps"][6]["items"][1]["status"] == "pending"


# --- Bước 2b: guard chống modal tự đóng khi tab vẽ lại -----------------


def test_toggle_modal_ignores_remount_spurious_fire(monkeypatch) -> None:
    """Nút mở bị tạo lại khi tab Lưu trữ vẽ lại (n_clicks 2 -> 0) kích hoạt
    callback nhưng không phải click thật: modal đang mở phải giữ nguyên.

    Bối cảnh: user đã bấm Đóng 1 lần trước đó (close_clicks=1) nên guard cũ
    (0, 0) không chặn được; lần kích hoạt giả có open_clicks=0 và
    target_ds_id=None (select đích cũng bị tạo lại) -> trước fix này
    toggle trả opened=False làm modal tự đóng sau khi migration thật DONE.
    """
    from app.ui.pages.data_sources import toggle_mig_modal

    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(triggered_id="ds-mig-start-btn"),
    )
    out = toggle_mig_modal(0, 1, True, None, "NO_TEMP")
    assert len(out) == 13
    assert all(v is dash.no_update for v in out)


def test_toggle_modal_reopen_without_target_restores_done_session(mig63_env, monkeypatch) -> None:
    """Mở lại modal khi select đích đã reset về None: vẫn khôi phục phiên
    DONE còn bước tay chưa tick (thay vì chặn bằng 'Vui lòng chọn...').

    Bối cảnh: sau migration thật DONE, tab Lưu trữ vẽ lại làm select đích
    mất value; guard `if not target_ds_id` đứng trước nhánh khôi phục nên
    toggle trả opened=False — user đóng modal rồi không mở lại được để
    tick các bước làm tay. Nhánh khôi phục dùng TARGET_DS_ID lưu trong DB
    nên không cần select; chỉ mở mới (empty state) mới cần target.
    """
    from app.services.metadata_migration import start_migration
    from app.ui.pages.data_sources import _MIG_MANUAL_IDX, toggle_mig_modal

    src_engine, target_engine, admin_ctx, ds_id = mig63_env
    res = start_migration(
        admin_ctx, target_ds_id=ds_id, mode="NO_TEMP", mock_target_engine=target_engine
    )
    assert res.ok, res.message
    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(triggered_id="ds-mig-start-btn"),
    )
    monkeypatch.setattr("app.ui.pages.data_sources.get_current_ctx", lambda: admin_ctx)
    # User đã bấm Đóng 1 lần (close_clicks=1), select đích reset -> None.
    out = toggle_mig_modal(1, 1, False, None, "NO_TEMP")
    assert len(out) == 13
    assert out[0] is True
    assert _has_text(out[1], "còn 4/4 bước làm tay chưa đánh dấu")
    assert out[6] == _MIG_MANUAL_IDX


# --- Bước 3: hai card migration + script cùng hàng ------------------------


def test_storage_two_cards_share_row() -> None:
    """Paper 'Chuyển dữ liệu sang Oracle' và Paper 'Script khởi tạo schema
    đích Oracle' nằm chung một SimpleGrid 2 cột (1 cột dưới md) — và CHỈ
    2 card đó (card 'Bản lưu SQLite cũ' đứng ngoài grid, full width)."""
    from app.ui.pages.data_sources import render_storage_tab

    content = render_storage_tab(
        {
            "temp_bytes": 0,
            "warning_gb": 2.0,
            "warning_days": 30,
            "is_warning": False,
            "uncheck_count": 0,
            "stale_count": 0,
        },
        purge_logs=[],
    )
    grids = [n for n in _tree_nodes(content) if type(n).__name__ == "SimpleGrid"]
    assert grids, "không tìm thấy SimpleGrid nào"
    target = None
    for grid in grids:
        if _has_id(grid, "ds-mig-target-select") and _has_text(grid, "Script khởi tạo schema đích Oracle"):
            target = grid
            break
    assert target is not None, "hai card migration + script không chung một SimpleGrid"
    assert getattr(target, "cols", None) == {"base": 1, "md": 2}
    # Grid chỉ có đúng 2 Paper con, theo thứ tự migration rồi script;
    # card 'Bản lưu SQLite cũ' đứng ngoài grid, full width (task 65:
    # thứ tự gốc là migration -> SQLite cũ -> script nên dễ ôm nhầm 3 card).
    papers = [n for n in _tree_nodes(target) if type(n).__name__ == "Paper"]
    assert len(papers) == 2, f"grid phải có đúng 2 Paper, thấy {len(papers)}"
    assert _has_text(papers[0], "Chuyển dữ liệu sang Oracle")
    assert _has_text(papers[1], "Script khởi tạo schema đích Oracle")
    assert not _has_text(target, "Bản lưu SQLite cũ")


# --- Bước 4: nút Xem trước cùng hàng với ô lọc ----------------------------


def test_purge_preview_button_same_row_as_filters() -> None:
    """Nút 'Xem trước' nằm trong cùng hàng flex với 4 ô lọc, căn cuối
    (thẳng hàng ô nhập, không rớt dòng)."""
    from app.ui.pages.data_sources import render_storage_tab

    content = render_storage_tab(
        {
            "temp_bytes": 0,
            "warning_gb": 2.0,
            "warning_days": 30,
            "is_warning": False,
            "uncheck_count": 0,
            "stale_count": 0,
        },
        purge_logs=[],
    )
    filter_ids = [
        "ds-purge-filter-template",
        "ds-purge-filter-checked",
        "ds-purge-filter-days",
        "ds-purge-filter-user",
    ]
    rows = []
    for node in _tree_nodes(content):
        style = getattr(node, "style", None) or {}
        if isinstance(style, dict) and style.get("display") == "flex" and style.get("alignItems") == "flex-end":
            rows.append(node)
    assert rows, "không tìm thấy hàng flex align-items flex-end"
    row = next(
        (
            r
            for r in rows
            if _has_id(r, "ds-purge-preview-btn") and all(_has_id(r, fid) for fid in filter_ids)
        ),
        None,
    )
    assert row is not None, "nút Xem trước không cùng hàng flex với 4 ô lọc"
    style = getattr(row, "style", {}) or {}
    assert style.get("flexWrap") == "nowrap"
