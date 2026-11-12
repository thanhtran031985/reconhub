"""Task 64: layout modal chuyển Oracle — 2 card + stepper hiện item đang chạy.

Tests-first: helper step_counts/running_item/running_step_index chưa tồn tại,
_render_mig_stepper/_render_mig_detail chưa có dạng 2 card, callback bấm bước
chưa có — các test này phải đỏ trước khi code.
"""

from __future__ import annotations

from types import SimpleNamespace

import dash

from app.services.migration_checklist import (
    build_fake_checklist,
    mark_step_error,
    new_checklist,
    step_status,
)
from tests.unit.test_migration_stepper63 import _precheck_data


def _copy_step_running() -> dict:
    """State fake đã tick 1 lần: bảo trì + tạo schema xong, copy đang chạy."""
    from app.services.migration_checklist import advance_fake_checklist

    state = build_fake_checklist(_precheck_data())
    return advance_fake_checklist(state, per_tick=4)


# --- Helper thuần (mới, task 64) ----------------------------------------


def test_step_counts_done_total() -> None:
    from app.services.migration_checklist import step_counts

    assert step_counts({"items": []}) == (0, 0)
    assert step_counts({"items": [{"status": "done"}, {"status": "pending"}, {"status": "done"}]}) == (2, 3)


def test_running_item_first_pending() -> None:
    """running_item = dòng chờ đầu tiên (D1). Người gọi chỉ dùng cho bước
    đang chạy; bước xong thì không còn dòng chờ nên trả None."""
    from app.services.migration_checklist import running_item

    running = {
        "key": "copy",
        "label": "Sao chép",
        "error": None,
        "items": [
            {"id": "a", "label": "Bảng A", "status": "done", "detail": None},
            {"id": "b", "label": "Bảng B", "status": "pending", "detail": None},
            {"id": "c", "label": "Bảng C", "status": "pending", "detail": None},
        ],
    }
    assert step_status(running) == "running"
    item = running_item(running)
    assert item is not None and item["id"] == "b"
    # Bước chưa có dòng nào xong nhưng là bước đang chạy (0 done): dòng chờ
    # đầu tiên vẫn là item đang làm.
    just_started = {
        "key": "copy",
        "label": "Sao chép",
        "error": None,
        "items": [
            {"id": "a", "label": "Bảng A", "status": "pending", "detail": None},
            {"id": "b", "label": "Bảng B", "status": "pending", "detail": None},
        ],
    }
    assert step_status(just_started) == "pending"
    first = running_item(just_started)
    assert first is not None and first["id"] == "a"
    done_step = {
        "key": "copy",
        "label": "Sao chép",
        "error": None,
        "items": [
            {"id": "a", "label": "Bảng A", "status": "done", "detail": None},
        ],
    }
    assert running_item(done_step) is None
    assert running_item({"key": "copy", "label": "Sao chép", "error": None, "items": []}) is None


def test_running_step_index() -> None:
    from app.services.migration_checklist import running_step_index

    state = build_fake_checklist(_precheck_data())
    # Precheck xong, bảo trì đang chạy (bước chờ đầu tiên).
    assert running_step_index(state) == 1
    running = _copy_step_running()
    assert running_step_index(running) == 3
    done = new_checklist(
        mode="fake",
        target_ds_id=7,
        target_name="T",
        mode_label="NO_TEMP",
        tables=[{"table": "RECON_USER", "rows": 1}],
        top_tables=[],
    )
    for step in done["steps"]:
        for item in step["items"]:
            item["status"] = "done"
    # Task 65: 6 bước tự động xong thì bước hiện tại là bước 7 manual.
    assert running_step_index(done) == 6
    err = build_fake_checklist(_precheck_data())
    mark_step_error(err, "copy", "Lỗi kết nối giả lập")
    assert running_step_index(err) == 3


def test_error_step_index() -> None:
    from app.services.migration_checklist import error_step_index

    state = build_fake_checklist(_precheck_data())
    assert error_step_index(state) is None
    mark_step_error(state, "verify", "Checksum lệch")
    assert error_step_index(state) == 4


# --- Render stepper 2 card (task 64) -------------------------------------


def test_stepper_subline_three_states() -> None:
    from app.ui.pages.data_sources import _render_mig_stepper

    state = _copy_step_running()
    blob = str(_render_mig_stepper(state))
    # Bước 1 xong: "✓ 6/6 việc xong".
    assert "✓ 6/6 việc xong" in blob
    # Bước 2 xong: "✓ 3/3 việc xong".
    assert "✓ 3/3 việc xong" in blob
    # Bước 4 đang chạy: item đang làm + số đếm theo đơn vị bảng (0/5 vì
    # tick đầu mới xong bảo trì + tạo schema, chưa chép bảng nào).
    assert "Đang: Sao chép bảng RECON_USER" in blob
    assert "0/5 bảng xong" in blob
    # Bước 5 chờ.
    assert "Chờ • 0/3 việc" in blob
    # Không còn checklist gộp chung trong stepper: nhãn dòng con của bước
    # khác không xuất hiện ở đây (chỉ nằm trong detail).
    assert "Quyền ADMIN" not in blob
    assert "Ghi MAINTENANCE=Y" not in blob
    # Mỗi bước bấm được: id pattern-matching mig-step.
    assert blob.count("mig-step") >= 6


