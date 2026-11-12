"""Follow-up task 65: bỏ next-steps ở bước 6, click bước đổi indicator,
progress bar trong modal migration.

Tests-first: các test này phải đỏ trước khi code (report còn khối
next-steps, click handler chỉ trả 2 output, chưa có progress_counts /
_render_mig_progress).
"""

from __future__ import annotations

from types import SimpleNamespace

import dash

from app.services.migration_checklist import (
    advance_fake_checklist,
    build_fake_checklist,
    overall_status,
)
from tests.unit.test_migration_stepper63 import _precheck_data, mig63_env

# Re-export fixture dùng chung với test_migration_stepper63 (pattern của
# test_export_concurrency57): __all__ đánh dấu import đã dùng cho ruff.
__all__ = ["mig63_env"]


def _done_fake_state() -> dict:
    """State fake chạy hết 6 bước tự động (chưa tick manual)."""
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


def _progress_node(node: object) -> object | None:
    for n in _tree_nodes(node):
        if type(n).__name__ == "Progress":
            return n
    return None


def _step_block(stepper: object, idx: int) -> object | None:
    for n in _tree_nodes(stepper):
        if getattr(n, "id", None) == {"type": "mig-step", "index": idx}:
            return n
    return None


def _is_selected(block: object | None) -> bool:
    if block is None:
        return False
    style = getattr(block, "style", None) or {}
    return style.get("backgroundColor") == "var(--mantine-color-blue-0)"


# --- Bước 1: bỏ next-steps khỏi detail bước 6 ------------------------------


def test_report_has_no_next_steps_but_keeps_table() -> None:
    """Báo cáo đối chiếu không còn khối 'Các bước tiếp theo' (đã có ở
    bước 7) nhưng vẫn có bảng đối chiếu + tiêu đề thành công."""
    from app.ui.pages.data_sources import _render_mig_report

    report = {
        "RECON_USER": {"source_rows": 5, "target_rows": 5, "matched": True, "checksum_matched": True},
        "RECON_MENU": {"source_rows": 12, "target_rows": 12, "matched": True, "checksum_matched": False},
    }
    blob = str(_render_mig_report(report, fake=True))
    assert "Các bước tiếp theo" not in blob
    assert "Chuyển dữ liệu thành công (mô phỏng)!" in blob
    assert "RECON_USER" in blob
    assert "RECON_MENU" in blob
    assert "Tất cả các bảng đã được sao chép" in blob


def test_detail_finish_step_has_no_next_steps() -> None:
    """Detail bước 6 sau khi fake xong: còn báo cáo, hết 4 dòng tay."""
    from app.ui.pages.data_sources import _render_mig_detail

    state = _done_fake_state()
    blob = str(_render_mig_detail(state, selected_idx=5))
    assert "Các bước tiếp theo" not in blob
    assert "Chuyển dữ liệu thành công (mô phỏng)!" in blob
    assert "RECON_USER" in blob
    # 4 việc tay chỉ còn ở detail bước 7, không ở bước 6.
    assert "Dừng ứng dụng web ReconHub" not in blob


# --- Bước 2: click bước đổi indicator --------------------------------------


def test_step_click_renders_stepper_with_new_selected(monkeypatch) -> None:
    """Bấm bước 6 sau khi fake xong (đang chọn bước 7): handler trả 3
    output, stepper vẽ lại với bước 6 được chọn (highlight), bước 7 hết
    chọn; detail sang bước 6."""
    from app.ui.pages.data_sources import handle_mig_step_click

    state = _done_fake_state()
    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(triggered_id={"type": "mig-step", "index": 5}),
    )
    selected, detail, stepper = handle_mig_step_click([0, 0, 0, 0, 0, 1, 0], state, 6)
    assert selected == 5
    assert "Chuyển dữ liệu thành công (mô phỏng)!" in str(detail)
    assert _is_selected(_step_block(stepper, 5)) is True
    assert _is_selected(_step_block(stepper, 6)) is False
    assert "Hoàn tất" in str(stepper)