def test_stepper_error_subline() -> None:
    from app.ui.pages.data_sources import _render_mig_stepper

    state = build_fake_checklist(_precheck_data())
    mark_step_error(state, "copy", "Lỗi kết nối giả lập")
    blob = str(_render_mig_stepper(state))
    assert "Lỗi kết nối giả lập" in blob


def test_stepper_selected_row_highlighted() -> None:
    from app.ui.pages.data_sources import _render_mig_stepper

    state = _copy_step_running()
    blob = str(_render_mig_stepper(state, selected_idx=1))
    # Hàng đang chọn có nền nhạt primary (biến theme, không hardcode màu).
    assert "mantine-color-blue-0" in blob


# --- Render detail theo bước chọn ----------------------------------------


def test_detail_shows_only_selected_step_items() -> None:
    from app.ui.pages.data_sources import _render_mig_detail

    state = _copy_step_running()
    detail_step2 = str(_render_mig_detail(state, selected_idx=1))
    assert "Ghi MAINTENANCE=Y vào RECON_APP_SETTING" in detail_step2
    assert "Quyền ADMIN" not in detail_step2
    assert "Sao chép bảng RECON_USER" not in detail_step2
    detail_step1 = str(_render_mig_detail(state, selected_idx=0))
    assert "Quyền ADMIN" in detail_step1
    assert "Ghi MAINTENANCE=Y" not in detail_step1


def test_detail_running_item_highlighted() -> None:
    from app.services.migration_checklist import advance_fake_checklist
    from app.ui.pages.data_sources import _render_mig_detail

    # Tick 2 lần: bảo trì + tạo schema + 4 bảng xong, backfill đang làm.
    state = advance_fake_checklist(_copy_step_running(), per_tick=4)
    assert step_status(state["steps"][3]) == "running"
    blob = str(_render_mig_detail(state, selected_idx=3))
    # Item đang làm: nhãn "Đang chạy" + tên item (backfill).
    assert "Đang chạy" in blob
    assert "Nối lại liên kết" in blob
    # Dòng xong vẫn hiện trong danh sách.
    assert "Sao chép bảng RECON_USER" in blob


def test_detail_finish_step_shows_report_when_done() -> None:
    from app.services.migration_checklist import advance_fake_checklist, overall_status
    from app.ui.pages.data_sources import _render_mig_detail

    state = build_fake_checklist(_precheck_data())
    for _ in range(30):
        state = advance_fake_checklist(state, per_tick=4)
        if overall_status(state) == "done":
            break
    assert overall_status(state) == "done"
    blob = str(_render_mig_detail(state, selected_idx=5))
    assert "Chuyển dữ liệu thành công (mô phỏng)!" in blob
    assert "Dừng ứng dụng web ReconHub" in blob
    # Bước 6 chưa xong thì chưa có báo cáo.
    running = _copy_step_running()
    assert "Chuyển dữ liệu thành công" not in str(_render_mig_detail(running, selected_idx=5))


def test_detail_empty_state_hint() -> None:
    from app.ui.pages.data_sources import _empty_mig_state, _render_mig_detail

    blob = str(_render_mig_detail(_empty_mig_state(), selected_idx=0))
    assert "Kiểm tra trước" in blob
    assert "Chưa có dữ liệu" in blob


def test_detail_error_step_shows_message() -> None:
    from app.ui.pages.data_sources import _render_mig_detail

    state = build_fake_checklist(_precheck_data())
    mark_step_error(state, "copy", "Lỗi kết nối giả lập")
    blob = str(_render_mig_detail(state, selected_idx=3))
    assert "Lỗi kết nối giả lập" in blob


# --- Callback bấm bước ----------------------------------------------------


def test_step_click_selects_step(monkeypatch) -> None:
    from app.ui.pages.data_sources import handle_mig_step_click

    state = _copy_step_running()
    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(triggered_id={"type": "mig-step", "index": 1}),
    )
    selected, detail = handle_mig_step_click([0, 1, 0, 0, 0, 0], state, 3)
    assert selected == 1
    assert "Ghi MAINTENANCE=Y vào RECON_APP_SETTING" in str(detail)
    assert "Sao chép bảng RECON_USER" not in str(detail)


def test_step_click_guard_no_clicks() -> None:
    from app.ui.pages.data_sources import handle_mig_step_click

    selected, detail = handle_mig_step_click([0, 0, 0, 0, 0, 0], None, None)
    assert selected is dash.no_update
    assert detail is dash.no_update
    selected2, detail2 = handle_mig_step_click([None] * 6, None, None)
    assert selected2 is dash.no_update
    assert detail2 is dash.no_update


def test_step_click_guard_wrong_trigger(monkeypatch) -> None:
    from app.ui.pages.data_sources import handle_mig_step_click

    monkeypatch.setattr("dash.callback_context", SimpleNamespace(triggered_id="ds-mig-run-btn"))
    selected, detail = handle_mig_step_click([0, 1, 0, 0, 0, 0], None, None)
    assert selected is dash.no_update
    assert detail is dash.no_update


def test_step_click_falls_back_to_empty_state(monkeypatch) -> None:
    from app.ui.pages.data_sources import handle_mig_step_click

    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(triggered_id={"type": "mig-step", "index": 0}),
    )
    selected, detail = handle_mig_step_click([1, 0, 0, 0, 0, 0], None, None)
    assert selected == 0
    assert "Kiểm tra trước" in str(detail)