def test_step_click_guards_return_three_no_updates(monkeypatch) -> None:
    """Guard không click thật / sai trigger trả đủ 3 no_update."""
    from app.ui.pages.data_sources import handle_mig_step_click

    out = handle_mig_step_click([0, 0, 0, 0, 0, 0, 0], None, None)
    assert len(out) == 3
    assert all(v is dash.no_update for v in out)
    monkeypatch.setattr("dash.callback_context", SimpleNamespace(triggered_id="ds-mig-run-btn"))
    out2 = handle_mig_step_click([0, 1, 0, 0, 0, 0, 0], None, None)
    assert len(out2) == 3
    assert all(v is dash.no_update for v in out2)


# --- Bước 3: progress_counts (helper thuần) --------------------------------


def test_progress_counts_idle_zero() -> None:
    """State idle (7 bước, 0 item): 0/total; total = 14 với 1 bảng
    (6+3+1+2+0+2), không tính item manual."""
    from app.services.migration_checklist import new_checklist, progress_counts

    state = new_checklist(
        mode="fake",
        target_ds_id=7,
        target_name="Oracle TEST",
        mode_label="NO_TEMP",
        tables=[{"table": "RECON_USER", "rows": 5}],
        top_tables=[],
    )
    done, total = progress_counts(state)
    assert (done, total) == (0, 14)


def test_progress_counts_fake_start_and_mid() -> None:
    """Fake mới bắt đầu: bước 1 xong (6/20); tick thêm 4 dòng -> 10/20."""
    from app.services.migration_checklist import progress_counts

    state = build_fake_checklist(_precheck_data())
    assert progress_counts(state) == (6, 20)
    state = advance_fake_checklist(state, per_tick=4)
    assert progress_counts(state) == (10, 20)


def test_progress_counts_done_excludes_manual() -> None:
    """Fake xong: 20/20 (6 bước tự động), dù bước 7 có 4 item pending —
    manual không tính vào tổng."""
    from app.services.migration_checklist import progress_counts

    state = _done_fake_state()
    assert overall_status(state) == "done"
    assert len(state["steps"][6]["items"]) == 4
    assert progress_counts(state) == (20, 20)


# --- Bước 3: _render_mig_progress ------------------------------------------


def test_render_progress_idle_is_empty() -> None:
    """Lúc idle không hiện bar: không có node Progress, không có '%'."""
    from app.ui.pages.data_sources import _empty_mig_state, _render_mig_progress

    rendered = _render_mig_progress(_empty_mig_state())
    assert _progress_node(rendered) is None
    assert "%" not in str(rendered)


def test_render_progress_running_shows_value_and_step() -> None:
    """Đang chạy (fake mới bắt đầu, bước 2 đang chạy): bar 30%,
    label ghi bước đang chạy + số việc."""
    from app.ui.pages.data_sources import _render_mig_progress

    state = build_fake_checklist(_precheck_data())
    rendered = _render_mig_progress(state)
    progress = _progress_node(rendered)
    assert progress is not None
    assert getattr(progress, "value", None) == 30
    blob = str(rendered)
    assert "Đang chạy bước 2/6" in blob
    assert "Bật chế độ bảo trì" in blob
    assert "6/20 việc" in blob
    assert "(30%)" in blob


def test_render_progress_done_is_full() -> None:
    """Chạy xong: bar 100%, label 'Hoàn tất 20/20 việc'."""
    from app.ui.pages.data_sources import _render_mig_progress

    rendered = _render_mig_progress(_done_fake_state())
    progress = _progress_node(rendered)
    assert progress is not None
    assert getattr(progress, "value", None) == 100
    assert "Hoàn tất 20/20 việc" in str(rendered)


def test_render_progress_error_is_red() -> None:
    """Bước lỗi: bar đỏ, label ghi bước lỗi."""
    from app.services.migration_checklist import mark_step_error
    from app.ui.pages.data_sources import _render_mig_progress

    state = build_fake_checklist(_precheck_data())
    mark_step_error(state, "copy", "Lỗi kết nối giả lập")
    rendered = _render_mig_progress(state)
    progress = _progress_node(rendered)
    assert progress is not None
    assert getattr(progress, "color", None) == "red"
    blob = str(rendered)
    assert "Lỗi ở bước 4/6" in blob
    assert "Sao chép dữ liệu" in blob
